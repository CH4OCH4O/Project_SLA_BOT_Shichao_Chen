# Handoff Guide

This guide is the operational handoff for running the Slack SLA Reminder Bot MVP after downloading the project.

For detailed Slack and Gemini setup, use [manual_setup_steps.md](manual_setup_steps.md). For the high-level project overview, use [../README.md](../README.md).

## What The App Does

The app monitors configured customer Slack channels and creates SLA cases for customer messages that require an employee response.

Current demo behavior:

- Case due time: 40 seconds.
- Warning time: 25 seconds.
- No immediate employee mention when the case is created.
- One near-breach warning mention at about 25 seconds.
- Breach and manager escalation at about 40 seconds.
- Gemini classifies customer messages, sentiment, priority, and reason.
- Gemini can match employee top-level channel replies to recent open cases.
- Dashboard shows manager KPIs and case details.

## Main Files

- `app.py`: Slack event handler and bot startup.
- `ai_classifier.py`: Gemini integration and AI fallback handling.
- `classifier.py`: rule-based fallback classifier.
- `sla_engine.py`: SLA timing, warning, breach, first response recording.
- `slack_client.py`: Slack message formatting and posting.
- `database.py`: SQLite schema, migrations, and queries.
- `dashboard.py`: Streamlit dashboard.
- `.env.example`: environment variable template.
- `config.yaml.example`: channel and role routing template.
- `DEMO_CASES.md`: demo scenarios.

## First-Time Setup

1. Unzip the project.
2. Open the project folder in VS Code.
3. Run:

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\setup.ps1
   ```

4. Follow [manual_setup_steps.md](manual_setup_steps.md) to configure:
   - Slack app.
   - Socket Mode.
   - Slack OAuth scopes.
   - Slack event subscriptions.
   - Slack channel/user IDs.
   - Gemini API key.

5. Fill in `.env`.
6. Confirm or edit `config.yaml`.
7. Run:

   ```powershell
   python scripts/init_db.py
   ```

## Required `.env` Values

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

`GEMINI_API_KEY` is recommended. Without it, the app still runs with rule-based customer classification, but AI channel matching will not auto-acknowledge cases.

## Required `config.yaml`

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

Channel names must match Slack channel names without `#`.

## Daily Runbook

Open two VS Code terminals.

Terminal 1:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\run_bot.ps1
```

Terminal 2:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\run_dashboard.ps1
```

Keep both terminals open during the demo.

AI does not need a third terminal. Gemini is called by the bot when Slack events arrive.

## Validation Checklist

### 1. Validate Gemini

```powershell
python scripts/test_ai_classifier.py
```

Expected:

```text
'classifier_source': 'gemini'
```

Also check that the employee channel match test returns:

```text
'is_response': True
'confidence': 0.75 or higher
```

### 2. Validate Slack Bot

Have the configured customer user send this in a monitored channel:

```text
Hi team, the dashboard is not refreshing. Can someone help?
```

Expected:

- Case created.
- No immediate support mention.
- Warning mention appears at about 25 seconds.
- Breach escalation appears at about 40 seconds if support does not reply.

### 3. Validate Thread Reply

Support replies in the original thread:

```text
Thanks for flagging this. I'm checking it now.
```

Expected dashboard result:

```text
status = acknowledged
response_source = thread_reply
```

### 4. Validate AI Channel Match

Support sends a top-level channel message:

```text
I'm checking the export issue now.
```

Expected dashboard result:

```text
status = acknowledged
response_source = ai_channel_match
```

## Dashboard Interpretation

KPI cards:

- Total cases: all SLA cases.
- Open cases: cases waiting for a valid employee response.
- Acknowledged: cases with a detected response.
- Breached: cases that missed the 40-second demo SLA.
- SLA compliance rate: completed cases that did not breach.
- Avg first response: average response time for acknowledged cases.

Case queue:

- Sentiment uses Gemini output.
- Priority uses Gemini output.
- AI reason explains why the customer message did or did not need action.
- Response source shows whether the response was detected by thread reply or AI channel matching.

Case detail:

- Original customer message.
- AI classification result.
- Slack channel.
- Assigned employee.
- Timeline from created to warning to acknowledged or breached.

## Resetting Data

Clear seeded demo data only:

```powershell
.\clear_demo_data.ps1
```

Clear all local case/message/notification history:

```powershell
python -c "import sqlite3; c=sqlite3.connect('sla_bot.db'); c.execute('DELETE FROM notifications'); c.execute('DELETE FROM sla_cases'); c.execute('DELETE FROM messages'); c.commit(); c.close(); print('Cleared all cases and messages.')"
```

Seed dashboard sample data:

```powershell
python scripts/seed_demo_data.py
```

## Troubleshooting

### Bot does not start

- Confirm `.env` exists.
- Confirm `.venv` exists or run `.\setup.ps1`.
- Confirm Python 3.11+ is installed.
- Confirm `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN` are set.

### Bot connects but does not react

- Confirm the bot is invited to the channel.
- Confirm the sender matches `CUSTOMER_USER_ID` for customer messages.
- Confirm support/manager users are listed in `roles.internal_users`.
- Confirm Slack event subscriptions include `message.channels`.

### Warning or breach does not appear

- Confirm `CHECK_INTERVAL_SECONDS=5`.
- Confirm the case is still open.
- Confirm no valid support reply was detected.
- Confirm the bot terminal is still running.

### Gemini is not used

- Run `python scripts/test_ai_classifier.py`.
- Confirm `GEMINI_API_KEY` is set.
- Confirm `GEMINI_MODEL=gemini-flash-latest`.
- Restart the bot after editing `.env`.

### Escalation does not post

- Confirm `SLACK_ESCALATION_CHANNEL_ID` is correct.
- Invite the bot to the escalation channel.
- Confirm `chat:write` scope.
- Reinstall the Slack app after scope changes.

## Security And GitHub Upload

Before uploading to GitHub:

- Do not include `.env`.
- Do not include `.venv`.
- Do not include `sla_bot.db`.
- Do not include screenshots showing real tokens.
- Rotate any exposed Slack or Gemini keys.

The included `.gitignore` excludes common secret and local-runtime files.

## Production Notes

This is a local demo MVP. For production use, consider:

- Hosted deployment for bot and dashboard.
- Managed database instead of SQLite.
- Secret manager instead of `.env`.
- OAuth installation flow for multiple Slack workspaces.
- More flexible user/channel administration.
- Audit controls for storing customer message text.
