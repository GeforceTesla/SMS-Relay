from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Settings:
    bearer_token: str
    db_path: Path
    private_key_path: Path
    max_body_bytes: int
    allowed_client_ids: frozenset[str]


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _load_toml_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("rb") as config_file:
        config = tomllib.load(config_file)
    server = config.get("server")
    if not isinstance(server, dict):
        raise RuntimeError(f"{config_path} must contain a [server] section")
    return server


def _client_ids_from_config(value: Any, source: str) -> frozenset[str]:
    if isinstance(value, str):
        items = [item.strip() for item in value.split(",")]
    elif isinstance(value, list):
        items = [str(item).strip() for item in value]
    else:
        raise RuntimeError(f"{source} allowed_client_ids must be a list or comma-separated string")

    client_ids = frozenset(item for item in items if item)
    if not client_ids:
        raise RuntimeError(f"{source} must contain at least one allowed client id")
    return client_ids


def _settings_from_config(config_path: Path) -> Settings:
    server = _load_toml_config(config_path)
    try:
        bearer_token = str(server["bearer_token"])
    except KeyError as exc:
        raise RuntimeError(f"{config_path} missing server.bearer_token") from exc

    if not bearer_token:
        raise RuntimeError(f"{config_path} server.bearer_token must not be empty")

    return Settings(
        bearer_token=bearer_token,
        db_path=Path(str(server.get("db_path", "./data/sms.db"))),
        private_key_path=Path(str(server.get("private_key_path", "./keys/server_private.pem"))),
        max_body_bytes=int(server.get("max_body_bytes", 65536)),
        allowed_client_ids=_client_ids_from_config(
            server.get("allowed_client_ids", ["phone-1"]),
            f"{config_path} server.allowed_client_ids",
        ),
    )


def _settings_from_env() -> Settings:
    allowed = os.getenv("SMS_RELAY_ALLOWED_CLIENT_IDS", "phone-1")
    return Settings(
        bearer_token=_required_env("SMS_RELAY_BEARER_TOKEN"),
        db_path=Path(os.getenv("SMS_RELAY_DB_PATH", "/app/data/sms.db")),
        private_key_path=Path(
            os.getenv("SMS_RELAY_PRIVATE_KEY_PATH", "/app/keys/server_private.pem")
        ),
        max_body_bytes=int(os.getenv("SMS_RELAY_MAX_BODY_BYTES", "65536")),
        allowed_client_ids=_client_ids_from_config(
            allowed, "SMS_RELAY_ALLOWED_CLIENT_IDS"
        ),
    )


def load_settings() -> Settings:
    config_path = Path(os.getenv("SMS_RELAY_CONFIG_PATH", "config.toml"))
    if config_path.exists():
        return _settings_from_config(config_path)
    return _settings_from_env()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
