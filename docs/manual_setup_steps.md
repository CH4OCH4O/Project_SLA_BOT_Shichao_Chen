# Manual Setup Steps

This guide is for someone who downloads the project zip and wants to deploy the demo in their own Slack workspace.

The setup has four parts:

1. Create Slack channels.
2. Create and configure a Slack app.
3. Create a Gemini API key.
4. Fill in `.env` and `config.yaml`.

## 1. Local Project Setup

Open the unzipped project folder in VS Code.

Run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup.ps1
```

This will:

- Create `.venv`.
- Install Python dependencies.
- Create `.env` from `.env.example` if missing.
- Initialize `sla_bot.db`.

Do not run the bot yet. Finish the Slack and Gemini setup first.

## 2. Create Slack Channels

Create at least three channels in the Slack workspace:

```text
#client-bella-beaut
#client-corewear
#internal-alerts
```

You can use different names, but then update `config.yaml` to match those names exactly without `#`.

Invite these users to the customer channels:

- Customer test user.
- Support / CSM test user.
- Manager test user if desired.
- The Slack bot, after the app is installed.

Invite the Slack bot and manager to the internal alerts channel.

## 3. Create A Slack App

1. Go to [Slack API Apps](https://api.slack.com/apps).
2. Click `Create New App`.
3. Choose `From scratch`.
4. App name: `SLA Reminder Bot` or similar.
5. Select the Slack workspace.
6. Click `Create App`.

## 4. Enable Socket Mode

Socket Mode lets the local Python bot receive Slack events without deploying a public web server.

1. In the Slack app console, open `Socket Mode`.
2. Turn on `Enable Socket Mode`.
3. Slack will ask for an app-level token.
4. Create an app-level token with this scope:

   ```text
   connections:write
   ```

5. Copy the app-level token. It starts with:

   ```text
   xapp-
   ```

6. Put it in `.env`:

   ```env
   SLACK_APP_TOKEN=xapp-...
   ```

## 5. Configure OAuth Bot Scopes

1. In the Slack app console, open `OAuth & Permissions`.
2. Under `Scopes -> Bot Token Scopes`, add:

   ```text
   app_mentions:read
   channels:history
   channels:read
   chat:write
   groups:history
   groups:read
   users:read
   ```

3. Click `Install to Workspace` or `Reinstall to Workspace`.
4. Copy the bot token. It starts with:

   ```text
   xoxb-
   ```

5. Put it in `.env`:

   ```env
   SLACK_BOT_TOKEN=xoxb-...
   ```

Notes:

- `channels:*` scopes are for public channels.
- `groups:*` scopes are for private channels.
- If you only use public channels, `groups:*` is still harmless for the demo if approved.
- After changing scopes, reinstall the Slack app.

## 6. Configure Event Subscriptions

1. In the Slack app console, open `Event Subscriptions`.
2. Turn on `Enable Events`.
3. You do not need to set a Request URL because this project uses Socket Mode.
4. Under `Subscribe to bot events`, add:

   ```text
   message.channels
   message.groups
   app_mention
   ```

5. Save changes.
6. Reinstall the app if Slack asks.

## 7. Invite The Bot To Channels

In Slack, invite the installed bot to each channel:

```text
/invite @YourBotName
```

Do this in:

```text
#client-bella-beaut
#client-corewear
#internal-alerts
```

The bot must be inside a channel before it can read messages or post reminders there.

## 8. Collect Slack IDs

The app needs Slack IDs, not display names.

After setting `SLACK_BOT_TOKEN` in `.env`, run:

```powershell
.\find_slack_ids.ps1
```

Or:

```powershell
python scripts/get_slack_ids.py
```

Copy these values:

- Customer user ID, starts with `U`.
- Support user ID, starts with `U`.
- Manager user ID, starts with `U`.
- Internal alerts channel ID, starts with `C`.

Put them in `.env`:

```env
SLACK_ESCALATION_CHANNEL_ID=C...
MANAGER_USER_ID=U...
SUPPORT_USER_ID=U...
CUSTOMER_USER_ID=U...
```

## 9. Create A Gemini API Key

Gemini is used for:

- Customer message classification.
- Sentiment classification.
- Priority classification.
- Short AI reason.
- Matching employee top-level channel replies to recent open cases.

Steps:

1. Go to [Google AI Studio](https://aistudio.google.com/).
2. Sign in with a Google account.
3. Open `Get API key` or `API keys`.
4. Create a new API key.
5. Copy the key.
6. Add it to `.env`:

   ```env
   GEMINI_API_KEY=your_key_here
   GEMINI_MODEL=gemini-flash-latest
   ```

Test Gemini:

```powershell
python scripts/test_ai_classifier.py
```

Expected successful output includes:

```text
'classifier_source': 'gemini'
```

If Gemini is missing or unavailable, the app still runs. It will log a fallback message and use rule-based customer classification. AI channel matching will not auto-acknowledge cases.

## 10. Configure `.env`

Final `.env` should look like this:

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

Important:

- Do not upload `.env` to GitHub.
- Restart the bot after changing `.env`.
- `CHECK_INTERVAL_SECONDS=5` is recommended for accurate 25-second warning and 40-second breach behavior.

## 11. Configure `config.yaml`

If `config.yaml` does not exist:

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

Rules:

- Channel names must match Slack channel names without `#`.
- `assigned_owner_env` and `manager_env` point to environment variable names in `.env`.
- Add each monitored customer channel under `channels`.
- Add every customer test user under `roles.customer_users`.
- Add every support/manager user under `roles.internal_users`.

## 12. Initialize The Database

Run:

```powershell
python scripts/init_db.py
```

This creates or migrates:

```text
sla_bot.db
```

The database stores:

- Slack messages needed for audit/debugging.
- SLA cases.
- Notification idempotency records.
- User/channel routing metadata.

## 13. Run The Bot And Dashboard

Terminal 1:

```powershell
.\run_bot.ps1
```

Expected log:

```text
Starting Slack SLA bot...
Starting Slack SLA bot in Socket Mode.
```

Terminal 2:

```powershell
.\run_dashboard.ps1
```

Streamlit should open in the browser.

## 14. Validate The Deployment

### Test 1: Gemini

```powershell
python scripts/test_ai_classifier.py
```

Expected:

```text
'classifier_source': 'gemini'
```

### Test 2: Customer Request

In a monitored customer channel, have the configured customer user send:

```text
Hi team, the dashboard is not refreshing. Can someone help?
```

Expected:

- Case is created.
- Bot does not immediately mention support.
- Dashboard shows an open case.

### Test 3: Warning And Breach

Do not reply.

Expected:

- Around 25 seconds: one warning mention in the original thread.
- Around 40 seconds: breach notice in the thread.
- Internal alerts channel receives escalation.
- Dashboard shows breached status.

### Test 4: Thread Reply

Customer sends:

```text
The export failed again. Can you check this?
```

Support replies in the original thread:

```text
Thanks for flagging this. I'm checking it now.
```

Expected:

- Case becomes acknowledged.
- `response_source=thread_reply`.

### Test 5: AI Channel Match

Customer sends:

```text
The export failed again. Can you check this?
```

Support sends a top-level channel message:

```text
I'm checking the export issue now.
```

Expected:

- Gemini matches the employee message to the open case.
- Case becomes acknowledged.
- `response_source=ai_channel_match`.

## 15. Troubleshooting

### Bot does not connect

- Check `SLACK_APP_TOKEN` starts with `xapp-`.
- Check Socket Mode is enabled.
- Check app-level token has `connections:write`.
- Restart the bot after editing `.env`.

### Bot does not receive messages

- Check event subscriptions include `message.channels`.
- For private channels, check `message.groups`.
- Invite the bot to the channel.
- Confirm the sender is configured as `CUSTOMER_USER_ID` or an internal user.

### Bot cannot post

- Check `SLACK_BOT_TOKEN` starts with `xoxb-`.
- Check `chat:write`.
- Reinstall the Slack app after adding scopes.
- Invite the bot to the channel.

### Escalation does not appear

- Check `SLACK_ESCALATION_CHANNEL_ID`.
- Invite the bot to the internal alerts channel.
- Confirm the open case was not acknowledged before 40 seconds.
- Confirm `CHECK_INTERVAL_SECONDS=5`.

### Gemini falls back to rule-based

- Check `GEMINI_API_KEY`.
- Check `GEMINI_MODEL=gemini-flash-latest`.
- Run `python scripts/test_ai_classifier.py`.
- Restart the bot after changing `.env`.

### Dashboard is empty

- Create a Slack case through the bot, or run:

  ```powershell
  python scripts/seed_demo_data.py
  ```

- Confirm bot and dashboard use the same `DATABASE_URL`.

## 16. Security Checklist Before Uploading To GitHub

Before publishing:

- Do not include `.env`.
- Do not include `sla_bot.db`.
- Do not include `.venv`.
- Do not include real Slack or Gemini tokens in screenshots, docs, or commits.
- If a token was exposed, rotate it in Slack or Google AI Studio.

The included `.gitignore` excludes these local files.
