"""구운 이미지가 조용히 낡지 않는가 (D28이 예고한 자리, 백로그 F15). DB가 필요 없다.

`--profile test` 는 소스만 마운트하고 `.venv` 는 **이미지에 구워져 있다.**
의존성을 바꾸고 다시 굽지 않으면 검사는 옛 라이브러리로 돈다.

D28 이 만든 부분 완화는 **새 임포트가 생겼을 때만** 문다 — `ImportError` 로 시끄럽게 죽는다.
**버전 상향과 제거는 조용하다.** 그 자리를 여기서 막는다.
"""

from __future__ import annotations

import tomllib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "uv.lock"
PROJECT = ROOT / "pyproject.toml"

pytestmark = pytest.mark.skipif(
    not LOCK.exists() or not PROJECT.exists(),
    reason=(
        "uv.lock / pyproject.toml 이 없다. 컨테이너에서 이 경로가 비면 마운트를 확인한다 —"
        " 없는 채로 통과하면 이 검사가 아무것도 지키지 않는다 (D28)."
    ),
)


def _locked() -> dict[str, str]:
    data = tomllib.loads(LOCK.read_text(encoding="utf-8"))
    return {p["name"].lower().replace("_", "-"): p["version"] for p in data.get("package", [])}


def _declared() -> set[str]:
    """이 프로젝트가 **직접** 선언한 것만 본다 (런타임 + dev)."""
    data = tomllib.loads(PROJECT.read_text(encoding="utf-8"))
    names: set[str] = set()
    specs = list(data["project"]["dependencies"])
    for group in data.get("dependency-groups", {}).values():
        specs.extend(group)
    for spec in specs:
        head = spec.split(">")[0].split("<")[0].split("=")[0].split("[")[0]
        names.add(head.strip().lower().replace("_", "-"))
    return names


def test_the_lock_covers_everything_we_declare():
    """대조군. 잠금 파일이 선언을 못 담으면 아래 검사가 아무것도 보지 않는다."""
    missing = sorted(_declared() - _locked().keys())
    assert not missing, f"uv.lock 에 없는 선언: {missing}"


def test_installed_versions_match_the_lock():
    """설치된 것이 잠금 파일과 같아야 한다.

    **여기서 갈라지면 지금 돌고 있는 환경이 낡은 것이다** — 컨테이너면 다시 굽고,
    호스트면 `uv sync` 다. 갈라진 채로 통과하면 검사가 옛 라이브러리를 증명한다.
    """
    locked = _locked()
    drift = []
    for name in sorted(_declared()):
        try:
            installed = version(name)
        except PackageNotFoundError:
            drift.append(f"{name}: 설치되지 않았다 (잠금 {locked[name]})")
            continue
        if installed != locked[name]:
            drift.append(f"{name}: 설치 {installed} vs 잠금 {locked[name]}")
    assert not drift, (
        "의존성이 잠금 파일과 갈라졌다 — 이 환경은 낡았다 (D28). "
        "컨테이너면 `docker compose build test`, 호스트면 `uv sync`: " + ", ".join(drift)
    )
