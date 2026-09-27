"""D16 환경변수 계약 검증. DB 가 필요 없다."""

from __future__ import annotations

from pathlib import Path

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


# --- D16 사본 대조 (.env.example) --------------------------------------------


def _env_example() -> dict[str, str]:
    """`.env.example` 의 `NAME=value` 를 읽는다. 주석과 빈 줄은 버린다."""
    path = Path(__file__).resolve().parents[1] / ".env.example"
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        out[name.strip()] = value.strip()
    return out


def test_env_example_holds_exactly_the_six_names():
    """D16 이 이름 여섯을 못 박았다. `.env.example` 은 그 사본이다 (ADR 의 복제 표).

    `POSTGRES_*` 셋은 compose 가 소유한다 — D16 의 여섯이 아니므로 여기서 뺀다.
    지금까지 이 대조를 하는 검사가 없었고, 실제로 그 파일의 한 대목이 낡아 있었다.
    """
    names = {k for k in _env_example() if not k.startswith("POSTGRES_")}
    assert names == {
        "DATABASE_URL",
        "SILLOK_HOST",
        "SILLOK_PORT",
        "SILLOK_WORKSPACE",
        "SILLOK_BEARER_TOKEN",
        "OPENAI_API_KEY",
    }


COMPOSE = Path(__file__).resolve().parents[1] / "docker-compose.yml"


def _api_block() -> list[str]:
    """compose 의 `api:` 서비스 블록. YAML 파서는 의존성이 아니므로 들여쓰기로 자른다."""
    lines = COMPOSE.read_text(encoding="utf-8").splitlines()
    start = lines.index("  api:")
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i] and not lines[i].startswith("    ")
         and not lines[i].lstrip().startswith("#")),
        len(lines),
    )
    return lines[start + 1 : end]


@pytest.mark.skipif(not COMPOSE.exists(), reason="test 컨테이너에는 docker-compose.yml 이 없다 — 호스트에서 돈다")
def test_api_takes_exactly_the_six_names_and_no_env_file():
    """D16. 표 밖의 변수(`PGHOSTADDR`·`OPENAI_BASE_URL` …)를 api 에서 막는 것은 `environment:` 목록이다.
    `env_file` 을 붙이면 `.env` 의 모든 이름이 들어와도 검사는 초록이었다 (2026-09-27 리뷰)."""
    block = _api_block()
    assert not any(line.strip().startswith("env_file") for line in block)
    start = block.index("    environment:")
    names = set()
    for line in block[start + 1 :]:
        if line.strip().startswith("#") or not line.strip():
            continue
        if not line.startswith("      "):
            break
        names.add(line.strip().split(":", 1)[0])
    assert names == {k for k in _env_example() if not k.startswith("POSTGRES_")}


def test_env_example_defaults_match_config():
    """사본의 기본값이 구현과 갈라지면 안 된다. 갈라지면 **사본이 틀린 것**이다 (D16)."""
    env = _env_example()
    assert env["DATABASE_URL"] == config.DEFAULT_DATABASE_URL
    assert env["SILLOK_HOST"] == config.DEFAULT_HOST
    assert env["SILLOK_PORT"] == str(config.DEFAULT_PORT)
    assert env["SILLOK_WORKSPACE"] == config.DEFAULT_WORKSPACE
    # 비밀은 기본값이 없다 — 비어 있는 것이 계약이다 (D7·D2).
    assert env["SILLOK_BEARER_TOKEN"] == ""
    assert env["OPENAI_API_KEY"] == ""
