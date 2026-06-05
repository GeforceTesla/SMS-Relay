from __future__ import annotations

from app.config import load_settings


def test_load_settings_from_config_toml(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
        [server]
        bearer_token = "from-config"
        db_path = "./data/test.db"
        private_key_path = "./keys/private.pem"
        max_body_bytes = 12345
        allowed_client_ids = ["phone-1", "phone-2"]
        """,
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SMS_RELAY_BEARER_TOKEN", raising=False)

    settings = load_settings()

    assert settings.bearer_token == "from-config"
    assert settings.db_path.as_posix() == "data/test.db"
    assert settings.private_key_path.as_posix() == "keys/private.pem"
    assert settings.max_body_bytes == 12345
    assert settings.allowed_client_ids == frozenset({"phone-1", "phone-2"})
