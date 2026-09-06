import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai_service
from config import Config


class IntegrationContractTests(unittest.TestCase):
    def test_moment_schema_declares_legacy_and_new_fields(self):
        schema_path = Path(__file__).resolve().parents[2] / "fuwai" / "ai" / "contracts" / "moment.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["schema_version"]["const"], 1)
        self.assertEqual(
            schema["required"],
            ["title", "summary", "tags", "suggested_replies", "safety_flags", "ai_status", "schema_version"],
        )

    def test_confirmed_text_is_the_only_ai_input(self):
        captured = {}

        def fake_request(endpoint, headers, payload):
            captured["payload"] = payload
            return '{"title":"record","summary":"confirmed text"}'

        with patch.object(Config, "AI_API_KEY", "test-key"), patch.object(
            ai_service, "_request_model", side_effect=fake_request
        ):
            ai_service.generate_diary("confirmed text", bpm=82)

        self.assertEqual(captured["payload"]["messages"][1]["content"].split("\n")[0], "confirmed text")
        self.assertIn("BPM", captured["payload"]["messages"][1]["content"])


if __name__ == "__main__":
    unittest.main()
