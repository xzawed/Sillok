"""저장소 규약이 코드에서 지켜지는가. DB 가 필요 없다.

산문으로만 둔 규약은 다음 사람이 모르고 어긴다. 여기 있는 것은 **문서가 약속한 것**이고,
어기면 조용히 사고가 나는 부류다.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

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


# --- 복원 절차의 가드가 실제로 무는가 (D54) ---------------------------------

REPO = TESTS.parent
OPERATIONS = REPO / "docs" / "operations.md"

# `test` 이미지에는 `docs/` 가 없다 — compose 가 `./src` 와 `./tests` 만 마운트하고
# Dockerfile 도 문서를 굽지 않는다 (D22 가 그렇게 정했다). 그래서 이 파일을 읽는 검사는
# 컨테이너에서 skip 되고 **호스트 `uv run pytest -q` 에서 돈다.** 증거 6종이 둘 다 돌리므로
# 이 부류가 어디에서도 안 도는 일은 없다. 아래 대조군은 파일을 읽지 않아 양쪽에서 다 돈다.
needs_repo_docs = pytest.mark.skipif(
    not OPERATIONS.exists(),
    reason=f"{OPERATIONS} 가 없다 — test 이미지에는 docs/ 가 없다 (D22). 호스트에서 돈다.",
)


def _bash_blocks(markdown: str) -> list[str]:
    """```bash 펜스 안쪽만 돌려준다. 산문의 예시 문장을 명령으로 오해하지 않으려고."""
    return re.findall(r"```bash\r?\n(.*?)```", markdown, re.S)


def _truncate_is_chained(block: str) -> bool:
    """블록의 `TRUNCATE` 줄이 **전부** `&&` 로 시작하는가.

    **판정은 여기 하나뿐이다.** 아래 검사와 대조군이 같은 함수를 부른다 — 대조군이 규칙을
    베껴 쓰면 규칙이 두 벌이 되고, 진짜 판정이 느슨해져도 대조군은 계속 초록이다.
    """
    targets = [
        line.strip()
        for line in block.splitlines()
        if "TRUNCATE" in line and not line.strip().startswith("#")
    ]
    return bool(targets) and all(line.startswith("&&") for line in targets)


@needs_repo_docs
def test_restore_runbook_chains_its_guard_to_the_truncate():
    """`TRUNCATE` 는 **빈 덤프 가드에 이어져 있어야** 한다 (D54).

    `test -s` 를 따로 한 줄에 두면 그 종료 코드를 아무도 소비하지 않는다. 그러면 가드가
    있는 것처럼 보이는데 아무 일도 하지 않고, 0바이트 덤프에 `TRUNCATE` 가 그대로 돈다 —
    **`kb_events` 는 Git 에 원본이 없는 유일한 데이터다** (D11).

    2026-09-05 실측: 옛 블록을 0바이트 덤프에 대고 그대로 돌리니 `test -s` 가 `1` 을 냈는데도
    이벤트 셋이 0 이 됐다. **가드가 `1` 을 냈는데 아무도 그것을 보지 않았다** — 뒤의 둘
    (`TRUNCATE`·붓기)이 `0` 으로 끝나 전체가 성공처럼 보였다. 산문으로만 두면 다음 사람이 되돌린다.
    """
    text = OPERATIONS.read_text(encoding="utf-8")
    blocks = [b for b in _bash_blocks(text) if "TRUNCATE" in b]
    assert blocks, "operations.md 의 bash 블록에서 TRUNCATE 를 찾지 못했다 — 이 검사가 낡았다"

    for block in blocks:
        assert _truncate_is_chained(block), (
            "복원 블록의 TRUNCATE 가 가드에 이어져 있지 않다 — `&&` 로 시작해야 한다"
        )
        # 잇는 대상이 실제로 빈 덤프 가드여야 한다. `&&` 만 보면 아무거나 이어도 통과한다.
        assert "test -s" in block, "TRUNCATE 가 있는 블록에 `test -s` 가드가 없다"


# `DUMP=` 을 여는 모든 모양 — `export`·`readonly`·한 줄의 둘째 문장까지. 값은 `_word` 가 읽는다.
_DUMP_ASSIGN = re.compile(r"(?:^|[\s;&|(])(?:(?:export|readonly|local|declare(?:\s+-\w+)*)\s+)?DUMP=")
_DUMP_FILE = re.compile(r"kb_events[\w.-]*\.sql")
_REDIRECT = re.compile(r"(?<![0-9&])[<>]{1,2}\s*(\S+)")


def _word(text: str, start: int) -> int:
    """셸 낱말 하나의 끝. `$( … )`·`${ … }` 안의 따옴표는 바깥 낱말을 끝내지 않는다 — 덤프 자리가 그 모양이다."""
    depth, quote, i = 0, "", start
    while i < len(text):
        ch = text[i]
        if depth == 0 and quote and ch == quote:
            quote = ""
        elif depth == 0 and not quote and ch in "\"'":
            quote = ch
        elif text.startswith(("$(", "${"), i) and quote != "'":
            depth, i = depth + 1, i + 1
        elif depth and ch in ")}":
            depth -= 1
        elif depth == 0 and not quote and ch in " \t;&|":
            break
        i += 1
    return i


def _assignments(code: str) -> tuple[list[str], str]:
    """(DUMP 에 넣는 값들, 그것을 뺀 나머지)."""
    values, rest, last = [], [], 0
    for m in _DUMP_ASSIGN.finditer(code):
        end = _word(code, m.end())
        values.append(code[m.end() : end])
        rest.append(code[last : m.start()])
        last = end
    return values, " ".join(rest + [code[last:]])


def _outside_quotes(code: str) -> str:
    """`"$DUMP"` 는 표시로 남기고 나머지 따옴표 안은 지운다 — `-c "… '<name>'"` 의 `<` 는 리다이렉트가 아니다."""
    code = code.replace('"$DUMP"', "@DUMP@")
    return re.sub(r"\"[^\"]*\"|'[^']*'", "''", code)


def dump_problems(blocks: list[str], repo_name: str) -> list[str]:
    """덤프를 쓰고 읽는 자리가 **저장소 밖, 스택마다, 모든 절에서 같은 한 줄**인가 (D37, 2026-09-27).

    `api` 는 저장소 전체를 `/workspace` 로 읽고, 덤프에는 원장에서 이미 지운 행이 남을 수 있다.
    복원 절은 백업 절이 둔 자리를 같은 줄로 다시 정한다 — 둘이 갈라지면 가드가 `1` 을 내고 멈추거나, 남의 덤프를 붓는다.
    D66 의 복제 스택이 한 자리를 나눠 쓰면 한 스택의 백업이 다른 스택의 것을 덮는다.
    """
    problems: list[str] = []
    values: list[str] = []
    for block in blocks:
        for line in block.splitlines():
            code = re.sub(r"(^|\s)#.*$", "", line).strip()
            if not code:
                continue
            found, rest = _assignments(code)
            values += found
            if _DUMP_FILE.search(rest):
                problems.append(f"덤프 파일 이름을 변수 밖에서 쓴다: {code}")
            rest = _outside_quotes(rest)
            if not re.search(r"\bpg_dump\b|\bpsql\b|\btest\s+-s\b", rest):
                continue
            if re.search(r"\|(?!\|)|\btee\b", rest):
                problems.append(f"덤프를 파이프로 나른다: {code}")
            targets = _REDIRECT.findall(rest) + re.findall(r"\btest\s+-s\s+(\S+)", rest)
            problems += [f"`\"$DUMP\"` 밖을 읽거나 쓴다: {code}" for t in targets if t not in {"@DUMP@", "/dev/null"}]
    if len(values) < 3:
        problems.append(f"백업·복원·새 머신 세 절이 모두 `DUMP=` 로 자리를 정하지 않는다: {values}")
    if len(set(values)) > 1:
        problems.append(f"절마다 덤프 자리가 다르다: {sorted(set(values))}")
    for value in set(values):
        first = value.strip("\"'").removeprefix("$HOME/").split("/", 1)[0]
        if not value.startswith('"$HOME/') or first.lower() == repo_name.lower():
            problems.append(f"덤프 자리가 저장소 밖의 홈 아래가 아니다: {value}")
        if "COMPOSE_PROJECT_NAME" not in value:
            problems.append(f"덤프 자리가 스택마다 다르지 않다: {value}")
    return problems


def _operations_bash() -> list[str]:
    return _bash_blocks(OPERATIONS.read_text(encoding="utf-8"))


@needs_repo_docs
def test_the_event_dump_lives_outside_the_repository():
    assert dump_problems(_operations_bash(), REPO.name) == []


@needs_repo_docs
@pytest.mark.parametrize(
    "old, new",
    [
        ('> "$DUMP"', "> kb_events.sql"),
        ('test -s "$DUMP"', "test -s kb_events.sql"),
        ('< "$DUMP"', '<"$HOME/other.sql"'),
        ('< "$DUMP"', '< "$DUMP" \\\n  && cat kb_events.sql | psql'),
        ('> "$DUMP"', '| tee "$DUMP"'),
        ('mkdir -p "$(dirname "$DUMP")"', 'mkdir -p "$(dirname "$DUMP")"; export DUMP=kb_events.sql'),
        ('mkdir -p "$(dirname "$DUMP")"', "readonly DUMP=kb_events.sql"),
        ("${COMPOSE_PROJECT_NAME:-$(basename \"$PWD\")}", "Sillok"),
        ("${COMPOSE_PROJECT_NAME:-$(basename \"$PWD\")}", "backup"),
        ('"$HOME/sillok-backup/', '"kb/'),
    ],
)
def test_the_dump_check_bites(old, new):
    """대조군. 리뷰가 초록으로 통과시킨 모양들이다. 앞의 것만 바꾸므로 절끼리 갈라진 경우도 함께 본다."""
    text = OPERATIONS.read_text(encoding="utf-8")
    assert old in text, f"대조군의 앵커가 사라졌다: {old!r}"
    assert dump_problems(_bash_blocks(text.replace(old, new, 1)), REPO.name), (old, new)


def test_the_guard_check_would_catch_the_old_block():
    """대조군. **옛 블록을 넣으면 위 검사가 물어야 한다.**

    무는지 확인하지 않으면 위 검사가 통과하는 이유를 알 수 없다 — 이 저장소의 재발 부류다.
    """
    old_block = (
        "test -s kb_events.sql\n"
        'docker compose exec -T db psql -v ON_ERROR_STOP=1 -c "TRUNCATE kb_events;"\n'
    )
    # **위 검사와 같은 함수를 부른다.** 규칙을 여기 베껴 쓰면 대조군이 아니라 사본이 된다
    # (Grok 리뷰가 그렇게 지적했다 — 처음에는 판정을 손으로 다시 적었다).
    assert not _truncate_is_chained(old_block), "옛 블록이 통과한다 — 판정이 느슨해졌다"
    assert _truncate_is_chained(
        "test -s kb_events.sql \\\n"
        '  && docker compose exec -T db psql -c "TRUNCATE kb_events;"\n'
    ), "고친 모양이 걸린다 — 판정이 너무 조이다"
