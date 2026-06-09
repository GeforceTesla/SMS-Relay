from __future__ import annotations

import base64
import json
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from .auth import verify_bearer_token
from .config import Settings, get_settings
from .crypto import DecryptionError, decrypt_envelope, sender_hash
from .db import (
    delete_messages_for_chain,
    first_client_for_sender,
    get_message,
    init_db,
    insert_sms,
    inbox_state,
    list_messages_for_chain,
    list_sender_threads,
)
from .models import EncryptedEnvelope

logger = logging.getLogger("sms_relay")

APP_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))


def format_server_time(value: int | None) -> str:
    if value is None:
        return "Unknown"
    local_time = datetime.fromtimestamp(value / 1000)
    return local_time.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def compact_message(value: str, limit: int = 96) -> str:
    one_line = " ".join(value.split())
    if len(one_line) <= limit:
        return one_line
    return one_line[: limit - 1].rstrip() + "..."


def sender_token(sender: str) -> str:
    encoded = base64.urlsafe_b64encode(sender.encode("utf-8")).decode("ascii")
    return encoded.rstrip("=")


def chain_token(client_id: str, sender: str) -> str:
    raw = json.dumps([client_id, sender], separators=(",", ":"))
    encoded = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")
    return encoded.rstrip("=")


def decode_sender_token(token: str) -> str:
    padding = "=" * (-len(token) % 4)
    try:
        return base64.urlsafe_b64decode((token + padding).encode("ascii")).decode("utf-8")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc


def decode_chain_token(token: str) -> tuple[str, str]:
    padding = "=" * (-len(token) % 4)
    try:
        raw = base64.urlsafe_b64decode((token + padding).encode("ascii")).decode("utf-8")
        client_id, sender = json.loads(raw)
        if not isinstance(client_id, str) or not isinstance(sender, str):
            raise ValueError
        return client_id, sender
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc


templates.env.filters["server_time"] = format_server_time
templates.env.filters["compact_message"] = compact_message
templates.env.filters["sender_token"] = sender_token
templates.env.filters["chain_token"] = lambda thread: chain_token(thread["client_id"], thread["sender"])


def create_app(
    settings: Settings | None = None,
    *,
    include_receiver: bool = True,
    include_reader: bool = True,
) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        init_db(app_settings.db_path)
        yield

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

    def settings_dep() -> Settings:
        return app_settings

    def auth_dep(
        authorization: str | None = Header(default=None),
        current_settings: Settings = Depends(settings_dep),
    ) -> None:
        verify_bearer_token(current_settings, authorization)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    if include_reader:
        app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")

        @app.get("/api/v1/inbox-state")
        def get_inbox_state() -> dict[str, int]:
            return inbox_state(app_settings.db_path)

        @app.get("/", response_class=HTMLResponse)
        def index(request: Request) -> HTMLResponse:
            threads = list_sender_threads(app_settings.db_path)
            return templates.TemplateResponse(
                request, "index.html", {"threads": threads}
            )

        @app.get("/senders/{token}", response_class=HTMLResponse)
        def sender_detail_legacy(token: str) -> RedirectResponse:
            sender = decode_sender_token(token)
            client_id = first_client_for_sender(app_settings.db_path, sender)
            if client_id is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
            return RedirectResponse(
                url=f"/chains/{chain_token(client_id, sender)}",
                status_code=status.HTTP_303_SEE_OTHER,
            )

        @app.get("/chains/{token}", response_class=HTMLResponse)
        def chain_detail(request: Request, token: str) -> HTMLResponse:
            client_id, sender = decode_chain_token(token)
            messages = list_messages_for_chain(app_settings.db_path, client_id, sender)
            if not messages:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
            threads = list_sender_threads(app_settings.db_path)
            return templates.TemplateResponse(
                request,
                "sender.html",
                {
                    "sender": sender,
                    "client_id": client_id,
                    "token": token,
                    "messages": messages,
                    "threads": threads,
                },
            )

        @app.post("/chains/{token}/delete")
        def delete_chain(token: str) -> RedirectResponse:
            client_id, sender = decode_chain_token(token)
            delete_messages_for_chain(app_settings.db_path, client_id, sender)
            return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

        @app.post("/senders/{token}/delete")
        def delete_sender_chain_legacy(token: str) -> RedirectResponse:
            sender = decode_sender_token(token)
            client_id = first_client_for_sender(app_settings.db_path, sender)
            if client_id is not None:
                delete_messages_for_chain(app_settings.db_path, client_id, sender)
            return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

        @app.get("/messages/{message_id}", response_class=HTMLResponse)
        def message_detail(request: Request, message_id: int) -> HTMLResponse:
            message = get_message(app_settings.db_path, message_id)
            if message is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
            return templates.TemplateResponse(
                request, "message.html", {"message": message}
            )

    if include_receiver:
        @app.post("/api/v1/sms", dependencies=[Depends(auth_dep)])
        async def receive_sms(
            request: Request, current_settings: Settings = Depends(settings_dep)
        ) -> dict[str, str]:
            body = await request.body()
            if len(body) > current_settings.max_body_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="payload too large",
                )

            try:
                payload = json.loads(body)
                envelope = EncryptedEnvelope(**payload)
            except (json.JSONDecodeError, TypeError, ValidationError):
                logger.info("sms_rejected reason=invalid_envelope")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="invalid encrypted envelope",
                ) from None

            if envelope.version != 1:
                logger.info(
                    "sms_rejected client_id=%s message_id=%s reason=unsupported_version",
                    envelope.client_id,
                    envelope.message_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="unsupported envelope version",
                )

            if envelope.client_id not in current_settings.allowed_client_ids:
                logger.info(
                    "sms_rejected client_id=%s message_id=%s reason=client_not_allowed",
                    envelope.client_id,
                    envelope.message_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="client id not allowed",
                )

            try:
                sms = decrypt_envelope(envelope, current_settings.private_key_path)
            except DecryptionError:
                logger.info(
                    "sms_rejected client_id=%s message_id=%s reason=decrypt_failed",
                    envelope.client_id,
                    envelope.message_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="encrypted payload could not be decrypted",
                ) from None

            _, duplicate = insert_sms(
                current_settings.db_path, envelope.client_id, envelope.message_id, sms
            )
            logger.info(
                "sms_accepted client_id=%s message_id=%s sender_hash=%s duplicate=%s",
                envelope.client_id,
                envelope.message_id,
                sender_hash(sms.sender),
                duplicate,
            )
            return {"status": "ok"}

    return app


app = create_app()
public_app = create_app(include_receiver=True, include_reader=False)
private_app = create_app(include_receiver=False, include_reader=True)
