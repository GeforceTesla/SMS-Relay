from __future__ import annotations

import base64
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("SMS_RELAY_BEARER_TOKEN", "test-token")
os.environ.setdefault("SMS_RELAY_DB_PATH", "/tmp/sms-relay-test-import.db")
os.environ.setdefault("SMS_RELAY_PRIVATE_KEY_PATH", "/tmp/sms-relay-test-key.pem")
os.environ.setdefault("SMS_RELAY_ALLOWED_CLIENT_IDS", "phone-1")

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture
def keypair(tmp_path: Path) -> tuple[Path, Path]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    private_path = tmp_path / "server_private.pem"
    public_path = tmp_path / "server_public.pem"

    private_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_path.write_bytes(
        public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return private_path, public_path


@pytest.fixture
def settings(tmp_path: Path, keypair: tuple[Path, Path]) -> Settings:
    private_path, _ = keypair
    return Settings(
        bearer_token="test-token",
        db_path=tmp_path / "sms.db",
        private_key_path=private_path,
        max_body_bytes=65536,
        allowed_client_ids=frozenset({"phone-1"}),
    )


@pytest.fixture
def client(settings: Settings) -> TestClient:
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def encrypted_payload(keypair: tuple[Path, Path]):
    _, public_path = keypair

    def build(
        *,
        client_id: str = "phone-1",
        message_id: str | None = None,
        sender: str = "+15551234567",
        body: str = "hello",
        received_at_phone: int = 1710000000000,
        sim_slot: int | None = 1,
    ) -> dict[str, Any]:
        public_key = serialization.load_pem_public_key(public_path.read_bytes())
        aes_key = os.urandom(32)
        nonce = os.urandom(12)
        plaintext = {
            "sender": sender,
            "body": body,
            "received_at_phone": received_at_phone,
            "sim_slot": sim_slot,
        }
        plaintext_bytes = json.dumps(
            plaintext, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
        ciphertext = AESGCM(aes_key).encrypt(nonce, plaintext_bytes, None)
        encrypted_key = public_key.encrypt(
            aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

        return {
            "version": 1,
            "client_id": client_id,
            "message_id": message_id or str(uuid.uuid4()),
            "encrypted_key": base64.b64encode(encrypted_key).decode("ascii"),
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
            "created_at": 1710000000000,
        }

    return build


def flip_b64_byte(value: str) -> str:
    data = bytearray(base64.b64decode(value))
    data[-1] ^= 1
    return base64.b64encode(data).decode("ascii")
