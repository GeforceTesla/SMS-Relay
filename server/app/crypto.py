from __future__ import annotations

import base64
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import ValidationError

from .models import EncryptedEnvelope, PlaintextSms


class DecryptionError(ValueError):
    pass


def _decode_b64(value: str, field_name: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except Exception as exc:
        raise DecryptionError(f"invalid base64 for {field_name}") from exc


@lru_cache(maxsize=4)
def load_private_key(private_key_path: str):
    key_data = Path(private_key_path).read_bytes()
    return serialization.load_pem_private_key(key_data, password=None)


def decrypt_envelope(
    envelope: EncryptedEnvelope, private_key_path: Path
) -> PlaintextSms:
    encrypted_key = _decode_b64(envelope.encrypted_key, "encrypted_key")
    nonce = _decode_b64(envelope.nonce, "nonce")
    ciphertext = _decode_b64(envelope.ciphertext, "ciphertext")

    if len(nonce) != 12:
        raise DecryptionError("invalid AES-GCM nonce length")

    private_key = load_private_key(str(private_key_path))
    try:
        aes_key = private_key.decrypt(
            encrypted_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
    except Exception as exc:
        raise DecryptionError("encrypted key could not be decrypted") from exc

    if len(aes_key) != 32:
        raise DecryptionError("invalid AES key length")

    try:
        plaintext_bytes = AESGCM(aes_key).decrypt(nonce, ciphertext, None)
    except InvalidTag as exc:
        raise DecryptionError("ciphertext authentication failed") from exc

    try:
        plaintext: Any = json.loads(plaintext_bytes.decode("utf-8"))
        return PlaintextSms(**plaintext)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValidationError) as exc:
        raise DecryptionError("invalid plaintext SMS payload") from exc


def sender_hash(sender: str) -> str:
    digest = hashes.Hash(hashes.SHA256())
    digest.update(sender.encode("utf-8"))
    return base64.urlsafe_b64encode(digest.finalize())[:16].decode("ascii")
