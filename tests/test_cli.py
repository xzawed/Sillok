"""CLI 표면 검증. DB 가 필요 없다."""

from __future__ import annotations

import pytest

from sillok import cli


def test_redact_hides_password():
    out = cli._redact("postgresql://sillok:secret@127.0.0.1:5432/sillok")
    assert "secret" not in out
    assert out == "postgresql://sillok:***@127.0.0.1:5432/sillok"


def test_redact_leaves_passwordless_dsn_alone():
    assert cli._redact("postgresql://db:5432/sillok") == "postgresql://db:5432/sillok"


def test_unreachable_db_fails_fast_with_a_message(capsys, monkeypatch):
    """무한 대기 대신 exit 1 과 읽을 수 있는 메시지.

    D17 이 마이그레이션을 serve 기동 시 bind 전에 돌리므로, 여기서 멈추면
    서비스가 아무 말 없이 안 뜬 것처럼 보인다.
    """
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://sillok:secret@127.0.0.1:1/sillok"
    )
    assert cli.main(["migrate"]) == 1
    err = capsys.readouterr().err
    assert "DB 에 붙을 수 없다" in err
    assert "secret" not in err


def test_command_is_required(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main([])
    assert exc.value.code != 0
