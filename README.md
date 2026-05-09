# Slack SLA Reminder Bot MVP

Demo project for Ridgeline Agency. The app monitors selected Slack customer channels, creates SLA cases for customer messages that need a response, warns the assigned employee before breach, escalates missed cases, records case history in SQLite, and shows manager KPIs in a Streamlit dashboard.

The current demo SLA is compressed for live presentation:

- Case due time: 40 seconds after creation.
- Warning time: 25 seconds after creation.
- No immediate employee mention when a case is created.
- One warning mention at about 25 seconds.
- Breach and manager escalation at about 40 seconds if no valid employee response is detected.

## What This Project Includes

- Slack Socket Mode bot using Slack Bolt for Python.
- Gemini AI classification for customer messages.
- Rule-based fallback if `GEMINI_API_KEY` is missing or Gemini fails.
- Gemini AI matching for employee top-level channel replies against recent open cases.
- Thread-based first response tracking.
- SQLite local database.
- Streamlit manager dashboard with SLA KPIs, sentiment, priority, response source, and AI reason.
- Demo scripts and sample scenarios.

## Architecture

```text
Slack workspace
  -> Slack Socket Mode events
  -> app.py
  -> ai_classifier.py
       -> Gemini API when GEMINI_API_KEY is set
       -> classifier.py fallback when Gemini is unavailable
  -> sla_engine.py
  -> database.py / sla_bot.db
  -> slack_client.py

Streamlit dashboard
  -> dashboard.py
  -> sla_bot.db
```

The bot and dashboard run locally and share the same SQLite database file.

## Requirements

- Python 3.11 or newer.
- A Slack workspace where you can create/install a Slack app.
- Permission to invite the bot to the monitored channels.
- Optional but recommended: a Gemini API key from Google AI Studio.
- Windows PowerShell is supported through the included `.ps1` scripts.

## Quick Start From A Downloaded Zip

1. Download and unzip the project.

2. Open the project folder in VS Code:

   ```text
   C:\path\to\Final Project_Ridgeline
   ```

3. Open a VS Code terminal and run:

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\setup.ps1
   ```

   This creates `.venv`, installs dependencies, creates `.env` from `.env.example` if missing, and initializes the database.

4. Create and configure a Slack app by following:

   ```text
   docs/manual_setup_steps.md
   ```

5. Create a Gemini API key by following the Gemini section in:

   ```text
   docs/manual_setup_steps.md
   ```

6. Edit `.env` and fill in your Slack/Gemini values.

7. Start the bot:

   ```powershell
   .\run_bot.ps1
   ```

8. Open a second terminal and start the dashboard:

   ```powershell
   .\run_dashboard.ps1
   ```

## Environment Variables

Create `.env` from `.env.example` and fill it in:

```env
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SLACK_SIGNING_SECRET=
SLACK_ESCALATION_CHANNEL_ID=C...

GEMINI_API_KEY=...
GEMINI_MODEL=gemini-flash-latest

MANAGER_USER_ID=U...
SUPPORT_USER_ID=U...
CUSTOMER_USER_ID=U...

DATABASE_URL=sqlite:///sla_bot.db

SLA_DEMO_DUE_SECONDS=40
SLA_DEMO_WARNING_SECONDS=25
AI_CHANNEL_MATCH_WINDOW_SECONDS=600
CHECK_INTERVAL_SECONDS=5
```

Notes:

- Do not commit `.env` to GitHub.
- `SLACK_BOT_TOKEN` comes from Slack `OAuth & Permissions`.
- `SLACK_APP_TOKEN` comes from Slack `Basic Information` or `Socket Mode` app-level tokens and needs `connections:write`.
- `SLACK_ESCALATION_CHANNEL_ID` is the internal alerts channel ID.
- `MANAGER_USER_ID`, `SUPPORT_USER_ID`, and `CUSTOMER_USER_ID` are Slack user IDs.
- `GEMINI_API_KEY` enables AI classification and channel-level response matching.
- If `GEMINI_API_KEY` is empty, the app still runs with rule-based customer classification, but AI channel matching will not auto-acknowledge cases.

## Slack App Setup

The full Slack setup checklist is in [docs/manual_setup_steps.md](docs/manual_setup_steps.md). In short:

1. Create a Slack app from scratch.
2. Enable Socket Mode.
3. Create an app-level token with `connections:write`.
4. Add bot scopes:
   - `app_mentions:read`
   - `channels:history`
   - `channels:read`
   - `chat:write`
   - `groups:history`
   - `groups:read`
   - `users:read`
5. Subscribe to bot events:
   - `message.channels`
   - `message.groups`
   - `app_mention`
6. Install or reinstall the app to the workspace.
7. Invite the bot to customer channels and the escalation channel.
8. Copy token, channel IDs, and user IDs into `.env`.

## Gemini API Setup

1. Go to [Google AI Studio](https://aistudio.google.com/).
2. Create an API key.
3. Add it to `.env`:

   ```env
   GEMINI_API_KEY=your_key_here
   GEMINI_MODEL=gemini-flash-latest
   ```

4. Test it:

   ```powershell
   python scripts/test_ai_classifier.py
   ```

If Gemini is working, output should include:

```text
'classifier_source': 'gemini'
```

## Configuration Files

`config.yaml` maps channel names to the support owner and manager environment variables.

Start from the example:

```powershell
copy config.yaml.example config.yaml
```

Example:

```yaml
channels:
  client-bella-beaut:
    assigned_owner_env: SUPPORT_USER_ID
    manager_env: MANAGER_USER_ID

  client-corewear:
    assigned_owner_env: SUPPORT_USER_ID
    manager_env: MANAGER_USER_ID

roles:
  customer_users:
    - CUSTOMER_USER_ID

  internal_users:
    - SUPPORT_USER_ID
    - MANAGER_USER_ID

  managers:
    - MANAGER_USER_ID
```

Important:

- Channel names must match Slack channel names without `#`.
- The values such as `SUPPORT_USER_ID` refer to variables in `.env`.
- If you add more customer channels, add them under `channels`.

## Database Setup And Migration

Initialize or migrate the database:

```powershell
python scripts/init_db.py
```

The migration is additive and keeps existing data. It adds fields used by the AI classifier and response detection:

- `needs_response`
- `sentiment`
- `ai_reason`
- `classifier_source`
- `response_source`
- `response_match_reason`
- `response_match_confidence`

To clear seeded demo data:

```powershell
.\clear_demo_data.ps1
```

To clear all local case/message/notification history:

```powershell
python -c "import sqlite3; c=sqlite3.connect('sla_bot.db'); c.execute('DELETE FROM notifications'); c.execute('DELETE FROM sla_cases'); c.execute('DELETE FROM messages'); c.commit(); c.close(); print('Cleared all cases and messages.')"
```

## Running The App

Terminal 1, bot:

```powershell
.\run_bot.ps1
```

Terminal 2, dashboard:

```powershell
.\run_dashboard.ps1
```

Manual equivalents:

```powershell
.\.venv\Scripts\Activate.ps1
python app.py
```

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run dashboard.py
```

AI does not need a separate terminal. The bot calls Gemini automatically when Slack messages arrive.

## Demo Scenarios

Use [DEMO_CASES.md](DEMO_CASES.md)

Core scenarios:

- Customer request creates a case without immediate employee mention.
- Warning posts once at about 25 seconds.
- Breach escalates at about 40 seconds.
- `I don't need help.` does not create a case.
- Employee thread reply acknowledges a case with `response_source=thread_reply`.
- Employee top-level channel reply can acknowledge a case with `response_source=ai_channel_match`.
- Unrelated employee channel messages do not close cases.

## Dashboard

The dashboard shows:

- Total cases.
- Open cases.
- Acknowledged cases.
- Breached cases.
- SLA compliance rate.
- Average first response time.
- Sentiment icon and label.
- Priority.
- Case status.
- Due time.
- First response time.
- Response source.
- AI reason.
- Case detail timeline.

## Useful Scripts

- `setup.ps1`: create venv, install dependencies, initialize database.
- `run_bot.ps1`: start the Slack bot.
- `run_dashboard.ps1`: start Streamlit dashboard.
- `find_slack_ids.ps1`: list Slack channel and user IDs.
- `clear_demo_data.ps1`: remove seeded `SLA-DEMO-*` data.
- `scripts/test_ai_classifier.py`: test Gemini classification and response matching.
- `scripts/seed_demo_data.py`: insert sample dashboard data.
- `scripts/init_db.py`: initialize or migrate SQLite.

## Security Notes

- Never commit `.env`, Slack tokens, Gemini keys, or local databases.
- `.gitignore` excludes `.env`, `.venv`, `sla_bot.db`, and SQLite files.
- If a token is accidentally exposed, rotate it in Slack or Google AI Studio.
- The dashboard does not display API keys.
- The database stores message text needed for the demo; avoid using sensitive real customer data.

## Troubleshooting

- Bot does not connect:
  - Check `SLACK_APP_TOKEN` starts with `xapp-`.
  - Confirm Socket Mode is enabled.
  - Confirm the app-level token has `connections:write`.

- Bot cannot post:
  - Check `SLACK_BOT_TOKEN` starts with `xoxb-`.
  - Confirm `chat:write` scope.
  - Reinstall the Slack app after changing scopes.
  - Invite the bot to the target channels.

- Bot does not receive messages:
  - Confirm event subscriptions include `message.channels` and `message.groups`.
  - Confirm the bot is invited to the channel.
  - Confirm customer/support user IDs in `.env`.

- Gemini returns fallback:
  - Run `python scripts/test_ai_classifier.py`.
  - Confirm `GEMINI_API_KEY` is set.
  - Confirm `GEMINI_MODEL=gemini-flash-latest`.
  - Restart the bot after changing `.env`.

- Dashboard is empty:
  - Create cases through Slack or run `python scripts/seed_demo_data.py`.
  - Confirm bot and dashboard use the same `DATABASE_URL`.

- Warning or breach timing feels late:
  - Set `CHECK_INTERVAL_SECONDS=5`.
  - Restart the bot.

## Known Limitations

- This is a local demo MVP, not a hosted production service.
- Customer/support/manager identities are statically configured.
- Channel routing is configured in `config.yaml`.
- Gemini matching uses a confidence threshold and intentionally avoids closing vague or unrelated messages.
- SQLite is suitable for the demo; production should use a managed database and secret store.
