from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


if load_dotenv:
    load_dotenv()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def slack_ts_to_datetime(ts: str) -> datetime:
    return datetime.fromtimestamp(float(ts), tz=timezone.utc)


def format_duration(seconds: int | float | None) -> str:
    if seconds is None:
        return "-"
    seconds = int(round(seconds))
    minutes, remainder = divmod(seconds, 60)
    if minutes:
        return f"{minutes}m {remainder}s"
    return f"{remainder}s"


def database_path() -> str:
    url = os.getenv("DATABASE_URL", "sqlite:///sla_bot.db")
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "", 1)
    return url


def load_config(path: str = "config.yaml") -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML is required to load config.yaml. Run `pip install -r requirements.txt`.") from exc

    config_path = Path(path)
    if not config_path.exists():
        config_path = Path("config.yaml.example")
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def resolve_env_ref(value: str | None) -> str | None:
    if not value:
        return None
    return os.getenv(value, value)


def message_excerpt(text: str, max_len: int = 120) -> str:
    clean = " ".join((text or "").split())
    if len(clean) <= max_len:
        return clean
    return clean[: max_len - 3] + "..."
