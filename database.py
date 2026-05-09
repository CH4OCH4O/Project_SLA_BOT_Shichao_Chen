from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from utils import database_path, iso_now


SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slack_channel_id TEXT NOT NULL,
    slack_channel_name TEXT,
    slack_message_ts TEXT NOT NULL,
    thread_ts TEXT,
    user_id TEXT,
    user_role TEXT,
    text TEXT,
    is_customer INTEGER NOT NULL DEFAULT 0,
    is_bot INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sla_cases (
    case_id TEXT PRIMARY KEY,
    slack_channel_id TEXT NOT NULL,
    slack_channel_name TEXT,
    customer_message_ts TEXT NOT NULL,
    thread_ts TEXT NOT NULL,
    customer_user_id TEXT NOT NULL,
    message_text TEXT,
    assigned_owner_user_id TEXT,
    priority TEXT NOT NULL DEFAULT 'medium',
    needs_response INTEGER NOT NULL DEFAULT 1,
    sentiment TEXT NOT NULL DEFAULT 'neutral',
    ai_reason TEXT,
    classifier_source TEXT NOT NULL DEFAULT 'rule_based',
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    due_at TEXT NOT NULL,
    first_response_at TEXT,
    response_time_seconds INTEGER,
    response_source TEXT,
    response_match_reason TEXT,
    response_match_confidence REAL,
    breached INTEGER NOT NULL DEFAULT 0,
    escalated INTEGER NOT NULL DEFAULT 0,
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    notification_type TEXT NOT NULL,
    sent_to_user_id TEXT,
    sent_to_channel_id TEXT,
    sent_at TEXT NOT NULL,
    slack_message_ts TEXT,
    UNIQUE(case_id, notification_type)
);

CREATE TABLE IF NOT EXISTS users (
    slack_user_id TEXT PRIMARY KEY,
    display_name TEXT,
    role TEXT,
    is_customer INTEGER NOT NULL DEFAULT 0,
    is_internal INTEGER NOT NULL DEFAULT 0,
    is_manager INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS channels (
    slack_channel_id TEXT PRIMARY KEY,
    channel_name TEXT UNIQUE,
    channel_type TEXT,
    assigned_owner_user_id TEXT,
    manager_user_id TEXT,
    active INTEGER NOT NULL DEFAULT 1
);
"""

CASE_COLUMN_MIGRATIONS = {
    "needs_response": "ALTER TABLE sla_cases ADD COLUMN needs_response INTEGER NOT NULL DEFAULT 1",
    "sentiment": "ALTER TABLE sla_cases ADD COLUMN sentiment TEXT NOT NULL DEFAULT 'neutral'",
    "ai_reason": "ALTER TABLE sla_cases ADD COLUMN ai_reason TEXT",
    "classifier_source": "ALTER TABLE sla_cases ADD COLUMN classifier_source TEXT NOT NULL DEFAULT 'rule_based'",
    "response_source": "ALTER TABLE sla_cases ADD COLUMN response_source TEXT",
    "response_match_reason": "ALTER TABLE sla_cases ADD COLUMN response_match_reason TEXT",
    "response_match_confidence": "ALTER TABLE sla_cases ADD COLUMN response_match_confidence REAL",
}


def connect(path: str | None = None) -> sqlite3.Connection:
    db_path = path or database_path()
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_connection(path: str | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(path: str | None = None) -> None:
    with get_connection(path) as conn:
        conn.executescript(SCHEMA)
        migrate_db(conn)


def migrate_db(conn: sqlite3.Connection) -> None:
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(sla_cases)").fetchall()
    }
    for column, statement in CASE_COLUMN_MIGRATIONS.items():
        if column not in existing:
            conn.execute(statement)


def insert_message(conn: sqlite3.Connection, message: dict) -> None:
    conn.execute(
        """
        INSERT INTO messages (
            slack_channel_id, slack_channel_name, slack_message_ts, thread_ts,
            user_id, user_role, text, is_customer, is_bot, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            message["slack_channel_id"],
            message.get("slack_channel_name"),
            message["slack_message_ts"],
            message.get("thread_ts"),
            message.get("user_id"),
            message.get("user_role"),
            message.get("text"),
            int(message.get("is_customer", False)),
            int(message.get("is_bot", False)),
            message.get("created_at", iso_now()),
        ),
    )


def create_case(conn: sqlite3.Connection, case: dict) -> str:
    case_id = case.get("case_id") or f"SLA-{uuid.uuid4().hex[:8].upper()}"
    conn.execute(
        """
        INSERT INTO sla_cases (
            case_id, slack_channel_id, slack_channel_name, customer_message_ts,
            thread_ts, customer_user_id, message_text, assigned_owner_user_id,
            priority, needs_response, sentiment, ai_reason, classifier_source,
            status, created_at, due_at, breached, escalated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, 0, 0)
        """,
        (
            case_id,
            case["slack_channel_id"],
            case.get("slack_channel_name"),
            case["customer_message_ts"],
            case["thread_ts"],
            case["customer_user_id"],
            case.get("message_text"),
            case.get("assigned_owner_user_id"),
            case.get("priority", "medium"),
            int(case.get("needs_response", True)),
            case.get("sentiment", "neutral"),
            case.get("ai_reason"),
            case.get("classifier_source", "rule_based"),
            case["created_at"],
            case["due_at"],
        ),
    )
    return case_id


def find_case_by_thread(conn: sqlite3.Connection, channel_id: str, thread_ts: str):
    return conn.execute(
        """
        SELECT * FROM sla_cases
        WHERE slack_channel_id = ? AND thread_ts = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (channel_id, thread_ts),
    ).fetchone()


def get_open_cases(conn: sqlite3.Connection):
    return conn.execute(
        "SELECT * FROM sla_cases WHERE status = 'open' ORDER BY created_at"
    ).fetchall()


def get_recent_open_cases_for_channel(
    conn: sqlite3.Connection,
    channel_id: str,
    since_at: str,
):
    return conn.execute(
        """
        SELECT * FROM sla_cases
        WHERE status = 'open'
          AND slack_channel_id = ?
          AND created_at >= ?
        ORDER BY created_at DESC
        """,
        (channel_id, since_at),
    ).fetchall()


def mark_first_response(
    conn: sqlite3.Connection,
    case_id: str,
    first_response_at: str,
    response_time_seconds: int,
    breached: bool,
    response_source: str = "thread_reply",
    response_match_reason: str | None = None,
    response_match_confidence: float | None = None,
) -> None:
    conn.execute(
        """
        UPDATE sla_cases
        SET status = 'acknowledged',
            first_response_at = ?,
            response_time_seconds = ?,
            breached = ?,
            response_source = ?,
            response_match_reason = ?,
            response_match_confidence = ?,
            resolved_at = ?
        WHERE case_id = ?
        """,
        (
            first_response_at,
            response_time_seconds,
            int(breached),
            response_source,
            response_match_reason,
            response_match_confidence,
            first_response_at,
            case_id,
        ),
    )


def mark_breached(conn: sqlite3.Connection, case_id: str) -> None:
    conn.execute(
        """
        UPDATE sla_cases
        SET status = 'breached', breached = 1, escalated = 1
        WHERE case_id = ?
        """,
        (case_id,),
    )


def notification_sent(conn: sqlite3.Connection, case_id: str, notification_type: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM notifications WHERE case_id = ? AND notification_type = ?",
        (case_id, notification_type),
    ).fetchone()
    return row is not None


def record_notification(
    conn: sqlite3.Connection,
    case_id: str,
    notification_type: str,
    sent_to_user_id: str | None,
    sent_to_channel_id: str | None,
    slack_message_ts: str | None,
) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO notifications (
            case_id, notification_type, sent_to_user_id, sent_to_channel_id,
            sent_at, slack_message_ts
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            case_id,
            notification_type,
            sent_to_user_id,
            sent_to_channel_id,
            iso_now(),
            slack_message_ts,
        ),
    )


def upsert_user(conn: sqlite3.Connection, user: dict) -> None:
    conn.execute(
        """
        INSERT INTO users (
            slack_user_id, display_name, role, is_customer, is_internal, is_manager
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(slack_user_id) DO UPDATE SET
            display_name = excluded.display_name,
            role = excluded.role,
            is_customer = excluded.is_customer,
            is_internal = excluded.is_internal,
            is_manager = excluded.is_manager
        """,
        (
            user["slack_user_id"],
            user.get("display_name"),
            user.get("role"),
            int(user.get("is_customer", False)),
            int(user.get("is_internal", False)),
            int(user.get("is_manager", False)),
        ),
    )


def upsert_channel(conn: sqlite3.Connection, channel: dict) -> None:
    conn.execute(
        """
        INSERT INTO channels (
            slack_channel_id, channel_name, channel_type,
            assigned_owner_user_id, manager_user_id, active
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(slack_channel_id) DO UPDATE SET
            channel_name = excluded.channel_name,
            channel_type = excluded.channel_type,
            assigned_owner_user_id = excluded.assigned_owner_user_id,
            manager_user_id = excluded.manager_user_id,
            active = excluded.active
        """,
        (
            channel["slack_channel_id"],
            channel.get("channel_name"),
            channel.get("channel_type", "customer"),
            channel.get("assigned_owner_user_id"),
            channel.get("manager_user_id"),
            int(channel.get("active", True)),
        ),
    )


def fetch_all_cases(conn: sqlite3.Connection):
    return conn.execute("SELECT * FROM sla_cases ORDER BY created_at DESC").fetchall()
