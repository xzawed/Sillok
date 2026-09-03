"""CLI 표면 검증. DB 가 필요 없다."""

from __future__ import annotations

import subprocess
import sys

import pytest

from sillok import cli


def test_unreachable_db_fails_fast_with_a_message(capsys, monkeypatch):
    """무한 대기 대신 exit 1 과 읽을 수 있는 메시지.

    D17 이 마이그레이션을 serve 기동 시 bind 전에 돌리므로, 여기서 멈추면
    서비스가 아무 말 없이 안 뜬 것처럼 보인다.
    """
    monkeypatch.setenv("DATABASE_URL", "postgresql://sillok:secret@127.0.0.1:1/sillok")
    assert cli.main(["migrate"]) == 1
    err = capsys.readouterr().err
    assert "DB 에 붙을 수 없다" in err
    assert "secret" not in err


def test_cli_does_not_import_the_driver():
    """D19: CLI 는 인자를 읽고 러너를 부를 뿐이다.

    psycopg 를 CLI 가 직접 알면 다음 명령(ingest)이 같은 자리에 SQL 을 놓기 쉬워진다.
    """
    assert not hasattr(cli, "psycopg")


def test_command_is_required():
    with pytest.raises(SystemExit) as exc:
        cli.main([])
    assert exc.value.code != 0


def test_unknown_command_is_rejected():
    with pytest.raises(SystemExit) as exc:
        cli.main(["reindex"])  # D19 의 인자 목록에 없다. 편의 명령을 발명하지 않는다
    assert exc.value.code != 0


def test_ingest_refuses_a_different_workspace(capsys, monkeypatch, tmp_path):
    """D37: ingest 와 get_file 은 같은 뿌리를 봐야 한다.

    저쪽 나무를 색인해 두면 `get_file` 은 **이 나무**를 저쪽의 path 로 연다 —
    같은 경로에 다른 내용이 있으면 조용히 남의 파일을 돌려준다.
    거절은 CLI 에서 끝난다 (0 이 아닌 종료 코드 + 사람이 읽는 문구). DB 에 닿지 않는다.
    """
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.setenv("SILLOK_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", "postgresql://sillok:secret@127.0.0.1:1/sillok")

    assert cli.main(["ingest", "--project", "sillok", "--workspace", str(other)]) == 1
    err = capsys.readouterr().err
    assert "SILLOK_WORKSPACE" in err
    assert "secret" not in err


def test_ingest_accepts_the_same_tree_spelled_differently(monkeypatch, tmp_path):
    """`.` 과 절대 경로가 같은 곳을 가리키면 통과한다 — 거절은 문자열이 아니라 경로를 본다.

    거절되지 않았다는 것은 **DB 까지 갔다**는 뜻이고, 죽은 DSN 이라 거기서 끝난다.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SILLOK_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", "postgresql://sillok:secret@127.0.0.1:1/sillok")

    with pytest.raises(Exception) as exc:
        cli.main(["ingest", "--project", "sillok", "--workspace", "."])
    assert "SILLOK_WORKSPACE" not in str(exc.value)


def test_registered_commands_are_exactly_the_implemented_ones():
    """구현되지 않은 명령을 파서에 미리 만들어 두지 않는다.

    이 검사가 없으면 serve 처럼 새 명령이 생겼을 때 옛 테스트가 실제로
    그 명령을 실행해 버린다 — 실제로 그렇게 매달렸다.
    """
    parser = cli._build_parser()
    actions = [a for a in parser._actions if a.dest == "command"]
    assert sorted(actions[0].choices) == ["ingest", "mcp", "migrate", "serve"]


# --- stdio (D45). `sillok mcp` 는 지금까지 검사가 하나도 없었다 ----------------


def test_mcp_reports_a_dead_db_on_stderr_and_leaves_stdout_clean(capfd, monkeypatch):
    """**stdout 은 JSON-RPC 채널이다** (D45). 한 글자라도 새면 클라이언트가 파싱에 실패한다.

    D17 과 같은 이유로 마이그레이션을 먼저 돌리므로 붙지 못하면 여기서 멈춘다.
    그때 보고가 stdout 으로 가면 그 자체가 계약 위반이다 — 그 불변식이 안 잠겨 있었다.
    """
    monkeypatch.setenv("DATABASE_URL", "postgresql://sillok:secret@127.0.0.1:1/sillok")
    assert cli.main(["mcp"]) == 1
    # `capfd` 다 — 파이썬의 print 뿐 아니라 임포트 중 fd 1 로 나가는 것까지 본다 (Grok 재검토).
    captured = capfd.readouterr()
    assert captured.out == ""  # 프로토콜 채널은 비어 있어야 한다
    assert "DB 에 붙을 수 없다" in captured.err
    assert "secret" not in captured.err  # 비밀은 어느 스트림에도 가지 않는다 (D21)


def test_mcp_does_not_import_the_server_until_it_runs():
    """`mcp` 의 무거운 임포트는 그 분기 안에 있다 (cli.py).

    모듈 최상단으로 올리면 `sillok migrate` 하나가 MCP SDK 전체를 끌고 온다.

    **이름 유무가 아니라 `sys.modules` 를 본다.** `from .mcp_server import build` 처럼
    별칭으로 올리면 속성 검사는 통과한다 (Grok 재검토). 새 프로세스에서 확인해야
    이 파일의 다른 검사가 이미 올려 둔 모듈에 속지 않는다.
    """
    probe = "import sillok.cli, sys; print(int(any(m.endswith('mcp_server') or m == 'anyio' for m in sys.modules)))"
    out = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert out == "0", f"cli 를 임포트하는 것만으로 MCP 쪽이 올라왔다: {out}"
