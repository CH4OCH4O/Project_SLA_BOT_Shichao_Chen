from __future__ import annotations

import logging
from typing import Any

from slack_sdk.errors import SlackApiError
from slack_sdk.web.client import WebClient

from utils import format_duration, message_excerpt


logger = logging.getLogger(__name__)


class SlackMessenger:
    def __init__(self, client: WebClient | None, escalation_channel_id: str | None = None):
        self.client = client
        self.escalation_channel_id = escalation_channel_id

    def post_thread_reply(self, channel_id: str, thread_ts: str, text: str) -> str | None:
        if not self.client:
            logger.info("Slack client unavailable. Would post thread reply: %s", text)
            return None
        try:
            response = self.client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=text,
            )
            return response.get("ts")
        except SlackApiError as exc:
            error = exc.response.get("error")
            logger.error(
                "Could not post Slack thread reply to %s/%s: %s",
                channel_id,
                thread_ts,
                error,
            )
            return None

    def post_case_created(self, case: dict[str, Any]) -> str | None:
        return self.post_thread_reply(
            case["slack_channel_id"],
            case["thread_ts"],
            "SLA case created. First response due within the 40-second demo deadline.",
        )

    def post_warning(self, case: dict[str, Any]) -> str | None:
        owner = case.get("assigned_owner_user_id")
        mention = f"<@{owner}>, " if owner else ""
        return self.post_thread_reply(
            case["slack_channel_id"],
            case["thread_ts"],
            f"⚠️ {mention}this customer request is close to breaching SLA. "
            "Please respond before the 40-second demo deadline.",
        )

    def post_breach_thread_notice(self, case: dict[str, Any]) -> str | None:
        return self.post_thread_reply(
            case["slack_channel_id"],
            case["thread_ts"],
            "🚨 SLA breach: This customer request exceeded the 40-second demo first response SLA.",
        )

    def post_escalation(self, case: dict[str, Any], manager_user_id: str | None) -> str | None:
        if not self.escalation_channel_id:
            logger.warning("No escalation channel configured; skipping escalation post.")
            return None
        manager = f"<@{manager_user_id}> " if manager_user_id else ""
        owner = case.get("assigned_owner_user_id")
        owner_text = f"<@{owner}>" if owner else "Unassigned"
        channel_name = case.get("slack_channel_name") or case.get("slack_channel_id")
        text = (
            f"{manager}🚨 SLA breached for case #{case.get('case_id')} in #{channel_name}.\n"
            "No valid employee response was detected within 40 seconds.\n"
            f"Channel: #{channel_name}\n"
            f"Owner: {owner_text}\n"
            f"Customer request: \"{message_excerpt(case.get('message_text') or '')}\"\n"
            "Manager review required."
        )
        if not self.client:
            logger.info("Slack client unavailable. Would post escalation: %s", text)
            return None
        try:
            response = self.client.chat_postMessage(channel=self.escalation_channel_id, text=text)
            return response.get("ts")
        except SlackApiError as exc:
            error = exc.response.get("error")
            logger.error("Could not post Slack escalation to %s: %s", self.escalation_channel_id, error)
            return None

    def post_first_response_recorded(
        self,
        case: dict[str, Any],
        response_time_seconds: int,
        breached: bool,
    ) -> str | None:
        if breached:
            text = (
                f"First response recorded in {format_duration(response_time_seconds)}. "
                "This case had already breached the 40-second demo SLA."
            )
        else:
            text = f"SLA met. First response recorded in {format_duration(response_time_seconds)}."
        if case.get("response_source") == "ai_channel_match":
            text += " Detected from a channel-level employee reply."
        return self.post_thread_reply(case["slack_channel_id"], case["thread_ts"], text)


def get_channel_name(client: WebClient, channel_id: str) -> str | None:
    try:
        response = client.conversations_info(channel=channel_id)
        channel = response.get("channel", {})
        return channel.get("name")
    except Exception:
        logger.exception("Could not resolve channel name for %s", channel_id)
        return None
