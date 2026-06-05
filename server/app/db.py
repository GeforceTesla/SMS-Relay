from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from .models import PlaintextSms


SCHEMA = """
CREATE TABLE IF NOT EXISTS sms_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id TEXT NOT NULL,
  client_message_id TEXT NOT NULL,
  sender TEXT NOT NULL,
  body TEXT NOT NULL,
  received_at_phone INTEGER NOT NULL,
  received_at_server INTEGER NOT NULL,
  sim_slot INTEGER,
  raw_json TEXT NOT NULL,
  UNIQUE(client_id, client_message_id)
);

CREATE INDEX IF NOT EXISTS idx_sms_received_at_server
ON sms_messages(received_at_server);

CREATE INDEX IF NOT EXISTS idx_sms_sender
ON sms_messages(sender);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def insert_sms(
    db_path: Path, client_id: str, client_message_id: str, sms: PlaintextSms
) -> tuple[int, bool]:
    now_ms = int(time.time() * 1000)
    raw_json = json.dumps(sms.model_dump(), separators=(",", ":"), sort_keys=True)

    with connect(db_path) as conn:
        try:
            cursor = conn.execute(
                """
                INSERT INTO sms_messages (
                    client_id,
                    client_message_id,
                    sender,
                    body,
                    received_at_phone,
                    received_at_server,
                    sim_slot,
                    raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    client_id,
                    client_message_id,
                    sms.sender,
                    sms.body,
                    sms.received_at_phone,
                    now_ms,
                    sms.sim_slot,
                    raw_json,
                ),
            )
            return int(cursor.lastrowid), False
        except sqlite3.IntegrityError:
            row = conn.execute(
                """
                SELECT id FROM sms_messages
                WHERE client_id = ? AND client_message_id = ?
                """,
                (client_id, client_message_id),
            ).fetchone()
            if row is None:
                raise
            return int(row["id"]), True


def list_messages(db_path: Path, limit: int = 100) -> list[sqlite3.Row]:
    with connect(db_path) as conn:
        return list(
            conn.execute(
                """
                SELECT id, client_id, client_message_id, sender, body,
                       received_at_phone, received_at_server, sim_slot
                FROM sms_messages
                ORDER BY received_at_server DESC
                LIMIT ?
                """,
                (limit,),
            )
        )


def get_message(db_path: Path, message_id: int) -> sqlite3.Row | None:
    with connect(db_path) as conn:
        return conn.execute(
            """
            SELECT id, client_id, client_message_id, sender, body,
                   received_at_phone, received_at_server, sim_slot
            FROM sms_messages
            WHERE id = ?
            """,
            (message_id,),
        ).fetchone()


def list_sender_threads(db_path: Path, limit: int = 100) -> list[sqlite3.Row]:
    with connect(db_path) as conn:
        return list(
            conn.execute(
                """
                SELECT m.id, m.client_id, m.client_message_id, m.sender, m.body,
                       m.received_at_phone, m.received_at_server, m.sim_slot,
                       (
                         SELECT COUNT(*)
                         FROM sms_messages c
                         WHERE c.sender = m.sender
                       ) AS message_count,
                       (
                         SELECT GROUP_CONCAT(client_id, ', ')
                         FROM (
                           SELECT DISTINCT c.client_id
                           FROM sms_messages c
                           WHERE c.sender = m.sender
                           ORDER BY c.client_id
                         )
                       ) AS receiver_client_ids
                FROM sms_messages m
                WHERE m.id = (
                    SELECT latest.id
                    FROM sms_messages latest
                    WHERE latest.sender = m.sender
                    ORDER BY latest.received_at_server DESC, latest.id DESC
                    LIMIT 1
                )
                ORDER BY m.received_at_server DESC, m.id DESC
                LIMIT ?
                """,
                (limit,),
            )
        )


def list_messages_for_sender(db_path: Path, sender: str, limit: int = 500) -> list[sqlite3.Row]:
    with connect(db_path) as conn:
        return list(
            conn.execute(
                """
                SELECT id, client_id, client_message_id, sender, body,
                       received_at_phone, received_at_server, sim_slot
                FROM sms_messages
                WHERE sender = ?
                ORDER BY received_at_server DESC, id DESC
                LIMIT ?
                """,
                (sender, limit),
            )
        )


def delete_messages_for_sender(db_path: Path, sender: str) -> int:
    with connect(db_path) as conn:
        cursor = conn.execute("DELETE FROM sms_messages WHERE sender = ?", (sender,))
        return int(cursor.rowcount)


def inbox_state(db_path: Path) -> dict[str, int]:
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS message_count,
                   COUNT(DISTINCT sender) AS sender_count,
                   COALESCE(MAX(received_at_server), 0) AS newest_received_at_server
            FROM sms_messages
            """
        ).fetchone()
    return {
        "message_count": int(row["message_count"]),
        "sender_count": int(row["sender_count"]),
        "newest_received_at_server": int(row["newest_received_at_server"]),
    }


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)
