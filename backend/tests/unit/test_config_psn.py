from pydantic import SecretStr

from app.config import Settings


def test_psn_npsso_defaults_to_empty(monkeypatch):
    monkeypatch.setenv("PSN_NPSSO", "")
    s = Settings(
        database_url="postgresql+asyncpg://x:x@localhost/x",
        anthropic_api_key="sk-test",
        igdb_client_id="id",
        igdb_client_secret="sec",
        rawg_api_key="key",
    )
    assert s.psn_npsso.get_secret_value() == ""


def test_psn_npsso_masked_in_repr():
    s = Settings(
        database_url="postgresql+asyncpg://x:x@localhost/x",
        anthropic_api_key="sk-test",
        igdb_client_id="id",
        igdb_client_secret="sec",
        rawg_api_key="key",
        psn_npsso=SecretStr("my-real-npsso-value"),
    )
    assert "my-real-npsso-value" not in repr(s)


def test_psn_npsso_loads_from_env(monkeypatch):
    monkeypatch.setenv("PSN_NPSSO", "npsso-from-env")
    s = Settings(
        database_url="postgresql+asyncpg://x:x@localhost/x",
        anthropic_api_key="sk-test",
        igdb_client_id="id",
        igdb_client_secret="sec",
        rawg_api_key="key",
    )
    assert s.psn_npsso.get_secret_value() == "npsso-from-env"
