import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import deepseek_client
from ai_errors import AIServiceError
from config import Config


class DeepSeekClientTests(unittest.TestCase):
    def test_uses_deepseek_chat_completions_endpoint_and_model(self):
        response = type("Response", (), {
            "status_code": 200,
            "raise_for_status": lambda self: None,
            "json": lambda self: {"choices": [{"message": {"content": '{"title":"x","summary":"y"}'}}]},
        })()
        with patch.object(Config, "AI_API_KEY", "test-key"), patch.object(
            Config, "AI_API_BASE_URL", "https://api.deepseek.com"
        ), patch.object(Config, "AI_MODEL", "deepseek-v4-flash"), patch(
            "deepseek_client.requests.post", return_value=response
        ) as post:
            result = deepseek_client.chat_completion([{"role": "user", "content": "demo"}])

        self.assertIn("/chat/completions", post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs["json"]["model"], "deepseek-v4-flash")
        self.assertEqual(result, '{"title":"x","summary":"y"}')

    def test_timeout_is_retryable_and_does_not_expose_key(self):
        with patch.object(Config, "AI_API_KEY", "super-secret"), patch(
            "deepseek_client.requests.post", side_effect=deepseek_client.requests.Timeout()
        ):
            with self.assertRaises(AIServiceError) as raised:
                deepseek_client.chat_completion([])
        self.assertEqual(raised.exception.code, "AI_TIMEOUT")
        self.assertTrue(raised.exception.retryable)
        self.assertNotIn("super-secret", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
