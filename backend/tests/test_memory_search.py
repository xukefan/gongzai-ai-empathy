import os
import sys
import unittest
from datetime import datetime
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite://"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException

from database import Base, SessionLocal, engine
from main import search_shared_memories
from models import Moment, Relationship


class MemorySearchTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.db.add(Relationship(
            user_a_id="user-a", user_b_id="user-b", invite_code="SEARCH1", status="active"
        ))
        self.db.add_all([
            self.moment("event-defense", "user-a", "答辩结束", "今天答辩结束，终于松了一口气。", ["答辩", "学习"], 9),
            self.moment("event-running", "user-b", "夜跑", "晚上完成了夜跑。", ["运动"], 10),
            self.moment("event-private", "user-a", "私密草稿", "答辩草稿不能分享。", ["答辩"], 11, "active"),
            self.moment("event-outsider", "user-c", "外部记录", "答辩相关的外部私有记录。", ["答辩"], 12),
        ])
        self.db.commit()

    @staticmethod
    def moment(event_id, user_id, title, transcript, tags, hour, status="shared"):
        recorded_at = datetime(2026, 9, 16, hour)
        return Moment(
            event_id=event_id, user_id=user_id, title=title, summary=transcript,
            confirmed_transcript=transcript, tags=tags, status=status,
            recorded_at=recorded_at, shared_at=recorded_at if status == "shared" else None,
        )

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    def test_search_returns_only_shared_partner_records_with_source_fields(self):
        response = search_shared_memories("user-b", "找答辩结束后的片段", 20, self.db)
        data = response.data
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["results"][0]["event_id"], "event-defense")
        self.assertIn("confirmed_transcript", data["results"][0])
        self.assertIn("tags", data["results"][0]["matched_fields"])
        self.assertEqual(data["search_method"], "local_lexical_semantic_v1")

    def test_search_accepts_explicit_tags_and_rejects_invalid_input(self):
        response = search_shared_memories("user-a", "运动", 20, self.db)
        self.assertEqual(response.data["results"][0]["event_id"], "event-running")
        with self.assertRaises(HTTPException) as raised:
            search_shared_memories("user-a", "", 20, self.db)
        self.assertEqual(raised.exception.status_code, 422)

    def test_search_requires_active_relationship(self):
        self.db.query(Relationship).update({"status": "unbound"})
        self.db.commit()
        with self.assertRaises(HTTPException) as raised:
            search_shared_memories("user-a", "答辩", 20, self.db)
        self.assertEqual(raised.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
