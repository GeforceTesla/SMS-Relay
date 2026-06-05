from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from .config import Settings


def verify_bearer_token(
    settings: Settings, authorization: str | None = Header(default=None)
) -> None:
    prefix = "Bearer "
    if not authorization or not authorization.startswith(prefix):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    supplied = authorization[len(prefix) :]
    if not secrets.compare_digest(supplied, settings.bearer_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
