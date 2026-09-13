import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite://"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException

from database import Base, SessionLocal, engine
from main import generate_moment, get_timeline, share_moment, unbind_relationship
from models import Moment, Relationship
from schemas import GenerateMomentRequest


class SharedTimelineTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.db.add(Relationship(
            user_a_id="user-a", user_b_id="user-b",
            invite_code="INVITE1", status="active",
        ))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    @staticmethod
    def ai_result():
        return {
            "title": "共同记录", "summary": "确认后的内容",
            "tags": ["日常"], "suggested_replies": [],
            "safety_flags": [], "ai_status": "generated",
            "schema_version": 1, "prompt_version": "moment-v5",
        }

    def create_moment(self, user_id, event_id, recorded_at):
        request = GenerateMomentRequest(
            user_id=user_id, content=f"{event_id} 的确认内容",
            consent=True, event_id=event_id, recorded_at=recorded_at,
        )
        with patch("main.generate_diary", return_value=self.ai_result()):
            response = generate_moment(request, self.db)
        return self.db.query(Moment).filter(Moment.id == response.data["id"]).one()

    def test_only_owner_can_share_and_shared_timeline_is_sorted(self):
        older = self.create_moment("user-a", "event-old", datetime(2026, 9, 1, 10, 0))
        newer = self.create_moment("user-b", "event-new", datetime(2026, 9, 2, 10, 0))
        private = self.create_moment("user-a", "event-private", datetime(2026, 9, 3, 10, 0))

        with self.assertRaises(HTTPException) as raised:
            share_moment(older.id, "user-b", self.db)
        self.assertEqual(raised.exception.status_code, 403)

        share_moment(older.id, "user-a", self.db)
        share_moment(newer.id, "user-b", self.db)
        older.status = "responded"
        self.db.commit()
        result = get_timeline("user-a", limit=20, offset=0, db=self.db)
        self.assertEqual(result.data["total"], 2)
        self.assertEqual(
            [item["event_id"] for item in result.data["moments"]],
            ["event-new", "event-old"],
        )
        self.assertNotIn(private.id, [item["id"] for item in result.data["moments"]])

    def test_archived_and_unconfirmed_records_are_not_visible(self):
        archived = self.create_moment("user-a", "event-archived", datetime(2026, 9, 2, 10, 0))
        share_moment(archived.id, "user-a", self.db)
        archived.status = "archived"
        unconfirmed = Moment(
            user_id="user-b", event_id="event-unconfirmed", title="草稿",
            status="shared", shared_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        self.db.add(unconfirmed)
        self.db.commit()
        result = get_timeline("user-a", limit=20, offset=0, db=self.db)
        self.assertEqual(result.data["total"], 0)

    def test_timeline_requires_active_relationship(self):
        self.db.query(Relationship).update({"status": "unbound"})
        self.db.commit()
        with self.assertRaises(HTTPException) as raised:
            get_timeline("user-a", db=self.db)
        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.detail["code"], "TIMELINE_RELATIONSHIP_REQUIRED")

    def test_unbind_targets_the_active_relationship_not_old_history(self):
        self.db.query(Relationship).delete()
        self.db.add(Relationship(
            user_a_id="user-a", user_b_id="former-partner",
            invite_code="OLDREL", status="unbound",
        ))
        self.db.add(Relationship(
            user_a_id="user-a", user_b_id="user-b",
            invite_code="ACTIVEREL", status="active",
        ))
        self.db.commit()
        response = unbind_relationship("user-a", self.db)
        self.assertEqual(response["status"], "unbound")
        active = self.db.query(Relationship).filter_by(invite_code="ACTIVEREL").one()
        self.assertEqual(active.status, "unbound")


if __name__ == "__main__":
    unittest.main()
