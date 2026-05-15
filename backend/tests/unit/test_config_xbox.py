from pydantic import SecretStr

from app.config import Settings

_BASE = dict(
    database_url="postgresql+asyncpg://x:x@localhost/x",
    anthropic_api_key="sk-test",
    igdb_client_id="id",
    igdb_client_secret="sec",
    rawg_api_key="key",
)


def test_openxbl_api_key_defaults_to_empty(monkeypatch):
    monkeypatch.setenv("OPENXBL_API_KEY", "")
    s = Settings(**_BASE)
    assert s.openxbl_api_key.get_secret_value() == ""


def test_openxbl_api_key_masked_in_repr():
    s = Settings(**_BASE, openxbl_api_key=SecretStr("super-secret-key"))
    assert "super-secret-key" not in repr(s)


def test_openxbl_api_key_loads_from_env(monkeypatch):
    monkeypatch.setenv("OPENXBL_API_KEY", "key-from-env")
    s = Settings(**_BASE)
    assert s.openxbl_api_key.get_secret_value() == "key-from-env"
