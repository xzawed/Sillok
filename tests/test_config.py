"""D16 환경변수 계약 검증. DB 가 필요 없다."""

from __future__ import annotations

import pytest

from sillok import config


def test_defaults_match_the_adr():
    cfg = config.load({})
    assert cfg.database_url == "postgresql://sillok:sillok@127.0.0.1:5432/sillok"
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 8080
    assert cfg.workspace == "."
    assert cfg.bearer_token == ""
    assert cfg.openai_api_key == ""


def test_empty_key_means_keyword_only():
    """D2: 키가 없으면 embedding 은 NULL 이고 tsv 만 쓴다."""
    assert config.load({}).embeddings_enabled is False
    assert config.load({"OPENAI_API_KEY": "sk-test"}).embeddings_enabled is True


def test_empty_bearer_means_local_no_auth():
    """D7: 빈 값이면 무인증. 값이 있으면 Bearer 를 요구한다."""
    assert config.load({}).auth_required is False
    assert config.load({"SILLOK_BEARER_TOKEN": "t"}).auth_required is True


def test_compose_style_overrides():
    cfg = config.load(
        {
            "DATABASE_URL": "postgresql://sillok:sillok@db:5432/sillok",
            "SILLOK_HOST": "0.0.0.0",
            "SILLOK_WORKSPACE": "/workspace",
        }
    )
    assert cfg.database_url.endswith("@db:5432/sillok")
    assert cfg.host == "0.0.0.0"
    assert cfg.workspace == "/workspace"
    # 덮지 않은 값은 기본값을 유지한다.
    assert cfg.port == 8080


@pytest.mark.parametrize("raw", ["", "0", "70000", "eighty-eighty"])
def test_bad_port_is_rejected_or_defaulted(raw):
    if raw == "":
        # 빈 값은 "설정하지 않음" 으로 본다.
        assert config.load({"SILLOK_PORT": raw}).port == 8080
        return
    with pytest.raises(ValueError):
        config.load({"SILLOK_PORT": raw})
