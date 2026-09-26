"""빌드 컨텍스트는 허용 목록이다 (D56, 2026-09-27).

거부 목록이던 `.dockerignore` 는 뿌리 기준 패턴이라 `src/sillok/__pycache__` 의 호스트 바이트코드를 이미지에 실었고,
`.env.*`·원장 덤프 모양도 빠져 있었다 (감사 F029, 실측). 전부 막고 Dockerfile 이 COPY 하는 것만 되살린다.
이미지 안에는 Dockerfile·.dockerignore 가 없으므로 이 검사는 호스트에서 돈다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    not (ROOT / "Dockerfile").exists() or not (ROOT / ".dockerignore").exists(),
    reason="이미지 안에는 Dockerfile·.dockerignore 가 없다 — 호스트에서 돈다",
)


def _patterns() -> list[str]:
    lines = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]


def _copy_sources() -> list[str]:
    """`COPY --from=…` 은 다른 이미지에서 오므로 컨텍스트가 아니다."""
    sources: list[str] = []
    for line in (ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines():
        words = line.split()
        if not words or words[0].upper() != "COPY" or any(w.startswith("--from") for w in words):
            continue
        args = [w for w in words[1:] if not w.startswith("--")]
        sources.extend(a.removeprefix("./").rstrip("/") for a in args[:-1])
    return sources


def test_the_context_starts_by_excluding_everything():
    assert _patterns()[0] == "*"


def test_every_copy_source_is_let_back_in():
    """빠뜨리면 빌드가 크게 실패한다 — 조용히 새는 쪽이 아니다. 그래도 목록이 COPY 와 한 쌍이라는 것을 여기서 잠근다."""
    patterns = set(_patterns())
    sources = _copy_sources()
    assert sources, "Dockerfile 에서 COPY 원천을 하나도 찾지 못했다 — 파서가 낡았다"
    for source in sources:
        assert f"!{source}" in patterns, f"{source} 를 COPY 하는데 .dockerignore 가 되살리지 않는다"


@pytest.mark.parametrize(
    "pattern",
    ["**/__pycache__", "**/*.py[cod]", "**/.venv", "**/.env", "**/.env.*", "**/*.pem", "**/*.key",
     "**/kb_events*.sql*"],
)
def test_local_leftovers_stay_out_even_inside_what_is_let_back_in(pattern):
    """`!src` 가 되살린 나무 안에도 로컬 바이트코드·env·키·덤프가 있을 수 있다. `**/` 가 없으면 뿌리에서만 막는다."""
    assert pattern in _patterns()
