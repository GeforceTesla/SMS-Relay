from __future__ import annotations

from app.crypto import decrypt_envelope
from app.models import EncryptedEnvelope


def test_crypto_decrypts_valid_envelope(settings, encrypted_payload) -> None:
    payload = encrypted_payload(body="hello crypto")
    sms = decrypt_envelope(EncryptedEnvelope(**payload), settings.private_key_path)

    assert sms.sender == "+15551234567"
    assert sms.body == "hello crypto"
    assert sms.received_at_phone == 1710000000000
    assert sms.sim_slot == 1
