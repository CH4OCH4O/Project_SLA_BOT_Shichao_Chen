from __future__ import annotations

import os
import logging
from datetime import timedelta
from typing import Any

import database
from slack_client import SlackMessenger
from utils import env_int, iso_now, parse_iso, resolve_env_ref, slack_ts_to_datetime, utc_now


logger = logging.getLogger(__name__)


class SLAEngine:
    def __init__(self, config: dict[str, Any], messenger: SlackMessenger):
        self.config = config
        self.messenger = messenger
        # Demo SLA timing is intentionally compressed and configurable.
        # Defaults: warn once at 25 seconds, then breach/escalate once at 40 seconds.
        self.sla_due_seconds = env_int("SLA_DEMO_DUE_SECONDS", 40)
        self.warning_seconds = env_int("SLA_DEMO_WARNING_SECONDS", 25)
        self.channel_match_window_seconds = env_int("AI_CHANNEL_MATCH_WINDOW_SECONDS", 600)

    def configured_customer_users(self) -> set[str]:
        users = set()
        for value in self.config.get("roles", {}).get("customer_users", []):
            resolved = resolve_env_ref(value)
            if resolved and not resolved.endswith("_HERE"):
                users.add(resolved)
        env_customer = os.getenv("CUSTOMER_USER_ID")
        if env_customer:
            users.add(env_customer)
        return users

    def configured_internal_users(self) -> set[str]:
        users = set()
        for value in self.config.get("roles", {}).get("internal_users", []):
            resolved = resolve_env_ref(value)
            if resolved and not resolved.endswith("_HERE"):
                users.add(resolved)
        for env_name in ("SUPPORT_USER_ID", "MANAGER_USER_ID"):
            value = os.getenv(env_name)
            if value:
                users.add(value)
        return users

    def is_customer(self, user_id: str | None) -> bool:
        return bool(user_id and user_id in self.configured_customer_users())

    def is_internal(self, user_id: str | None) -> bool:
        return bool(user_id and user_id in self.configured_internal_users())

    def channel_settings(self, channel_name: str | None) -> dict[str, Any]:
        if not channel_name:
            return {}
        return self.config.get("channels", {}).get(channel_name, {})

    def assigned_owner_for_channel(self, channel_name: str | None) -> str | None:
        settings = self.channel_settings(channel_name)
        return resolve_env_ref(settings.get("assigned_owner_env")) or os.getenv("SUPPORT_USER_ID")

    def manager_for_channel(self, channel_name: str | None) -> str | None:
        settings = self.channel_settings(channel_name)
        return resolve_env_ref(settings.get("manager_env")) or os.getenv("MANAGER_USER_ID")

    def create_case(
        self,
        conn,
        channel_id: str,
        channel_name: str | None,
        ts: str,
        user_id: str,
        text: str,
        priority: str,
        needs_response: bool = True,
        sentiment: str = "neutral",
        ai_reason: str | None = None,
        classifier_source: str = "rule_based",
    ) -> str:
        created_at = slack_ts_to_datetime(ts)
        due_at = created_at + timedelta(seconds=self.sla_due_seconds)
        case = {
            "slack_channel_id": channel_id,
            "slack_channel_name": channel_name,
            "customer_message_ts": ts,
            "thread_ts": ts,
            "customer_user_id": user_id,
            "message_text": text,
            "assigned_owner_user_id": self.assigned_owner_for_channel(channel_name),
            "priority": priority,
            "needs_response": needs_response,
            "sentiment": sentiment,
            "ai_reason": ai_reason,
            "classifier_source": classifier_source,
            "created_at": created_at.isoformat(),
            "due_at": due_at.isoformat(),
        }
        case_id = database.create_case(conn, case)
        case["case_id"] = case_id
        slack_ts = self.messenger.post_case_created(case)
        database.record_notification(
            conn,
            case_id,
            "case_created",
            case.get("assigned_owner_user_id"),
            channel_id,
            slack_ts,
        )
        return case_id

    def record_first_response(
        self,
        conn,
        case,
        response_ts: str,
        response_source: str = "thread_reply",
        response_match_reason: str | None = None,
        response_match_confidence: float | None = None,
    ) -> bool:
        if case["status"] != "open":
            return False
        response_at = slack_ts_to_datetime(response_ts)
        created_at = parse_iso(case["created_at"])
        due_at = parse_iso(case["due_at"])
        if not created_at or not due_at:
            return False

        response_seconds = max(0, int((response_at - created_at).total_seconds()))
        breached = response_at > due_at
        database.mark_first_response(
            conn,
            case["case_id"],
            response_at.isoformat(),
            response_seconds,
            breached,
            response_source,
            response_match_reason,
            response_match_confidence,
        )
        case_dict = dict(case)
        case_dict["response_source"] = response_source
        slack_ts = self.messenger.post_first_response_recorded(
            case_dict,
            response_seconds,
            breached,
        )
        database.record_notification(
            conn,
            case["case_id"],
            "first_response_recorded",
            case["assigned_owner_user_id"],
            case["slack_channel_id"],
            slack_ts,
        )
        return True

    def recent_open_cases_for_channel(self, conn, channel_id: str) -> list[dict[str, Any]]:
        since_at = (utc_now() - timedelta(seconds=self.channel_match_window_seconds)).isoformat()
        return [
            dict(row)
            for row in database.get_recent_open_cases_for_channel(conn, channel_id, since_at)
        ]

    def check_open_cases(self) -> None:
        now = utc_now()
        with database.get_connection() as conn:
            for row in database.get_open_cases(conn):
                case = dict(row)
                created_at = parse_iso(case["created_at"])
                due_at = parse_iso(case["due_at"])
                if not created_at or not due_at:
                    continue
                age_seconds = (now - created_at).total_seconds()

                if age_seconds >= self.sla_due_seconds or now >= due_at:
                    self._send_breach(conn, case)
                elif age_seconds >= self.warning_seconds:
                    self._send_warning(conn, case)

    def _send_warning(self, conn, case: dict[str, Any]) -> None:
        if database.notification_sent(conn, case["case_id"], "warning_25s"):
            return
        slack_ts = self.messenger.post_warning(case)
        database.record_notification(
            conn,
            case["case_id"],
            "warning_25s",
            case.get("assigned_owner_user_id"),
            case["slack_channel_id"],
            slack_ts,
        )
        logger.info("Warning sent for case %s", case["case_id"])

    def _send_breach(self, conn, case: dict[str, Any]) -> None:
        self._send_warning(conn, case)
        if database.notification_sent(conn, case["case_id"], "breach_40s"):
            return
        database.mark_breached(conn, case["case_id"])
        thread_ts = self.messenger.post_breach_thread_notice(case)
        database.record_notification(
            conn,
            case["case_id"],
            "breach_40s",
            case.get("assigned_owner_user_id"),
            case["slack_channel_id"],
            thread_ts,
        )
        manager = self.manager_for_channel(case.get("slack_channel_name"))
        escalation_ts = self.messenger.post_escalation(case, manager)
        database.record_notification(
            conn,
            case["case_id"],
            "escalation_manager",
            manager,
            os.getenv("SLACK_ESCALATION_CHANNEL_ID"),
            escalation_ts,
        )
        logger.info("Breach sent for case %s", case["case_id"])


def seed_configured_entities(config: dict[str, Any]) -> None:
    with database.get_connection() as conn:
        for value in config.get("roles", {}).get("customer_users", []):
            user_id = resolve_env_ref(value)
            if user_id and not user_id.endswith("_HERE"):
                database.upsert_user(
                    conn,
                    {
                        "slack_user_id": user_id,
                        "display_name": "Customer",
                        "role": "customer",
                        "is_customer": True,
                    },
                )
        for env_name, role in (("SUPPORT_USER_ID", "support"), ("MANAGER_USER_ID", "manager")):
            user_id = os.getenv(env_name)
            if user_id:
                database.upsert_user(
                    conn,
                    {
                        "slack_user_id": user_id,
                        "display_name": role.title(),
                        "role": role,
                        "is_internal": True,
                        "is_manager": role == "manager",
                    },
                )
