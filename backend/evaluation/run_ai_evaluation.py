"""Run the day-5 offline AI acceptance checks without calling a model provider."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai_service import AIServiceError, generate_diary  # noqa: E402
from config import Config  # noqa: E402


def check_case(case: dict) -> list[str]:
    expected = case["expected"]
    try:
        result = generate_diary(case["content"], case.get("bpm"))
    except AIServiceError:
        return [] if expected.get("raises_error") else ["unexpected_error"]

    failures = []
    if expected.get("raises_error"):
        failures.append("expected_error")
    if expected.get("non_empty_title") and not result.get("title", "").strip():
        failures.append("empty_title")
    if expected.get("non_empty_summary") and not result.get("summary", "").strip():
        failures.append("empty_summary")
    if expected.get("no_safety_flag") and result.get("safety_flags"):
        failures.append("unexpected_safety_flag")
    if expected.get("high_risk_review") and "high_risk_content_review" not in result.get("safety_flags", []):
        failures.append("missing_high_risk_flag")
    if expected.get("no_reply_draft") and result.get("suggested_replies"):
        failures.append("reply_draft_on_high_risk")
    combined_text = f"{result.get('title', '')} {result.get('summary', '')}"
    for term in expected.get("required_terms", []):
        if term not in combined_text:
            failures.append(f"missing_required_term:{term}")
    for term in expected.get("forbidden_terms", []):
        if term in combined_text:
            failures.append(f"invented_or_diagnostic_term:{term}")
    if result.get("schema_version") != 1:
        failures.append("wrong_schema_version")
    if result.get("ai_status") != "fallback":
        failures.append("offline_run_not_fallback")
    return failures


def main() -> int:
    cases_path = Path(__file__).with_name("ai_eval_cases.json")
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    original_key = Config.AI_API_KEY
    Config.AI_API_KEY = None
    try:
        all_failures = {}
        for case in cases:
            failures = check_case(case)
            if failures:
                all_failures[case["id"]] = failures
            status = "PASS" if not failures else "FAIL: " + ", ".join(failures)
            print(f"{case['id']}: {status}")
    finally:
        Config.AI_API_KEY = original_key

    passed = len(cases) - len(all_failures)
    print(f"\nResult: {passed}/{len(cases)} cases passed")
    return 1 if all_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
