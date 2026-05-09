# Demo Cases

Use these scenarios to validate the 40-second Slack SLA demo and the Gemini-assisted AI agent behavior.

## Scenario 1: No Immediate Employee Mention

Customer:

```text
Hi team, the dashboard is not refreshing. Can someone help?
```

Expected:

- Case is created.
- Bot does not immediately mention the assigned employee.
- At about 25 seconds, bot mentions the employee in the original thread.
- If no valid response is detected by 40 seconds, the case is breached and escalated.

## Scenario 2: Customer Does Not Need Help

Customer:

```text
I don't need help.
```

Expected:

- Gemini classifies `needs_response=false`.
- No SLA case is created.
- If `GEMINI_API_KEY` is missing, the app falls back to the rule-based classifier and logs the fallback.

## Scenario 3: Negative Urgent Customer Sentiment

Customer:

```text
This is urgent. We are blocked and cannot continue the workflow.
```

Expected:

- Case is created.
- Sentiment is `negative`.
- Priority is `high`.
- Dashboard shows the red angry sentiment icon.
- Warning posts at about 25 seconds.
- Breach and escalation post at about 40 seconds if no response is detected.

## Scenario 4: Employee Replies In Thread

Customer:

```text
The export failed again. Can you check this?
```

Employee thread reply:

```text
Thanks for flagging this. I'm checking it now.
```

Expected:

- Case is acknowledged.
- First response time is recorded.
- `response_source=thread_reply`.

## Scenario 5: Employee Replies In Channel, Not Thread

Customer:

```text
The export failed again. Can you check this?
```

Employee top-level channel message:

```text
I'm checking the export issue now.
```

Expected:

- Gemini compares the employee message with recent open cases in the same channel.
- Matching case is acknowledged when confidence is at least `0.75`.
- `response_source=ai_channel_match`.
- Dashboard shows the case as acknowledged.

## Scenario 6: Employee Unrelated Channel Message

Customer:

```text
The dashboard is not refreshing.
```

Employee top-level channel message:

```text
I will be away for lunch.
```

Expected:

- Gemini does not match this as a valid response.
- Case remains open.
