from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
from slack_sdk import WebClient


def main() -> None:
    load_dotenv()
    token = os.getenv("SLACK_BOT_TOKEN")
    if not token:
        raise SystemExit("Set SLACK_BOT_TOKEN in .env before running this script.")

    client = WebClient(token=token)

    print("Channels:")
    cursor = None
    while True:
        response = client.conversations_list(
            types="public_channel,private_channel",
            exclude_archived=True,
            limit=200,
            cursor=cursor,
        )
        for channel in response.get("channels", []):
            print(f"- #{channel.get('name')}: {channel.get('id')}")
        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    print("\nUsers:")
    cursor = None
    while True:
        response = client.users_list(limit=200, cursor=cursor)
        for user in response.get("members", []):
            if user.get("deleted") or user.get("is_bot"):
                continue
            profile = user.get("profile", {})
            name = profile.get("display_name") or profile.get("real_name") or user.get("name")
            print(f"- {name}: {user.get('id')}")
        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break


if __name__ == "__main__":
    main()
