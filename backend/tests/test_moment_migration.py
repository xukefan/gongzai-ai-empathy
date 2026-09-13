import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, inspect, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from migrations import migrate_moment_record_fields


class MomentMigrationTests(unittest.TestCase):
    def test_additive_migration_upgrades_an_old_moments_table(self):
        engine = create_engine("sqlite://")
        with engine.begin() as connection:
            connection.execute(text(
                "CREATE TABLE moments ("
                "id VARCHAR(36) PRIMARY KEY, user_id VARCHAR(36), "
                "title VARCHAR(100), summary TEXT, raw_text TEXT, "
                "voice_id VARCHAR(36), status VARCHAR(20), created_at TIMESTAMP)"
            ))

        with patch.object(migrate_moment_record_fields, "engine", engine):
            added = migrate_moment_record_fields.migrate()
            second_run = migrate_moment_record_fields.migrate()

        columns = {column["name"] for column in inspect(engine).get_columns("moments")}
        self.assertIn("event_id", added)
        self.assertIn("confirmed_transcript", added)
        self.assertIn("suggested_replies", added)
        self.assertIn("reply_confirmed_transcript", added)
        self.assertFalse(second_run)
        self.assertTrue({
            "event_id", "raw_transcript", "confirmed_transcript", "bpm",
            "tags", "suggested_replies", "safety_flags", "image_urls",
            "reply_voice_id", "reply_confirmed_transcript", "shared_at",
        }.issubset(columns))


if __name__ == "__main__":
    unittest.main()
