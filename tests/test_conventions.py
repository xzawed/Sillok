"""저장소 규약이 코드에서 지켜지는가. DB 가 필요 없다.

산문으로만 둔 규약은 다음 사람이 모르고 어긴다. 여기 있는 것은 **문서가 약속한 것**이고,
어기면 조용히 사고가 나는 부류다.
"""

from __future__ import annotations

import re
from pathlib import Path

from sillok import service

TESTS = Path(__file__).resolve().parent

# D55. 검사는 제품과 같은 DB·같은 볼륨을 쓴다. 격리는 이름으로 한다.
TEST_PROJECT_PREFIX = "t_"

# `project` 값이 나타나는 네 모양. 하나만 보면 나머지로 새는 길이 남는다 —
# 처음에는 `PROJECT` 상수만 봤고, `_wipe(db, "t_step4")` 는 그 그물 밖이었다 (Grok 적대 리뷰).
PROJECT_SHAPES = (
    re.compile(r'^PROJECT\s*=\s*["\']([^"\']+)["\']', re.M),
    re.compile(r'["\']project["\']\s*:\s*["\']([^"\']+)["\']'),
    re.compile(r'_wipe\([^,)]+,\s*["\']([^"\']+)["\']'),
    re.compile(r"VALUES\s*\(\s*'([^']+)'", re.I),
)


def _db_capable() -> list[Path]:
    """DB 에 닿을 수 있는 검사 파일. **`dbcheck` 를 임포트해야 닿는다.**

    그래서 이 범위는 자동으로 따라온다 — 어떤 파일이 DB 검사가 되는 순간 그 임포트가 생기고,
    그 파일이 이 그물에 들어온다. 목록을 손으로 들고 있지 않는 이유다.
    """
    return [
        p
        for p in sorted(TESTS.glob("test_*.py"))
        # 자기 자신은 뺀다. 넣으면 이 파일의 **주석 속 예시**가 아래 대조군을 살려 두어,
        # 진짜 호출부가 사라져도 "그 모양이 걸린다" 가 참이 된다 (Grok 재검토).
        if p != Path(__file__).resolve() and "dbcheck" in p.read_text(encoding="utf-8")
    ]


def test_db_tests_only_touch_their_own_project():
    """DB 에 닿는 검사의 `project` 는 전부 `t_` 로 시작한다 (D55).

    같은 볼륨을 쓰므로 이 접두사가 유일한 격리다. 산문으로만 두면 다음 검사가
    `sillok` 을 쓰고, 그 순간 검사가 제품 데이터를 지운다.
    """
    offenders = []
    for path in _db_capable():
        body = path.read_text(encoding="utf-8")
        for shape in PROJECT_SHAPES:
            for m in shape.finditer(body):
                value = m.group(1)
                if value.startswith(TEST_PROJECT_PREFIX):
                    continue
                # D25 가 거절하는 값은 DB 에 닿을 수 없다 — 거절을 확인하는 검사의 재료다.
                # 규칙을 여기 베끼지 않고 **그 판정을 그대로 부른다.**
                try:
                    service.normalize_project(value)
                except service.ValidationFailed:
                    continue
                offenders.append(f"{path.name}: {value!r}")
    assert not offenders, (
        "DB 검사가 t_ 밖의 project 를 쓴다 — 같은 볼륨이라 제품 데이터를 건드린다 (D55): "
        + ", ".join(sorted(set(offenders)))
    )


def test_the_net_actually_covers_the_db_tests():
    """대조군 하나. 범위가 비면 위 검사는 언제나 통과한다."""
    files = _db_capable()
    assert len(files) >= 5, f"DB 검사 파일을 {len(files)}개만 찾았다 — 범위가 낡았다"


def test_every_shape_finds_something():
    """대조군 둘. **모양 하나가 아무것도 못 찾으면 그 갈래는 죽은 그물이다.**

    정규식이 낡아도 검사는 초록이므로, 각 모양이 실제로 걸리는지 따로 본다.
    """
    bodies = [p.read_text(encoding="utf-8") for p in _db_capable()]
    for shape in PROJECT_SHAPES:
        hits = sum(len(shape.findall(b)) for b in bodies)
        assert hits > 0, f"이 모양이 하나도 걸리지 않는다 — 그물이 낡았다: {shape.pattern}"
