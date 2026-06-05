from __future__ import annotations

from app.db import connect

from conftest import flip_b64_byte


def test_valid_encrypted_payload_is_accepted(
    client, auth_headers, settings, encrypted_payload
) -> None:
    response = client.post(
        "/api/v1/sms", json=encrypted_payload(body="stored"), headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    with connect(settings.db_path) as conn:
        row = conn.execute("SELECT sender, body FROM sms_messages").fetchone()
    assert row["sender"] == "+15551234567"
    assert row["body"] == "stored"


def test_wrong_bearer_token_rejected(client, encrypted_payload) -> None:
    response = client.post(
        "/api/v1/sms",
        json=encrypted_payload(),
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert response.status_code == 401


def test_missing_bearer_token_rejected(client, encrypted_payload) -> None:
    response = client.post("/api/v1/sms", json=encrypted_payload())

    assert response.status_code == 401


def test_tampered_ciphertext_rejected(client, auth_headers, encrypted_payload) -> None:
    payload = encrypted_payload()
    payload["ciphertext"] = flip_b64_byte(payload["ciphertext"])

    response = client.post("/api/v1/sms", json=payload, headers=auth_headers)

    assert response.status_code == 400


def test_tampered_encrypted_key_rejected(client, auth_headers, encrypted_payload) -> None:
    payload = encrypted_payload()
    payload["encrypted_key"] = flip_b64_byte(payload["encrypted_key"])

    response = client.post("/api/v1/sms", json=payload, headers=auth_headers)

    assert response.status_code == 400


def test_wrong_client_id_rejected(client, auth_headers, encrypted_payload) -> None:
    response = client.post(
        "/api/v1/sms",
        json=encrypted_payload(client_id="phone-2"),
        headers=auth_headers,
    )

    assert response.status_code == 403


def test_payload_too_large_rejected(client, auth_headers) -> None:
    response = client.post(
        "/api/v1/sms",
        content=b'{"version":1,"padding":"' + (b"x" * 70000) + b'"}',
        headers=auth_headers,
    )

    assert response.status_code == 413


def test_plaintext_payload_rejected(client, auth_headers, settings) -> None:
    response = client.post(
        "/api/v1/sms",
        json={"sender": "+15551234567", "body": "plain secret"},
        headers=auth_headers,
    )

    assert response.status_code == 400
    with connect(settings.db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM sms_messages").fetchone()[0]
    assert count == 0


def test_web_ui_lists_messages(client, auth_headers, encrypted_payload) -> None:
    response = client.post(
        "/api/v1/sms", json=encrypted_payload(body="visible"), headers=auth_headers
    )
    assert response.status_code == 200

    page = client.get("/")
    assert page.status_code == 200
    assert "visible" in page.text


def test_web_ui_groups_messages_by_sender_newest_first(client, auth_headers, encrypted_payload) -> None:
    first = client.post(
        "/api/v1/sms",
        json=encrypted_payload(sender="+15550000001", body="older from one"),
        headers=auth_headers,
    )
    second = client.post(
        "/api/v1/sms",
        json=encrypted_payload(sender="+15550000001", body="newest from one"),
        headers=auth_headers,
    )
    third = client.post(
        "/api/v1/sms",
        json=encrypted_payload(sender="+15550000002", body="only from two"),
        headers=auth_headers,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 200

    page = client.get("/")
    assert page.status_code == 200
    assert "2 sender threads" in page.text
    assert "+15550000001" in page.text
    assert "newest from one" in page.text
    assert "older from one" not in page.text


def test_sender_history_and_delete_chain(client, auth_headers, settings, encrypted_payload) -> None:
    from app.db import connect
    from app.main import sender_token

    sender = "+15550000003"
    other_sender = "+15550000004"
    assert client.post(
        "/api/v1/sms",
        json=encrypted_payload(sender=sender, body="old history"),
        headers=auth_headers,
    ).status_code == 200
    assert client.post(
        "/api/v1/sms",
        json=encrypted_payload(sender=sender, body="new history"),
        headers=auth_headers,
    ).status_code == 200
    assert client.post(
        "/api/v1/sms",
        json=encrypted_payload(sender=other_sender, body="keep me"),
        headers=auth_headers,
    ).status_code == 200

    token = sender_token(sender)
    history = client.get(f"/senders/{token}")
    assert history.status_code == 200
    assert history.text.index("new history") < history.text.index("old history")
    assert "2 sender threads" in history.text
    assert other_sender in history.text
    assert "keep me" in history.text
    assert f'data-delete-url="/senders/{token}/delete"' in history.text
    assert "Delete chain</button>" in history.text
    assert f'action="/senders/{token}/delete"' not in history.text

    deleted = client.post(f"/senders/{token}/delete", follow_redirects=False)
    assert deleted.status_code == 303

    with connect(settings.db_path) as conn:
        deleted_count = conn.execute(
            "SELECT COUNT(*) FROM sms_messages WHERE sender = ?", (sender,)
        ).fetchone()[0]
        kept_count = conn.execute(
            "SELECT COUNT(*) FROM sms_messages WHERE sender = ?", (other_sender,)
        ).fetchone()[0]
    assert deleted_count == 0
    assert kept_count == 1


def test_inbox_state_changes_after_message(client, auth_headers, encrypted_payload) -> None:
    empty = client.get("/api/v1/inbox-state")
    assert empty.status_code == 200
    assert empty.json() == {
        "message_count": 0,
        "sender_count": 0,
        "newest_received_at_server": 0,
    }

    response = client.post(
        "/api/v1/sms",
        json=encrypted_payload(sender="+15550000005", body="state update"),
        headers=auth_headers,
    )
    assert response.status_code == 200

    state = client.get("/api/v1/inbox-state")
    assert state.status_code == 200
    payload = state.json()
    assert payload["message_count"] == 1
    assert payload["sender_count"] == 1
    assert payload["newest_received_at_server"] > 0


def test_public_app_exposes_receiver_only(settings, auth_headers, encrypted_payload) -> None:
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app(settings, include_receiver=True, include_reader=False)) as public_client:
        assert public_client.get("/healthz").status_code == 200
        assert public_client.get("/").status_code == 404
        assert public_client.get("/api/v1/inbox-state").status_code == 404
        response = public_client.post(
            "/api/v1/sms", json=encrypted_payload(), headers=auth_headers
        )
        assert response.status_code == 200


def test_private_app_exposes_reader_only(settings, auth_headers, encrypted_payload) -> None:
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app(settings, include_receiver=False, include_reader=True)) as private_client:
        assert private_client.get("/healthz").status_code == 200
        assert private_client.get("/").status_code == 200
        assert private_client.get("/api/v1/inbox-state").status_code == 200
        response = private_client.post(
            "/api/v1/sms", json=encrypted_payload(), headers=auth_headers
        )
        assert response.status_code == 404
