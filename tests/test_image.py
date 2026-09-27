"""이미지 입력 고정과 `api` 컨테이너 권한 (D18, 2026-09-27 감사 F110·F111).

값(digest·판)은 원천에만 있다 — 여기서는 **모양**만 잠근다. 떠 있는 태그, 판 없는 설치, root 로 도는 api 로
조용히 되돌아가지 않게 한다. Dockerfile·docker-compose.yml 은 이미지 안에 없으므로 호스트에서 돈다.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"
COMPOSE = ROOT / "docker-compose.yml"

pytestmark = pytest.mark.skipif(
    not DOCKERFILE.exists() or not COMPOSE.exists(),
    reason="이미지 안에는 Dockerfile·docker-compose.yml 이 없다 — 호스트에서 돈다",
)

# `이름:태그@sha256:…` — 태그는 사람이 읽으라고 남기고, 받는 것은 digest 가 정한다.
PINNED = re.compile(r"[\w./-]+:[\w.-]+@sha256:[0-9a-f]{64}")


def _stages() -> list[tuple[str, list[list[str]]]]:
    """(스테이지 이름, 명령들). 주석을 버리고 줄 이음(`\\`)을 합친다. 명령은 낱말 목록이다."""
    stages: list[tuple[str, list[list[str]]]] = []
    buffer = ""
    for line in DOCKERFILE.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if text.endswith("\\"):
            buffer += text[:-1] + " "
            continue
        words = (buffer + text).split()
        buffer = ""
        if words[0].upper() == "FROM":
            args = [w for w in words[1:] if not w.startswith("--")]
            stages.append((args[2] if len(args) >= 3 and args[1].upper() == "AS" else "", [words]))
        else:
            stages[-1][1].append(words)
    return stages


def _runtime() -> list[list[str]]:
    (commands,) = [c for name, c in _stages() if name == "runtime"]
    return commands


def test_every_base_image_is_pinned_by_digest():
    """앞 스테이지를 잇는 `FROM runtime` 은 이미지가 아니다. 그 밖은 전부 digest 다."""
    names = {name for name, _ in _stages()}
    bases = [
        [w for w in commands[0][1:] if not w.startswith("--")][0]
        for _, commands in _stages()
    ]
    external = [b for b in bases if b not in names]
    assert external, "대조군 — FROM 을 하나도 읽지 못했다"
    assert all(PINNED.fullmatch(b) for b in external), external


def test_tools_come_from_pinned_images_not_from_pip():
    """uv 는 판·digest 가 붙은 공식 이미지에서 복사한다. `pip install uv` 는 판도 해시도 없었다."""
    commands = [c for _, cs in _stages() for c in cs]
    sources = [w.split("=", 1)[1] for c in commands if c[0].upper() == "COPY" for w in c if w.startswith("--from=")]
    names = {name for name, _ in _stages()}
    external = [s for s in sources if s not in names]
    assert external, "uv 를 이미지에서 복사해 오는 줄이 없다"
    assert all(PINNED.fullmatch(s) for s in external), external
    assert not any("pip" in c for c in commands if c[0].upper() == "RUN"), "RUN 이 pip 로 무언가를 설치한다"


def test_the_runtime_neither_starts_through_uv_nor_keeps_a_cache():
    """compose 의 api 는 읽기 전용 루트다 — `uv run` 은 캐시 디렉터리를 만들려다 죽는다. PATH 에 가상환경이 있다.
    캐시는 쓰지 않는다 — 이미지에 66 MB 로 구워지고 있었다. `test` 스테이지도 이 ENV 를 물려받는다."""
    commands = _runtime()
    (cmd,) = [c for c in commands if c[0].upper() == "CMD"]
    assert json.loads(" ".join(cmd[1:]))[0] != "uv", cmd
    env = [w for c in commands if c[0].upper() == "ENV" for w in c[1:]]
    assert "UV_NO_CACHE=1" in env, env
    assert not any(c[0].upper() == "USER" for _, cs in _stages() for c in cs), (
        "Dockerfile 에 USER 를 두면 test 스테이지의 uv sync 가 root 가 아니어서 실패한다 — compose 에서 정한다"
    )


def test_the_build_backend_is_pinned():
    """`uv.lock` 밖이라 판을 적지 않으면 빌드마다 PyPI 의 그 시점 최신이 들어온다."""
    requires = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["build-system"]["requires"]
    assert requires and all(re.fullmatch(r"[A-Za-z0-9_.-]+==[0-9][\w.]*", r) for r in requires), requires


def test_every_compose_image_is_pinned_by_digest():
    images = [
        line.split("image:", 1)[1].strip()
        for line in COMPOSE.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("image:")
    ]
    assert images, "대조군 — image: 를 하나도 읽지 못했다"
    assert all(PINNED.fullmatch(i) for i in images), images


def _api() -> dict[str, list[str]]:
    """compose `api` 의 키 → 값들(같은 줄의 값이나 아래 목록 항목). YAML 파서는 의존성이 아니다."""
    lines = COMPOSE.read_text(encoding="utf-8").splitlines()
    start = lines.index("  api:")
    keys: dict[str, list[str]] = {}
    current = None
    for line in lines[start + 1 :]:
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if not line.startswith("    "):
            break
        if not line.startswith("     "):
            current, _, value = text.partition(":")
            keys[current] = [value.strip().strip("\"'")] if value.strip() else []
        elif current and text.startswith("- "):
            keys[current].append(text[2:].strip().strip("\"'"))
    return keys


def test_api_runs_unprivileged_on_a_read_only_root():
    """비루트·읽기 전용 루트·capability 없음·권한 상승 없음. `/workspace` 를 가리지는 않는다 (D37)."""
    api = _api()
    assert "environment" in api and "volumes" in api, "대조군 — api 블록을 읽지 못했다"
    uid, _, gid = api["user"][0].partition(":")
    assert uid.isdigit() and int(uid) > 0 and gid.isdigit() and int(gid) > 0, api["user"]
    assert api["read_only"] == ["true"]
    assert "/tmp" in api["tmpfs"]
    assert api["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in api["security_opt"]
    assert not {"privileged", "cap_add", "env_file"} & set(api), sorted(api)
