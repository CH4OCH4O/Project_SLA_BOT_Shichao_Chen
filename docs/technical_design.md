# Technical Design

## System Architecture

The MVP is a local Python application with three main parts:

- Slack bot runtime: Slack Bolt in Socket Mode listens to message events and posts case updates.
- SLA engine: local business logic creates cases, tracks responses, sends warnings, and escalates breaches.
- Dashboard: Streamlit reads the same SQLite database and renders manager-facing performance views.

SQLite is the system of record. The bot writes messages, SLA cases, user/channel metadata, and notification history. The dashboard reads from the database.

## Main Components

- `app.py`: Slack event ingestion and routing.
- `ai_classifier.py`: Gemini AI calls, strict JSON parsing, retry, normalization, and fallback handling.
- `classifier.py`: deterministic rule-based fallback classifier.
- `sla_engine.py`: case creation, due time calculation, warning/breach checks, first response recording.
- `slack_client.py`: Slack posting helpers and message copy.
- `database.py`: schema, additive migrations, and query helpers.
- `dashboard.py`: Streamlit dashboard.

## Data Flow

### Customer top-level message

```text
Slack message event
  -> app.py
  -> database.insert_message
  -> ai_classifier.classify_customer_message
       -> Gemini when GEMINI_API_KEY exists
       -> classifier.py fallback when Gemini is unavailable
  -> sla_engine.create_case when needs_response=true
  -> database.create_case
  -> slack_client.post_case_created
```

Important behavior:

- Bot messages are ignored.
- Thread replies from customers do not create new cases.
- Employee/internal top-level messages do not create customer cases.
- Messages such as `I don't need help` should classify as `needs_response=false`.

### Internal thread reply

```text
Slack thread reply event
  -> app.py
  -> database.find_case_by_thread
  -> sla_engine.record_first_response
  -> database.mark_first_response(response_source='thread_reply')
  -> slack_client.post_first_response_recorded
```

### Internal top-level channel reply

```text
Slack top-level message from internal user
  -> app.py
  -> sla_engine.recent_open_cases_for_channel
  -> ai_classifier.match_employee_response_to_case
  -> sla_engine.record_first_response when confidence >= 0.75
  -> database.mark_first_response(response_source='ai_channel_match')
```

Safety constraints:

- Matching only considers open cases in the same Slack channel.
- Matching only considers recent cases within `AI_CHANNEL_MATCH_WINDOW_SECONDS`.
- Match confidence must be at least `0.75`.
- Unrelated or vague employee messages should not close cases.

### Scheduled SLA check

```text
APScheduler interval job
  -> sla_engine.check_open_cases
  -> warning at SLA_DEMO_WARNING_SECONDS
  -> breach/escalation at SLA_DEMO_DUE_SECONDS
  -> database.notifications for idempotency
  -> slack_client warning/escalation posts
```

## SLA Timing Logic

The demo policy compresses the SLA into seconds:

- Case created: due time is `created_at + SLA_DEMO_DUE_SECONDS`.
- Default due time: `40` seconds.
- Default warning time: `25` seconds.
- No immediate employee mention at case creation.
- One warning mention at about 25 seconds.
- Breach and manager escalation at about 40 seconds.

Environment variables:

```env
SLA_DEMO_DUE_SECONDS=40
SLA_DEMO_WARNING_SECONDS=25
CHECK_INTERVAL_SECONDS=5
```

Idempotency:

- Warning notification type: `warning_25s`.
- Breach notification type: `breach_40s`.
- Notification rows are unique by `(case_id, notification_type)`.

## AI Classification

`ai_classifier.py` centralizes all Gemini logic. Gemini calls are not scattered through the codebase.

Customer classification returns:

```json
{
  "needs_response": true,
  "sentiment": "negative",
  "priority": "high",
  "reason": "Customer reports a workflow-blocking issue and asks for help.",
  "classifier_source": "gemini"
}
```

Allowed values:

- `needs_response`: `true` or `false`
- `sentiment`: `positive`, `neutral`, `negative`
- `priority`: `low`, `medium`, `high`
- `classifier_source`: `gemini` or `rule_based`

Employee channel matching returns:

```json
{
  "is_response": true,
  "matched_case_id": "SLA-123",
  "confidence": 0.86,
  "reason": "The employee message refers to checking the export issue.",
  "classifier_source": "gemini"
}
```

Fallback behavior:

- If `GEMINI_API_KEY` is missing, app logs a warning and uses rule-based customer classification.
- If Gemini returns invalid JSON, the app retries once.
- If retry fails, customer classification falls back to rule-based logic.
- Channel-level response matching does not auto-close cases without Gemini.

## Database Schema

Primary tables:

- `messages`: Slack message events for audit/debugging.
- `sla_cases`: one row per tracked customer request.
- `notifications`: sent warning/breach/escalation records and idempotency.
- `users`: local role metadata.
- `channels`: local channel metadata.

Important `sla_cases` fields:

- `case_id`
- `slack_channel_id`
- `slack_channel_name`
- `customer_message_ts`
- `thread_ts`
- `customer_user_id`
- `message_text`
- `assigned_owner_user_id`
- `needs_response`
- `sentiment`
- `priority`
- `ai_reason`
- `classifier_source`
- `status`
- `created_at`
- `due_at`
- `first_response_at`
- `response_time_seconds`
- `response_source`
- `response_match_reason`
- `response_match_confidence`
- `breached`
- `escalated`
- `resolved_at`

`database.init_db()` runs additive migrations for newer columns, so an existing local SQLite file can be upgraded without dropping data.

## Dashboard Design

The dashboard is manager-facing and reads from SQLite.

It shows:

- SLA KPI cards.
- Case queue with sentiment icons, priority, status, due time, first response time, response source, and AI reason.
- Team performance table.
- Case detail panel with classification context and timeline.

Status styles:

- Open: neutral/blue.
- Acknowledged: green.
- Breached: red.
- Near due: yellow/orange.

Sentiment icons:

- Negative: red angry face.
- Positive: green smiling face.
- Neutral: yellow neutral face.

## Configuration

`.env` controls secrets and runtime values:

```env
SLACK_BOT_TOKEN=
SLACK_APP_TOKEN=
SLACK_ESCALATION_CHANNEL_ID=
GEMINI_API_KEY=
GEMINI_MODEL=gemini-flash-latest
MANAGER_USER_ID=
SUPPORT_USER_ID=
CUSTOMER_USER_ID=
DATABASE_URL=sqlite:///sla_bot.db
SLA_DEMO_DUE_SECONDS=40
SLA_DEMO_WARNING_SECONDS=25
AI_CHANNEL_MATCH_WINDOW_SECONDS=600
CHECK_INTERVAL_SECONDS=5
```

`config.yaml` controls channel routing:

```yaml
channels:
  client-bella-beaut:
    assigned_owner_env: SUPPORT_USER_ID
    manager_env: MANAGER_USER_ID

roles:
  customer_users:
    - CUSTOMER_USER_ID
```

## Assumptions

- This is a local demo application.
- Slack workspace/app setup is done manually by a workspace admin or app installer.
- Customer, support, and manager identities are configured through `.env` and `config.yaml`.
- One support owner and one manager are enough for the MVP demo.
- The bot and dashboard run on the same machine and share one SQLite database.

## Limitations

- No hosted production deployment is included.
- No multi-tenant Slack OAuth install flow.
- No CRM or ticketing integration.
- SQLite is local and not intended for concurrent production teams.
- Message text is stored locally for demo/debugging.
- Gemini output is normalized and constrained, but still probabilistic.

## Future Production Considerations

- Deploy bot and dashboard on managed infrastructure.
- Use a managed database.
- Move secrets to a secret manager.
- Add Slack OAuth installation for multiple client workspaces.
- Add admin UI for users, channels, owners, and SLA policies.
- Add audit retention controls for message text.
- Add human review mode for low-confidence AI matches.
