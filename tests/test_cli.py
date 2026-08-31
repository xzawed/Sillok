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
        cli.main(["serve"])  # D8 의 명령이지만 3단계 전까지는 없다
    assert exc.value.code != 0
