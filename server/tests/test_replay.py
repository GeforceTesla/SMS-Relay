from __future__ import annotations

from app.db import connect


def test_duplicate_message_id_is_idempotent(
    client, auth_headers, settings, encrypted_payload
) -> None:
    message_id = "f71fcb9d-f9b2-49b5-9e1b-5b79c2a78e33"
    first_payload = encrypted_payload(message_id=message_id, body="first")
    second_payload = encrypted_payload(message_id=message_id, body="second")

    first = client.post("/api/v1/sms", json=first_payload, headers=auth_headers)
    second = client.post("/api/v1/sms", json=second_payload, headers=auth_headers)

    assert first.status_code == 200
    assert second.status_code == 200
    with connect(settings.db_path) as conn:
        rows = conn.execute("SELECT body FROM sms_messages").fetchall()
    assert [row["body"] for row in rows] == ["first"]
