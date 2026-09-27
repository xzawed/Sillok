"""이미지 입력 고정과 `api` 컨테이너 권한 (D18, 2026-09-27 감사 F110·F111).

값(digest·판)은 원천에만 있다 — 여기서는 **모양**만 잠근다. 떠 있는 태그, 판 없는 설치, root 로 도는 api 로
조용히 되돌아가지 않게 한다. Dockerfile·docker-compose.yml 은 이미지 안에 없으므로 그 둘의 검사는 호스트에서 돈다.

**판정은 텍스트를 받는 함수 하나씩이다.** 진짜 파일에는 빈 목록을, 대조군의 망가진 텍스트에는 무언가를 내야 한다 —
첫 판은 파일에 묶인 판정이라 대조군을 둘 수 없었고, 리뷰가 그 틈으로 16가지 되돌림을 초록으로 통과시켰다.
"""

from __future__ import annotations

import json
import re
import shlex
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"
COMPOSE = ROOT / "docker-compose.yml"

needs_dockerfile = pytest.mark.skipif(
    not DOCKERFILE.exists(), reason="이미지 안에는 Dockerfile 이 없다 — 호스트에서 돈다"
)
needs_compose = pytest.mark.skipif(
    not COMPOSE.exists(), reason="이미지 안에는 docker-compose.yml 이 없다 — 호스트에서 돈다"
)

# `이름:태그@sha256:…` — 태그는 사람이 읽으라고 남기고, 받는 것은 digest 가 정한다.
PINNED = re.compile(r"[\w./-]+:[\w.-]+@sha256:[0-9a-f]{64}")
INSTRUCTIONS = frozenset(
    "FROM RUN CMD LABEL EXPOSE ENV ADD COPY ENTRYPOINT VOLUME USER WORKDIR ARG ONBUILD STOPSIGNAL "
    "HEALTHCHECK SHELL MAINTAINER".split()
)
# 판도 해시도 없이 무언가를 내려받아 설치하는 길. `pipefail` 같은 낱말은 걸리지 않게 경계를 둔다.
# OS 패키지도 판 없이 들어오므로 막는다 — 필요해지면 고정하는 법과 함께 여기를 고친다.
FETCHING = re.compile(
    r"\bpip[0-9.]*\b|\bpipx\b|\bcurl\b|\bwget\b|<<|\buvx\b|\buv\s+(?:tool|pip|python)\s+install\b"
    r"|--python-preference\b|\bapt(?:-get)?\s+install\b|\bapk\s+add\b"
)


# --- Dockerfile ------------------------------------------------------------------


def _commands(text: str) -> list[list[str]]:
    """주석을 버리고 줄 이음(`\\`)을 합친 명령들. 명령은 낱말 목록이다."""
    commands: list[list[str]] = []
    buffer = ""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.endswith("\\"):
            buffer += stripped[:-1] + " "
            continue
        commands.append((buffer + stripped).split())
        buffer = ""
    return commands


def _exec_words(command: list[str]) -> list[str]:
    """CMD·ENTRYPOINT 의 낱말. JSON 배열이면 원소를 다시 공백으로 쪼갠다 — `sh -c "uv run …"` 도 본다."""
    rest = " ".join(command[1:])
    try:
        items = json.loads(rest)
    except json.JSONDecodeError:
        items = command[1:]
    return [word for item in items for word in str(item).split()]


def _pinned_or_stage(source: str, defined: set[str]) -> bool:
    return source in defined or bool(PINNED.fullmatch(source))


def dockerfile_problems(text: str) -> list[str]:
    problems: list[str] = []
    # `# syntax=` 는 주석이 아니라 BuildKit 이 받아 오는 프런트엔드다
    problems += [
        f"digest 없는 syntax 프런트엔드: {m.group(1)}"
        for m in re.finditer(r"(?im)^\s*#\s*syntax\s*=\s*(\S+)", text)
        if not PINNED.fullmatch(m.group(1))
    ]
    commands = _commands(text)
    problems += [f"알 수 없는 명령(heredoc 본문?): {c[0]}" for c in commands if c[0].upper() not in INSTRUCTIONS]
    defined: set[str] = set()  # **앞에서** 정의된 스테이지 이름만 내부다 — `FROM debian AS debian` 은 이미지다
    stage = ""
    env: dict[str, dict[str, str]] = {}
    execs: dict[str, list[list[str]]] = {}
    compiled_src = False
    for c in commands:
        op = c[0].upper()
        if op == "FROM":
            args = [w for w in c[1:] if not w.startswith("--")]
            base = args[0]
            if base not in defined and ("$" in base or not PINNED.fullmatch(base)):
                problems.append(f"digest 없는 베이스: {base}")
            stage = args[2] if len(args) >= 3 and args[1].upper() == "AS" else base
            # 앞 스테이지에서 이어받는 것을 따라간다 — default 는 runtime 의 ENV 를 물려받는다
            env[stage] = dict(env.get(base, {}))
            execs[stage] = list(execs.get(base, []))
            defined.add(stage)
        elif op in {"COPY", "ADD"}:
            for w in c[1:]:
                if w.startswith("--from=") and not _pinned_or_stage(w.split("=", 1)[1], defined):
                    problems.append(f"digest 없는 복사 원천: {w}")
            if op == "ADD" and any(re.match(r"https?://|git@", w) for w in c[1:]):
                problems.append(f"ADD 가 원격을 받는다: {' '.join(c)}")
        elif op == "RUN":
            joined = " ".join(c[1:])
            # `--mount=type=bind,from=…` 도 이미지를 받아 온다 — uv 문서가 보여 주는 모양이다
            for option in (w for w in c[1:] if w.startswith("--mount=")):
                for part in option.removeprefix("--mount=").split(","):
                    key, _, value = part.partition("=")
                    if key == "from" and not _pinned_or_stage(value, defined):
                        problems.append(f"digest 없는 마운트 원천: {option}")
            if FETCHING.search(joined):
                problems.append(f"RUN 이 판 없이 내려받는다: {joined}")
            # 잠금을 벗어난 해석은 판을 고정하지 않는다 — `uv sync` 는 늘 잠금 그대로다 (D18)
            for step in re.split(r"&&|\|\||;", joined):
                if re.search(r"\buv\s+sync\b", step) and not re.search(r"--frozen\b|--locked\b", step):
                    problems.append(f"uv sync 가 잠금을 벗어날 수 있다: {step.strip()}")
        elif op == "USER":
            problems.append("Dockerfile 의 USER — test 스테이지의 uv sync 가 실패한다(실측). compose 가 정한다")
        elif op == "ENV":
            words = shlex.split(" ".join(c[1:]))
            pairs = [w.split("=", 1) for w in words] if all("=" in w for w in words) else [[words[0], " ".join(words[1:])]]
            env[stage].update(dict(pairs))
        if op == "RUN" and stage == "runtime" and re.search(r"\bcompileall\b.*\bsrc\b", " ".join(c[1:])):
            compiled_src = True
        elif op in {"CMD", "ENTRYPOINT"}:
            execs[stage] = [e for e in execs[stage] if e[0].upper() != op] + [c]
    if "runtime" not in env:
        return problems + ["runtime 스테이지가 없다"]
    # 앱 자신은 편집 설치라 UV_COMPILE_BYTECODE 가 닿지 않는다 — /app/src 에 .pyc 가 0 이었다(리뷰 실측)
    if not compiled_src:
        problems.append("runtime 이 src 의 바이트코드를 굽지 않는다")
    # `docker build .` 은 마지막 스테이지를 굽는다 — test 로 끝나면 pytest 를 실은 이미지가 나온다 (D22)
    last = [c for c in commands if c[0].upper() == "FROM"][-1]
    last_args = [w for w in last[1:] if not w.startswith("--")]
    if last_args[0] != "runtime" or (len(last_args) >= 3 and last_args[2] == "test"):
        problems.append(f"마지막 스테이지가 runtime 을 잇지 않는다: {' '.join(last)}")
    for name in ("runtime", "default"):
        if name not in env:
            continue
        for key in ("UV_NO_CACHE", "UV_COMPILE_BYTECODE"):
            if env[name].get(key) != "1":
                problems.append(f"{name} 의 {key} 가 1 이 아니다")
        for c in execs[name]:
            if any(w == "uv" or w.endswith("/uv") for w in _exec_words(c)):
                problems.append(f"{name} 이 uv 를 거쳐 뜬다: {' '.join(c)}")
    return problems


@needs_dockerfile
def test_the_dockerfile_pins_its_inputs_and_starts_without_uv():
    assert dockerfile_problems(DOCKERFILE.read_text(encoding="utf-8")) == []


@needs_dockerfile
@pytest.mark.parametrize(
    "old, new",
    [
        ("@sha256:", "@sha256:x"),  # 베이스와 uv 가 모두 걸린다 — 아래 둘이 각각을 본다
        ("FROM python:3.12-slim@", "FROM ${BASE}@"),
        ("COPY --from=ghcr.io/astral-sh/uv:0.12.13@sha256:", "COPY --from=ghcr.io/astral-sh/uv:0.12.13@sha256:0"),
        ('CMD ["sillok", "serve"]', 'CMD ["uv", "run", "--no-sync", "sillok", "serve"]'),
        ('CMD ["sillok", "serve"]', 'CMD ["sh", "-c", "uv run sillok serve"]'),
        ('CMD ["sillok", "serve"]', 'ENTRYPOINT ["/bin/uv", "run"]\nCMD ["sillok", "serve"]'),
        ("    UV_NO_CACHE=1 \\", "    UV_NO_CACHE=0 \\"),
        ("    UV_COMPILE_BYTECODE=1 \\", ""),
        ('CMD ["sillok", "serve"]', 'CMD ["sillok", "serve"]\nENV UV_NO_CACHE=0'),
        ('CMD ["sillok", "serve"]', 'USER 10001\nCMD ["sillok", "serve"]'),
        ("WORKDIR /app", "WORKDIR /app\nRUN pip3 install uv"),
        ("WORKDIR /app", "WORKDIR /app\nRUN /usr/local/bin/pip install uv"),
        ("WORKDIR /app", "WORKDIR /app\nRUN curl -LsSf https://astral.sh/uv/install.sh | sh"),
        ("WORKDIR /app", "WORKDIR /app\nRUN <<EOF\npip install uv\nEOF"),
        ("WORKDIR /app", "WORKDIR /app\nADD https://example.invalid/uv.tar.gz /tmp/"),
        ("FROM runtime AS default", "FROM runtime AS default\nCMD uv run sillok serve"),
        ("FROM runtime AS default", ""),
        ("# Sillok api", "# syntax=docker/dockerfile:1\n# Sillok api"),
        ("RUN uv sync --frozen --no-dev", "RUN --mount=from=ghcr.io/astral-sh/uv:latest,source=/uv,target=/bin/uv uv sync --frozen --no-dev"),
        ("RUN uv sync --frozen --no-dev", "RUN uv sync --no-dev"),
        ("RUN python -m compileall -q src", ""),
        ("WORKDIR /app", "WORKDIR /app\nRUN apt-get update && apt-get install -y gcc"),
        ("WORKDIR /app", "WORKDIR /app\nRUN uvx ruff --version"),
        ("WORKDIR /app", "WORKDIR /app\nRUN uv tool install ruff"),
        ("RUN uv sync --frozen --no-dev", "RUN uv sync --frozen --no-dev --python-preference only-managed"),
        ('CMD ["sillok", "serve"]', 'ENV UV_NO_CACHE=0 X="a b"\nCMD ["sillok", "serve"]'),
    ],
)
def test_the_dockerfile_check_bites(old, new):
    """대조군. 진짜 Dockerfile 에서 한 곳만 되돌려도 판정이 무언가를 내야 한다. 앵커가 없으면 대조군이 낡은 것이다."""
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert old in text, f"대조군의 앵커가 사라졌다: {old!r}"
    assert dockerfile_problems(text.replace(old, new, 1)), (old, new)


@needs_compose
def test_the_list_form_of_command_is_read_too():
    """거짓 양성 대조군. 목록 모양의 command 는 흐름 모양과 같은 뜻이다 — 모양 때문에 붉어지면 안 된다."""
    text = COMPOSE.read_text(encoding="utf-8").replace('    command: ["sillok", "serve"]', "    command:\n      - sillok\n      - serve")
    assert compose_problems(text) == []


@needs_compose
def test_the_name_of_a_built_image_is_not_a_pull():
    """거짓 양성 대조군. `build:` 옆의 `image:` 는 구운 이미지의 이름이지 받아 오는 태그가 아니다."""
    text = COMPOSE.read_text(encoding="utf-8").replace("    build:\n      context: .", "    image: sillok-api:local\n    build:\n      context: .", 1)
    assert "sillok-api:local" in text
    assert compose_problems(text) == []


@needs_dockerfile
@pytest.mark.parametrize(
    "addition",
    [
        "RUN set -o pipefail && echo ok",
        'HEALTHCHECK CMD ["python", "-c", "print(1)"]',
        'LABEL org.opencontainers.image.title="sillok"',
        "# pip 는 쓰지 않는다 — uv 는 이미지에서 복사한다",
        'ENV GREETING="a b" UV_NO_CACHE=1',
    ],
)
def test_the_dockerfile_check_leaves_ordinary_lines_alone(addition):
    """거짓 양성 대조군. 판정이 낱말 경계 없이 문자열을 찾으면 여기서 붉어진다."""
    text = DOCKERFILE.read_text(encoding="utf-8").replace('CMD ["sillok", "serve"]', addition + '\nCMD ["sillok", "serve"]', 1)
    assert dockerfile_problems(text) == []


def test_a_stage_alias_does_not_hide_an_unpinned_image():
    """`FROM debian AS debian` 의 debian 은 이미지다 — 이름이 스테이지 목록에 있다고 내부로 보면 BuildKit 이 latest 를 받는다(실측)."""
    assert dockerfile_problems("FROM debian AS debian\nFROM debian AS runtime\nENV UV_NO_CACHE=1 UV_COMPILE_BYTECODE=1\n")
    assert dockerfile_problems(
        "FROM busybox AS busybox\nFROM python:3.12-slim@sha256:" + "0" * 64 + " AS runtime\n"
        "ENV UV_NO_CACHE=1 UV_COMPILE_BYTECODE=1\nCOPY --from=busybox /bin/sh /x\n"
    )


# --- pyproject · uv.lock -----------------------------------------------------------


def test_the_build_backend_and_its_build_deps_are_pinned_and_locked():
    """빌드 백엔드는 `uv.lock` 밖이다. hatchling 과 그것이 끌어오는 것까지 `==` 로 적고, `uv lock` 이 옮겨 적은 사본이
    같아야 한다 — `uv sync --frozen` 은 잠금의 사본을 쓰므로 pyproject 만 고치면 옛 판이 조용히 쓰였다(실측)."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requires = project["build-system"]["requires"]
    constraints = project["tool"]["uv"]["build-constraint-dependencies"]
    pinned = re.compile(r"[A-Za-z0-9_.-]+==[0-9][\w.]*")
    assert requires and all(pinned.fullmatch(r) for r in requires), requires
    assert constraints and all(pinned.fullmatch(c) for c in constraints), constraints
    locked = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))["manifest"]["build-constraints"]
    assert sorted(f"{c['name']}{c['specifier']}" for c in locked) == sorted(constraints), "`uv lock` 을 다시 돌린다"


# --- docker-compose.yml ------------------------------------------------------------


def _key(raw: str) -> str:
    """`"privileged": true` 와 `privileged : true` 는 compose 에게 같은 키다(리뷰 실측)."""
    return raw.strip().strip("\"'").strip()


def _services(text: str) -> dict[str, dict[str, list[str]]]:
    """서비스 → (키 → 값들: 같은 줄의 값이나 아래 목록 항목). YAML 파서는 의존성이 아니다."""
    services: dict[str, dict[str, list[str]]] = {}
    inside, name, current = False, None, None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0:
            inside, name = _key(stripped.partition(":")[0]) == "services", None
        elif inside and indent == 2:
            name, current = _key(stripped.partition(":")[0]), None
            services[name] = {}
        elif inside and name and indent == 4:
            key, _, value = stripped.partition(":")
            current = _key(key)
            services[name][current] = [value.strip().strip("\"'")] if value.strip() else []
        elif inside and name and current and stripped.startswith("- "):
            services[name][current].append(stripped[2:].strip().strip("\"'"))
    return services


# api 가 가져도 되는 키. **허용 목록이다** — 금지 목록은 `volumes_from`·`cgroup_parent` 같은 새 길을 놓쳤다(리뷰 실측).
_API_KEYS = frozenset(
    {"build", "image", "depends_on", "command", "user", "read_only", "tmpfs", "cap_drop", "security_opt",
     "environment", "ports", "volumes", "healthcheck", "restart"}
)


def compose_problems(text: str) -> list[str]:
    problems: list[str] = []
    body = [line for line in text.splitlines() if not line.strip().startswith("#")]
    # 병합 키와 extends 는 다른 곳의 설정을 이 블록에 들인다 — 블록만 봐서는 안 보인다
    problems += [f"병합·상속: {line.strip()}" for line in body if _key(line).startswith(("<<", "extends"))]
    services = _services(text)
    # `build:` 가 있는 서비스의 image 는 받아 오는 것이 아니라 구운 것의 이름이다
    pulled = [s["image"][0] for s in services.values() if s.get("image") and "build" not in s]
    if not pulled:
        problems.append("받아 오는 image: 를 하나도 읽지 못했다")
    problems += [f"digest 없는 이미지: {i}" for i in pulled if not PINNED.fullmatch(i)]
    api = services.get("api", {})
    if "environment" not in api:
        return problems + ["api 블록을 읽지 못했다"]
    problems += [f"api 에 허용 목록 밖의 키: {k}" for k in sorted(set(api) - _API_KEYS)]
    # 흐름 모양(`["sillok", "serve"]`)도 목록 모양(`- sillok`)도 같은 command 다
    raw = api.get("command", [])
    command = json.loads(raw[0]) if len(raw) == 1 and raw[0].startswith("[") else raw
    if not command or any(w == "uv" or w.endswith("/uv") for item in command for w in str(item).split()):
        problems.append(f"api 의 command 가 없거나 uv 를 거친다: {command}")
    uid, _, gid = (api.get("user") or [""])[0].partition(":")
    if not (uid.isdigit() and int(uid) > 0 and gid.isdigit() and int(gid) > 0):
        problems.append(f"api 가 비루트 숫자 uid:gid 로 돌지 않는다: {api.get('user')}")
    if api.get("read_only") != ["true"]:
        problems.append("api 의 루트가 읽기 전용이 아니다")
    if "/tmp" not in api.get("tmpfs", []):
        problems.append("api 에 /tmp tmpfs 가 없다")
    if api.get("cap_drop") != ["ALL"]:
        problems.append("api 가 capability 를 전부 버리지 않는다")
    if api.get("security_opt") != ["no-new-privileges:true"]:
        problems.append(f"api 의 security_opt 가 no-new-privileges 하나가 아니다: {api.get('security_opt')}")
    if api.get("volumes") != [".:/workspace:ro"]:
        problems.append(f"api 의 마운트가 읽기 전용 나무 하나가 아니다: {api.get('volumes')}")
    return problems


@needs_compose
def test_compose_pins_images_and_runs_api_unprivileged():
    """비루트·읽기 전용 루트·capability 없음·권한 상승 없음. `/workspace` 를 가리지는 않는다 (D37)."""
    assert compose_problems(COMPOSE.read_text(encoding="utf-8")) == []


@needs_compose
@pytest.mark.parametrize(
    "old, new",
    [
        ("pgvector/pgvector:pg16@sha256:", "pgvector/pgvector:pg16@sha256:x"),
        ('    user: "10001:10001"', '    user: "0:0"'),
        ('    user: "10001:10001"', ""),
        ("    read_only: true", "    read_only: false"),
        ("    cap_drop:\n      - ALL", ""),
        ("    cap_drop:\n      - ALL", "    cap_drop:\n      - ALL\n    cap_add:\n      - SYS_ADMIN"),
        ("      - no-new-privileges:true", "      - no-new-privileges:true\n      - seccomp:unconfined"),
        ("      - no-new-privileges:true", "      - no-new-privileges:false"),
        ('    command: ["sillok", "serve"]', '    command: ["uv", "run", "--no-sync", "sillok", "serve"]'),
        ('    command: ["sillok", "serve"]', ""),
        ("      - .:/workspace:ro", "      - .:/workspace"),
        ("      - .:/workspace:ro", "      - .:/workspace:ro\n      - /var/run/docker.sock:/var/run/docker.sock"),
        ('    user: "10001:10001"', '    user: "10001:10001"\n    privileged: true'),
        ('    user: "10001:10001"', '    user: "10001:10001"\n    pid: host'),
        ('    user: "10001:10001"', '    user: "10001:10001"\n    <<: *priv'),
        ('    user: "10001:10001"', '    user: "10001:10001"\n    extends: {file: x.yml, service: y}'),
        ('    user: "10001:10001"', '    user: "10001:10001"\n    env_file: .env'),
        ('    user: "10001:10001"', '    user: "10001:10001"\n    entrypoint: ["uv", "run"]'),
        ('    command: ["sillok", "serve"]', "    command:\n      - uv\n      - run"),
        ('    user: "10001:10001"', '    user: "10001:10001"\n    privileged : true'),
        ('    user: "10001:10001"', '    user: "10001:10001"\n    "privileged": true'),
        ('    user: "10001:10001"', '    user: "10001:10001"\n    volumes_from:\n      - db'),
        ('    user: "10001:10001"', '    user: "10001:10001"\n    cgroup_parent: host'),
    ],
)
def test_the_compose_check_bites(old, new):
    """대조군. 리뷰가 초록으로 통과시킨 되돌림들이다 (병합 키·extends 는 `docker compose config` 로 privileged 가 됐다)."""
    text = COMPOSE.read_text(encoding="utf-8")
    assert old in text, f"대조군의 앵커가 사라졌다: {old!r}"
    assert compose_problems(text.replace(old, new, 1)), (old, new)
