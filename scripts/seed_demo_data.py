from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import database
from utils import utc_now


def main() -> None:
    database.init_db()
    now = utc_now()
    support = "U_SUPPORT_DEMO"
    manager = "U_MANAGER_DEMO"
    customer = "U_CUSTOMER_DEMO"

    with database.get_connection() as conn:
        demo_ids = ("SLA-DEMO-MET", "SLA-DEMO-OPEN", "SLA-DEMO-BREACH")
        for case_id in demo_ids:
            conn.execute("DELETE FROM notifications WHERE case_id = ?", (case_id,))
            conn.execute("DELETE FROM sla_cases WHERE case_id = ?", (case_id,))

        database.upsert_user(
            conn,
            {
                "slack_user_id": customer,
                "display_name": "Demo Customer",
                "role": "customer",
                "is_customer": True,
            },
        )
        database.upsert_user(
            conn,
            {
                "slack_user_id": support,
                "display_name": "Demo Support",
                "role": "support",
                "is_internal": True,
            },
        )
        database.upsert_user(
            conn,
            {
                "slack_user_id": manager,
                "display_name": "Demo Manager",
                "role": "manager",
                "is_internal": True,
                "is_manager": True,
            },
        )

        cases = [
            {
                "case_id": "SLA-DEMO-MET",
                "slack_channel_id": "C_ALPHA",
                "slack_channel_name": "client-alpha",
                "customer_message_ts": str(now.timestamp()),
                "thread_ts": str(now.timestamp()),
                "customer_user_id": customer,
                "message_text": "Hi team, the dashboard is not refreshing. Can someone help?",
                "assigned_owner_user_id": support,
                "priority": "medium",
                "needs_response": True,
                "sentiment": "neutral",
                "ai_reason": "Customer reports a dashboard refresh issue and asks for help.",
                "classifier_source": "gemini",
                "created_at": (now - timedelta(minutes=10)).isoformat(),
                "due_at": (now - timedelta(minutes=9, seconds=20)).isoformat(),
            },
            {
                "case_id": "SLA-DEMO-OPEN",
                "slack_channel_id": "C_ALPHA",
                "slack_channel_name": "client-alpha",
                "customer_message_ts": str((now - timedelta(minutes=2)).timestamp()),
                "thread_ts": str((now - timedelta(minutes=2)).timestamp()),
                "customer_user_id": customer,
                "message_text": "The export failed again. Can you check this?",
                "assigned_owner_user_id": support,
                "priority": "medium",
                "needs_response": True,
                "sentiment": "negative",
                "ai_reason": "Customer reports a repeated export failure and asks for investigation.",
                "classifier_source": "gemini",
                "created_at": (now - timedelta(seconds=28)).isoformat(),
                "due_at": (now + timedelta(seconds=12)).isoformat(),
            },
            {
                "case_id": "SLA-DEMO-BREACH",
                "slack_channel_id": "C_BETA",
                "slack_channel_name": "client-beta",
                "customer_message_ts": str((now - timedelta(minutes=7)).timestamp()),
                "thread_ts": str((now - timedelta(minutes=7)).timestamp()),
                "customer_user_id": customer,
                "message_text": "This is urgent. We are blocked and cannot continue the workflow.",
                "assigned_owner_user_id": support,
                "priority": "high",
                "needs_response": True,
                "sentiment": "negative",
                "ai_reason": "Customer describes an urgent workflow-blocking issue.",
                "classifier_source": "gemini",
                "created_at": (now - timedelta(seconds=70)).isoformat(),
                "due_at": (now - timedelta(seconds=30)).isoformat(),
            },
        ]

        for case in cases:
            database.create_case(conn, case)

        database.mark_first_response(
            conn,
            "SLA-DEMO-MET",
            (now - timedelta(minutes=9, seconds=35)).isoformat(),
            25,
            False,
            "thread_reply",
        )
        database.record_notification(conn, "SLA-DEMO-MET", "case_created", support, "C_ALPHA", "demo")
        database.record_notification(conn, "SLA-DEMO-MET", "first_response_recorded", support, "C_ALPHA", "demo")
        database.record_notification(conn, "SLA-DEMO-OPEN", "case_created", support, "C_ALPHA", "demo")
        database.record_notification(conn, "SLA-DEMO-OPEN", "warning_25s", support, "C_ALPHA", "demo")
        database.mark_breached(conn, "SLA-DEMO-BREACH")
        database.record_notification(conn, "SLA-DEMO-BREACH", "case_created", support, "C_BETA", "demo")
        database.record_notification(conn, "SLA-DEMO-BREACH", "warning_25s", support, "C_BETA", "demo")
        database.record_notification(conn, "SLA-DEMO-BREACH", "breach_40s", support, "C_BETA", "demo")
        database.record_notification(conn, "SLA-DEMO-BREACH", "escalation_manager", manager, "C_ESCALATE", "demo")

    print("Seeded demo SLA cases.")


if __name__ == "__main__":
    main()
