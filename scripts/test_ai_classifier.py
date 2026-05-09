from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from ai_classifier import classify_customer_message, match_employee_response_to_case


def main() -> None:
    customer_examples = [
        "Hi team, the dashboard is not refreshing. Can someone help?",
        "This is urgent. We are blocked and cannot continue.",
        "Thanks, that solved it.",
        "I don't need help.",
        "No worries, we figured it out.",
    ]
    for text in customer_examples:
        print(text)
        print(classify_customer_message(text))
        print()

    open_cases = [
        {
            "case_id": "101",
            "message_text": "The export failed again. Can you check this?",
            "created_at": "2026-05-09T12:00:00+00:00",
        }
    ]
    print("Employee channel match:")
    print(match_employee_response_to_case("I'm checking the export issue now.", open_cases))


if __name__ == "__main__":
    main()
