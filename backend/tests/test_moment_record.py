import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Use an isolated in-memory database before backend modules are imported.
os.environ["DATABASE_URL"] = "sqlite://"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException

from config import Config

Config.DATABASE_URL = "sqlite://"

from database import Base, SessionLocal, engine
from main import generate_moment
from models import VoiceRecord
from schemas import GenerateMomentRequest


class MomentRecordTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    @staticmethod
    def ai_result():
        return {
            "title": "答辩结束后的记录",
            "summary": "今天答辩结束后感到轻松。",
            "tags": ["答辩", "学习"],
            "suggested_replies": ["辛苦了，结束了就好。"],
            "safety_flags": [],
            "ai_status": "generated",
            "schema_version": 1,
            "prompt_version": "moment-v5",
        }

    def test_confirmed_moment_persists_complete_record(self):
        voice = VoiceRecord(user_id="user-a", file_url="voice.wav", duration=12)
        self.db.add(voice)
        self.db.commit()
        self.db.refresh(voice)

        request = GenerateMomentRequest(
            user_id="user-a",
            content="今天答辩终于结束了，现在松了一口气。",
            raw_transcript="今天答辩终于结束了现在松了一口气",
            consent=True,
            event_id="event-001",
            voice_id=voice.id,
            source="watch",
            bpm=82,
            image_urls=["https://example.test/image-1.jpg"],
            user_note="答辩结束后记录",
        )
        with patch("main.generate_diary", return_value=self.ai_result()):
            response = generate_moment(request, self.db)

        record = response.data
        self.assertEqual(record["event_id"], "event-001")
        self.assertEqual(record["raw_transcript"], "今天答辩终于结束了现在松了一口气")
        self.assertEqual(record["confirmed_transcript"], request.content)
        self.assertEqual(record["raw_text"], request.content)
        self.assertEqual(record["voice_id"], voice.id)
        self.assertEqual(record["bpm"], 82)
        self.assertEqual(record["tags"], ["答辩", "学习"])
        self.assertEqual(record["suggested_replies"], ["辛苦了，结束了就好。"])
        self.assertEqual(record["image_urls"], ["https://example.test/image-1.jpg"])
        self.assertEqual(record["idempotent_replay"], False)

    def test_same_event_id_returns_existing_record_without_regeneration(self):
        request = GenerateMomentRequest(
            user_id="user-a", content="确认后的文字", consent=True, event_id="event-002"
        )
        with patch("main.generate_diary", return_value=self.ai_result()) as generate:
            first = generate_moment(request, self.db)
            second = generate_moment(request, self.db)

        self.assertEqual(generate.call_count, 1)
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertTrue(second.data["idempotent_replay"])

    def test_unconfirmed_text_cannot_trigger_ai_generation(self):
        request = GenerateMomentRequest(user_id="user-a", content="尚未确认", consent=False)
        with patch("main.generate_diary") as generate:
            with self.assertRaises(HTTPException) as raised:
                generate_moment(request, self.db)
        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.detail["code"], "AI_CONSENT_REQUIRED")
        generate.assert_not_called()

    def test_cannot_attach_another_users_voice(self):
        voice = VoiceRecord(user_id="user-b", file_url="private.wav", duration=8)
        self.db.add(voice)
        self.db.commit()
        self.db.refresh(voice)
        request = GenerateMomentRequest(
            user_id="user-a", content="确认后的文字", consent=True, voice_id=voice.id
        )
        with patch("main.generate_diary") as generate:
            with self.assertRaises(HTTPException) as raised:
                generate_moment(request, self.db)
        self.assertEqual(raised.exception.status_code, 403)
        generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
