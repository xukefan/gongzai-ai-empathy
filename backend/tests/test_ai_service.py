import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai_service
from config import Config


class AIServiceTests(unittest.TestCase):
    def test_without_key_returns_complete_fallback_schema(self):
        with patch.object(Config, "AI_API_KEY", None):
            result = ai_service.generate_diary("walk with a friend")
        self.assertEqual(result["ai_status"], "fallback")
        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(result["tags"], ["\u751f\u6d3b\u7247\u6bb5"])
        self.assertEqual(result["suggested_replies"], [])
        self.assertEqual(result["safety_flags"], [])
        self.assertIn("title", result)
        self.assertIn("summary", result)

    def test_valid_model_json_is_normalized(self):
        response = json.dumps({
            "title": "walk", "summary": "walk with a friend",
            "tags": ["friend", "outdoors"],
            "suggested_replies": ["sounds nice"], "safety_flags": [],
        })
        with patch.object(Config, "AI_API_KEY", "test-key"), patch.object(
            ai_service, "_request_model", return_value=response
        ):
            result = ai_service.generate_diary("walk with a friend")
        self.assertEqual(result["ai_status"], "generated")
        self.assertEqual(result["tags"], ["friend", "outdoors"])
        self.assertEqual(result["suggested_replies"], ["sounds nice"])

    def test_markdown_json_is_accepted(self):
        response = "```json\n{\"title\": \"entry\", \"summary\": \"a record\"}\n```"
        with patch.object(Config, "AI_API_KEY", "test-key"), patch.object(
            ai_service, "_request_model", return_value=response
        ):
            result = ai_service.generate_diary("a record")
        self.assertEqual(result["title"], "entry")
        self.assertEqual(result["tags"], [])

    def test_invalid_json_is_retried_once(self):
        with patch.object(Config, "AI_API_KEY", "test-key"), patch.object(
            ai_service, "_request_model",
            side_effect=["invalid response", '{"title":"fixed","summary":"result"}'],
        ) as request:
            result = ai_service.generate_diary("source text")
        self.assertEqual(request.call_count, 2)
        self.assertEqual(result["title"], "fixed")

    def test_two_invalid_responses_raise_after_one_retry(self):
        with patch.object(Config, "AI_API_KEY", "test-key"), patch.object(
            ai_service, "_request_model", side_effect=["bad", "still bad"]
        ) as request:
            with self.assertRaises(ai_service.AIServiceError) as error:
                ai_service.generate_diary("source text")
        self.assertEqual(request.call_count, 2)
        self.assertIn("\u5df2\u91cd\u8bd5\u4e00\u6b21", str(error.exception))

    def test_high_risk_content_is_flagged_and_has_no_reply_draft(self):
        response = json.dumps({
            "title": "attention", "summary": "needs review",
            "suggested_replies": ["please do not worry"], "safety_flags": [],
        })
        with patch.object(Config, "AI_API_KEY", "test-key"), patch.object(
            ai_service, "_request_model", return_value=response
        ):
            result = ai_service.generate_diary("\u6211\u4e0d\u60f3\u6d3b\u4e86")
        self.assertIn("high_risk_content_review", result["safety_flags"])
        self.assertEqual(result["suggested_replies"], [])

    def test_bpm_is_background_only(self):
        captured = {}
        def fake_request(endpoint, headers, payload):
            captured["payload"] = payload
            return '{"title":"run","summary":"completed a run"}'
        with patch.object(Config, "AI_API_KEY", "test-key"), patch.object(
            ai_service, "_request_model", side_effect=fake_request
        ):
            result = ai_service.generate_diary("completed a run", bpm=120)
        prompt = captured["payload"]["messages"][0]["content"]
        context = captured["payload"]["messages"][1]["content"]
        self.assertIn("BPM", prompt)
        self.assertIn("safety_flags", prompt)
        self.assertIn("BPM", context)
        self.assertNotIn("diagnosis", result["summary"].lower())


if __name__ == "__main__":
    unittest.main()
