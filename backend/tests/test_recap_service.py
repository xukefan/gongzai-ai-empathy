import os
import sys
import unittest
from datetime import date, datetime
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite://"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException

from database import Base, SessionLocal, engine
from main import get_recap
from models import Moment, Relationship


class RecapServiceTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.db.add(Relationship(
            user_a_id="user-a", user_b_id="user-b", invite_code="RECAP1", status="active"
        ))
        self.db.add_all([
            self.moment("event-2026-09-15", "user-a", datetime(2026, 9, 15, 9), ["学习", "答辩"]),
            self.moment("event-2026-09-16", "user-b", datetime(2026, 9, 16, 18), ["学习"]),
            self.moment("event-2025-09-15", "user-a", datetime(2025, 9, 15, 11), ["旅行"]),
            self.moment("event-archived", "user-b", datetime(2026, 9, 16, 20), ["不应出现"], "archived"),
            self.moment("event-outsider", "user-c", datetime(2026, 9, 16, 21), ["私有"]),
        ])
        self.db.commit()

    @staticmethod
    def moment(event_id, user_id, recorded_at, tags, status="shared"):
        return Moment(
            event_id=event_id,
            user_id=user_id,
            title=event_id,
            summary=f"{event_id} 的摘要",
            confirmed_transcript=f"{event_id} 的确认转写",
            recorded_at=recorded_at,
            shared_at=recorded_at,
            status=status,
            tags=tags,
        )

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    def test_weekly_recap_only_uses_visible_moments_and_explicit_tags(self):
        recap = get_recap("week", "user-a", date(2026, 9, 16), self.db)
        data = recap.data
        self.assertEqual(data["total_moments"], 2)
        self.assertEqual(data["source_event_ids"], ["event-2026-09-16", "event-2026-09-15"])
        self.assertEqual(data["topics"], [{"tag": "学习", "count": 2}, {"tag": "答辩", "count": 1}])
        self.assertNotIn("event-archived", data["source_event_ids"])
        self.assertNotIn("event-outsider", data["source_event_ids"])
        self.assertEqual(data["generation_method"], "deterministic_fact_aggregation")

    def test_anniversary_recap_matches_month_and_day_across_years(self):
        recap = get_recap("anniversary", "user-b", date(2026, 9, 15), self.db)
        self.assertEqual(recap.data["total_moments"], 2)
        self.assertEqual(
            recap.data["source_event_ids"], ["event-2026-09-15", "event-2025-09-15"]
        )
        self.assertIsNone(recap.data["period_start"])

    def test_monthly_recap_uses_a_calendar_month_window(self):
        recap = get_recap("month", "user-a", date(2026, 9, 16), self.db)
        self.assertEqual(recap.data["period_start"], "2026-09-01T00:00:00")
        self.assertEqual(recap.data["period_end"], "2026-10-01T00:00:00")
        self.assertEqual(recap.data["total_moments"], 2)

    def test_anniversary_requires_anchor_date_and_access_requires_relationship(self):
        with self.assertRaises(HTTPException) as missing_date:
            get_recap("anniversary", "user-a", None, self.db)
        self.assertEqual(missing_date.exception.status_code, 422)

        self.db.query(Relationship).update({"status": "unbound"})
        self.db.commit()
        with self.assertRaises(HTTPException) as unbound:
            get_recap("month", "user-a", date(2026, 9, 16), self.db)
        self.assertEqual(unbound.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
