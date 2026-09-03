"""구운 이미지가 조용히 낡지 않는가 (D28이 예고한 자리). DB가 필요 없다.

`--profile test` 는 소스만 마운트하고 `.venv` 는 **이미지에 구워져 있다.**
의존성을 바꾸고 다시 굽지 않으면 검사는 옛 라이브러리로 돈다.

D28 이 만든 부분 완화는 **새 임포트가 생겼을 때만** 문다 — `ImportError` 로 시끄럽게 죽는다.
**버전 상향·전이 의존성·제거는 조용했다.** 그 셋을 여기서 막는다.

**방향은 설치 → 잠금이다.** 직접 선언한 것만 보면 `uv lock --upgrade` 가 전이 의존성만
올렸을 때 초록이고, `psycopg[binary]` 의 실체인 `psycopg-binary` 도 보이지 않는다
(Grok 적대 리뷰가 그 자리를 찍었다). 반대 방향(잠금 → 설치)은 검사하지 않는다 —
`pywin32`·`colorama` 처럼 이 플랫폼에 안 깔리는 것이 정상이기 때문이다.

**이 검사가 증명하지 못하는 것 하나.** 이것은 *지금 보이는 잠금 파일*과 *지금 깔린 것*이 같다는
말이다. 컨테이너에서 그 잠금 파일이 **작업 트리의 것**인 이유는 compose 가 마운트하기 때문이고,
그 마운트를 지우면 이미지 안의 잠금과 이미지 안의 venv 를 비교하게 되어 언제나 통과한다.
안에서는 그것을 알 수 없다 — 그래서 마운트는 `docker-compose.yml` 에 주석으로 묶어 두었다.
"""

from __future__ import annotations

import tomllib
from importlib.metadata import distributions
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "uv.lock"


def _canon(name: str) -> str:
    return name.lower().replace("_", "-").replace(".", "-")


def _locked() -> dict[str, set[str]]:
    """이름 → 버전 **집합**. uv 는 플랫폼마다 다른 버전을 잠글 수 있어 하나로 접지 않는다."""
    data = tomllib.loads(LOCK.read_text(encoding="utf-8"))
    out: dict[str, set[str]] = {}
    for package in data.get("package", []):
        out.setdefault(_canon(package["name"]), set()).add(package["version"])
    return out


def _installed() -> dict[str, str]:
    return {
        _canon(dist.metadata["Name"]): dist.version
        for dist in distributions()
        if dist.metadata["Name"]
    }


def test_the_lock_is_here_at_all():
    """**없으면 실패다. 건너뛰지 않는다.**

    건너뛰면 D28 이 만든 바로 그 실패 모드가 된다 — 아무것도 지키지 않으면서 초록이다.
    """
    assert LOCK.exists(), f"{LOCK} 이 없다 — compose 의 test 서비스 마운트를 확인한다 (D28)"


def test_the_two_sets_are_not_trivially_small():
    """대조군. 둘 중 하나가 비면 아래 검사는 언제나 통과한다."""
    assert len(_locked()) >= 20
    assert len(_installed()) >= 20


def test_everything_installed_is_locked_at_the_same_version():
    """설치된 것은 전부 잠금 파일에 있고 버전이 같아야 한다.

    **여기서 갈라지면 지금 돌고 있는 환경이 낡은 것이다.** 컨테이너면 다시 굽고,
    호스트면 `uv sync` 다. 갈라진 채로 통과하면 검사가 옛 라이브러리를 증명한다.

    잠금에서 빠진 채 설치돼 있는 것은 **지운 의존성이 이미지에 남아 있다**는 뜻이다.
    """
    locked = _locked()
    drift = []
    for name, installed in sorted(_installed().items()):
        if name not in locked:
            drift.append(f"{name} {installed}: 잠금 파일에 없다 (지운 의존성이 남아 있다)")
        elif installed not in locked[name]:
            drift.append(f"{name}: 설치 {installed} vs 잠금 {sorted(locked[name])}")
    assert not drift, (
        "의존성이 잠금 파일과 갈라졌다 — 이 환경은 낡았다 (D28). "
        "컨테이너면 `docker compose build test`, 호스트면 `uv sync`: " + ", ".join(drift)
    )
