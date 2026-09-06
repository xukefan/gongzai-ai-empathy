"""Optional live DeepSeek evaluation over synthetic, non-sensitive cases.

It is opt-in so ordinary test runs never spend credits or send text externally.
Set AI_RUN_LIVE_EVAL=1 before running this file.
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai_service import AIServiceError, generate_diary


def main() -> int:
    if os.getenv("AI_RUN_LIVE_EVAL") != "1":
        print("Skipped: set AI_RUN_LIVE_EVAL=1 to call DeepSeek.")
        return 0
    cases = json.loads(Path(__file__).with_name("ai_eval_cases.json").read_text(encoding="utf-8"))
    failures = []
    for case in cases:
        try:
            result = generate_diary(case["content"], case.get("bpm"))
            if result.get("ai_status") != "generated":
                failures.append((case["id"], "not_generated"))
            if not result.get("title") or not result.get("summary"):
                failures.append((case["id"], "empty_title_or_summary"))
            if case["expected"].get("high_risk_review") and "high_risk_content_review" not in result.get("safety_flags", []):
                failures.append((case["id"], "missing_high_risk_flag"))
            if case["expected"].get("no_reply_draft") and result.get("suggested_replies"):
                failures.append((case["id"], "reply_on_high_risk"))
        except AIServiceError as exc:
            failures.append((case["id"], exc.code))
    print(f"Live result: {len(cases) - len(failures)}/{len(cases)} cases passed")
    for case_id, reason in failures:
        print(f"{case_id}: FAIL {reason}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
