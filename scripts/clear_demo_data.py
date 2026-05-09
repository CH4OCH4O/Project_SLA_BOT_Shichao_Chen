from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import database


def main() -> None:
    database.init_db()
    with database.get_connection() as conn:
        conn.execute("DELETE FROM notifications WHERE case_id LIKE 'SLA-DEMO-%'")
        conn.execute("DELETE FROM sla_cases WHERE case_id LIKE 'SLA-DEMO-%'")
        conn.execute("DELETE FROM messages WHERE slack_channel_id IN ('C_ALPHA', 'C_BETA')")
    print("Cleared demo SLA cases.")


if __name__ == "__main__":
    main()
