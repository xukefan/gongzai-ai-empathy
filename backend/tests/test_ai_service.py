import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai_service
from ai_prompts import MOMENT_SYSTEM_PROMPT, PROMPT_VERSION
from config import Config


class AIServiceTests(unittest.TestCase):
    def test_title_prompt_is_constrained_for_faithful_short_output(self):
        self.assertEqual(PROMPT_VERSION, "moment-v5")
        self.assertIn("6 至 20 个中文字符", MOMENT_SYSTEM_PROMPT)
        self.assertIn("不输出候选列表", MOMENT_SYSTEM_PROMPT)
        self.assertIn("不补充原文没有的情绪", MOMENT_SYSTEM_PROMPT)

    def test_summary_prompt_preserves_modality_and_negation(self):
        self.assertIn("还没完成", MOMENT_SYSTEM_PROMPT)
        self.assertIn("可能会去", MOMENT_SYSTEM_PROMPT)
        self.assertIn("计划写成事实", MOMENT_SYSTEM_PROMPT)
        self.assertIn("明确说出的情绪可以如实保留", MOMENT_SYSTEM_PROMPT)

    def test_tag_prompt_only_allows_explicit_topics(self):
        self.assertIn("只能概括原文明确出现的主题", MOMENT_SYSTEM_PROMPT)
        self.assertIn("不得从 BPM、语气、常识", MOMENT_SYSTEM_PROMPT)
        self.assertIn("返回空数组", MOMENT_SYSTEM_PROMPT)

    def test_reply_prompt_is_optional_non_diagnostic_and_safe(self):
        self.assertIn("0 至 3 条可选回复草稿", MOMENT_SYSTEM_PROMPT)
        self.assertIn("不能自动发送", MOMENT_SYSTEM_PROMPT)
        self.assertIn("不提供医疗、法律或危机处置指导", MOMENT_SYSTEM_PROMPT)
        self.assertIn("高风险、自伤、他伤或急性身体不适内容时必须返回空数组", MOMENT_SYSTEM_PROMPT)

    def test_model_replies_are_deduplicated_and_limited(self):
        response = json.dumps({
            "title": "record", "summary": "a record", "tags": [],
            "suggested_replies": ["辛苦了", "辛苦了", "x" * 250, "如果你愿意，可以聊聊", "extra"],
            "safety_flags": [],
        })
        with patch.object(Config, "AI_API_KEY", "test-key"), patch.object(
            ai_service, "_request_model", return_value=response
        ):
            result = ai_service.generate_diary("今天完成了答辩")
        self.assertEqual(result["suggested_replies"], ["辛苦了", "x" * 200, "如果你愿意，可以聊聊"])

    def test_truncation_cannot_create_duplicate_replies_or_tags(self):
        response = json.dumps({
            "title": "record", "summary": "a record",
            "tags": ["y" * 21, "y" * 20],
            "suggested_replies": ["z" * 201, "z" * 200],
            "safety_flags": [],
        })
        with patch.object(Config, "AI_API_KEY", "test-key"), patch.object(
            ai_service, "_request_model", return_value=response
        ):
            result = ai_service.generate_diary("今天完成了答辩")
        self.assertEqual(result["tags"], ["y" * 20])
        self.assertEqual(result["suggested_replies"], ["z" * 200])

    def test_model_tags_are_deduplicated_and_limited(self):
        response = json.dumps({
            "title": "record", "summary": "a record",
            "tags": ["学习", "学习", "x" * 30, "跑步", "地点", "extra"],
            "suggested_replies": [], "safety_flags": [],
        })
        with patch.object(Config, "AI_API_KEY", "test-key"), patch.object(
            ai_service, "_request_model", return_value=response
        ):
            result = ai_service.generate_diary("学习和跑步")
        self.assertEqual(result["tags"], ["学习", "x" * 20, "跑步", "地点", "extra"])

    def test_fallback_summary_does_not_add_bpm_interpretation(self):
        with patch.object(Config, "AI_API_KEY", None):
            result = ai_service.generate_diary("今天完成了慢跑。", bpm=180)
        self.assertEqual(result["summary"], "今天完成了慢跑。")
        self.assertNotIn("BPM", result["summary"])

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
