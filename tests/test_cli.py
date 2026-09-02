"""CLI 표면 검증. DB 가 필요 없다."""

from __future__ import annotations

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
