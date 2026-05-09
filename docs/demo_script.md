# Demo Script

## Prerequisites

- Bot is running with `python app.py`.
- Dashboard is running with `streamlit run dashboard.py`.
- `CHECK_INTERVAL_SECONDS=5` is set for a tight demo loop.
- The Slack app is installed in the test workspace.
- Test users are invited to monitored customer channels and the escalation channel.

## Core Timing

1. Customer top-level message creates a case only when classification says `needs_response=true`.
2. Bot may post a quiet case-created note, but does not immediately mention the assigned employee.
3. Around 25 seconds, bot posts one warning in the original thread and mentions the employee.
4. Around 40 seconds, unresolved cases breach and escalate to the internal alerts channel.

## Scenarios

Use the full scenario list in `DEMO_CASES.md`.

### Fast Live Demo

1. Customer posts:

   ```text
   Hi team, the dashboard is not refreshing. Can someone help?
   ```

2. Show that no immediate employee mention appears.
3. Wait for the 25-second warning mention.
4. Let it breach at 40 seconds and show escalation plus dashboard status.
5. Customer posts:

   ```text
   I don't need help.
   ```

6. Show that no case is created.
7. Customer posts:

   ```text
   The export failed again. Can you check this?
   ```

8. Employee replies in the channel:

   ```text
   I'm checking the export issue now.
   ```

9. Show that Gemini marks the case acknowledged with `response_source=ai_channel_match`.
