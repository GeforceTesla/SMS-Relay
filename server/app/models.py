from __future__ import annotations

from pydantic import BaseModel, Field


class EncryptedEnvelope(BaseModel):
    version: int
    client_id: str = Field(min_length=1, max_length=128)
    message_id: str = Field(min_length=1, max_length=128)
    encrypted_key: str = Field(min_length=1)
    nonce: str = Field(min_length=1)
    ciphertext: str = Field(min_length=1)
    created_at: int


class PlaintextSms(BaseModel):
    sender: str = Field(min_length=1, max_length=128)
    body: str = Field(min_length=0, max_length=65535)
    received_at_phone: int
    sim_slot: int | None = None
