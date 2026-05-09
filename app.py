from __future__ import annotations

import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

import database
from ai_classifier import classify_customer_message, match_employee_response_to_case
from sla_engine import SLAEngine, seed_configured_entities
from slack_client import SlackMessenger, get_channel_name
from utils import env_int, iso_now, load_config


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


config = load_config()
database.init_db()

bolt_app = App(token=os.getenv("SLACK_BOT_TOKEN"))
messenger = SlackMessenger(
    bolt_app.client,
    escalation_channel_id=os.getenv("SLACK_ESCALATION_CHANNEL_ID"),
)
engine = SLAEngine(config, messenger)
seed_configured_entities(config)


def _is_bot_message(event: dict) -> bool:
    return bool(event.get("bot_id") or event.get("subtype") == "bot_message")


def _channel_name(channel_id: str) -> str | None:
    return get_channel_name(bolt_app.client, channel_id)


@bolt_app.event("message")
def handle_message_events(event, logger):  # noqa: ANN001
    if _is_bot_message(event):
        return

    channel_id = event.get("channel")
    user_id = event.get("user")
    ts = event.get("ts")
    thread_ts = event.get("thread_ts")
    text = event.get("text") or ""

    if not channel_id or not user_id or not ts:
        return

    channel_name = _channel_name(channel_id)
    is_customer = engine.is_customer(user_id)
    is_internal = engine.is_internal(user_id)
    user_role = "customer" if is_customer else "internal" if is_internal else "unknown"

    with database.get_connection() as conn:
        database.insert_message(
            conn,
            {
                "slack_channel_id": channel_id,
                "slack_channel_name": channel_name,
                "slack_message_ts": ts,
                "thread_ts": thread_ts,
                "user_id": user_id,
                "user_role": user_role,
                "text": text,
                "is_customer": is_customer,
                "is_bot": False,
                "created_at": iso_now(),
            },
        )

        if thread_ts and is_internal:
            case = database.find_case_by_thread(conn, channel_id, thread_ts)
            if case:
                engine.record_first_response(conn, case, ts, response_source="thread_reply")
            return

        if thread_ts:
            return

        if is_internal:
            open_cases = engine.recent_open_cases_for_channel(conn, channel_id)
            # AI channel matching catches employee replies that happen outside
            # the original Slack thread while staying scoped to this channel.
            match = match_employee_response_to_case(
                text,
                open_cases,
                context={"channel_id": channel_id, "employee_user_id": user_id},
            )
            if match["is_response"] and match["matched_case_id"]:
                matched_case = next(
                    (case for case in open_cases if case["case_id"] == match["matched_case_id"]),
                    None,
                )
                if matched_case:
                    engine.record_first_response(
                        conn,
                        matched_case,
                        ts,
                        response_source="ai_channel_match",
                        response_match_reason=match.get("reason"),
                        response_match_confidence=match.get("confidence"),
                    )
                    logger.info(
                        "AI channel match acknowledged case %s with confidence %.2f",
                        matched_case["case_id"],
                        match.get("confidence", 0),
                    )
            else:
                logger.info("Ignoring internal top-level message from %s", user_id)
            return

        if not is_customer:
            logger.info("Ignoring unknown top-level message from %s", user_id)
            return

        # AI agent classification happens in one module so Gemini prompts,
        # JSON validation, and rule-based fallback stay easy to demo and audit.
        result = classify_customer_message(
            text,
            context={"channel_id": channel_id, "channel_name": channel_name, "customer_user_id": user_id},
        )
        if not result["needs_response"]:
            logger.info("Ignoring message: %s", result["reason"])
            return

        case_id = engine.create_case(
            conn,
            channel_id=channel_id,
            channel_name=channel_name,
            ts=ts,
            user_id=user_id,
            text=text,
            priority=result["priority"],
            needs_response=result["needs_response"],
            sentiment=result["sentiment"],
            ai_reason=result["reason"],
            classifier_source=result["classifier_source"],
        )
        logger.info("Created SLA case %s. Classifier reason: %s", case_id, result["reason"])


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        engine.check_open_cases,
        "interval",
        seconds=env_int("CHECK_INTERVAL_SECONDS", 5),
        id="sla_open_case_check",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler


if __name__ == "__main__":
    if not os.getenv("SLACK_BOT_TOKEN") or not os.getenv("SLACK_APP_TOKEN"):
        raise SystemExit(
            "Missing Slack tokens. Copy .env.example to .env and set SLACK_BOT_TOKEN and SLACK_APP_TOKEN."
        )
    start_scheduler()
    logger.info("Starting Slack SLA bot in Socket Mode.")
    SocketModeHandler(bolt_app, os.environ["SLACK_APP_TOKEN"]).start()
