"""저장소 규약이 코드에서 지켜지는가. DB 가 필요 없다.

산문으로만 둔 규약은 다음 사람이 모르고 어긴다. 여기 있는 것은 **문서가 약속한 것**이고,
어기면 조용히 사고가 나는 부류다.
"""

from __future__ import annotations

import re
from pathlib import Path

TESTS = Path(__file__).resolve().parent

# D55. 검사는 제품과 같은 DB·같은 볼륨을 쓴다. 격리는 이름으로 한다.
TEST_PROJECT_PREFIX = "t_"


def test_db_tests_only_touch_their_own_project():
    """검사의 `project` 는 전부 `t_` 로 시작한다 (D55).

    같은 볼륨을 쓰므로 이 접두사가 유일한 격리다. 산문으로만 두면 다음 검사가
    `sillok` 을 쓰고, 그 순간 검사가 제품 데이터를 지운다.
    """
    offenders = []
    for path in sorted(TESTS.glob("test_*.py")):
        for m in re.finditer(r'^PROJECT\s*=\s*"([^"]*)"', path.read_text(encoding="utf-8"), re.M):
            if not m.group(1).startswith(TEST_PROJECT_PREFIX):
                offenders.append(f"{path.name}: {m.group(1)!r}")
    assert not offenders, (
        "검사가 t_ 밖의 project 를 쓴다 — 같은 볼륨이라 제품 데이터를 건드린다 (D55): "
        + ", ".join(offenders)
    )


def test_the_prefix_rule_actually_finds_something():
    """대조군. 정규식이 아무것도 못 찾으면 위 검사는 언제나 통과한다."""
    found = 0
    for path in TESTS.glob("test_*.py"):
        found += len(re.findall(r'^PROJECT\s*=\s*"', path.read_text(encoding="utf-8"), re.M))
    assert found >= 4, f"PROJECT 상수를 {found}개만 찾았다 — 정규식이 낡았다"
