from __future__ import annotations


def test_sms_body_not_in_logs(client, auth_headers, encrypted_payload, caplog) -> None:
    secret_body = "do-not-log-this-body"
    payload = encrypted_payload(body=secret_body)

    caplog.set_level("INFO", logger="sms_relay")
    response = client.post("/api/v1/sms", json=payload, headers=auth_headers)

    assert response.status_code == 200
    assert secret_body not in caplog.text
    assert payload["ciphertext"] not in caplog.text
    assert payload["encrypted_key"] not in caplog.text
    assert "test-token" not in caplog.text
