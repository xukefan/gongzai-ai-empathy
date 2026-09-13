"""Add the 4.6.1 life-moment record fields to an existing database.

Run once for development or deployment databases created before this change:

    python migrations/migrate_moment_record_fields.py

The migration is intentionally additive. It does not delete or rewrite older
moment records, and it can be run again safely.
"""

from sqlalchemy import inspect, text

from database import engine


# The DDL types work with the project's SQLite development database and
# PostgreSQL deployment database. All fields are nullable to preserve existing
# moments that were created before the richer record format existed.
MOMENT_COLUMNS = {
    "event_id": "VARCHAR(128)",
    "raw_transcript": "TEXT",
    "confirmed_transcript": "TEXT",
    "source": "VARCHAR(20)",
    "bpm": "INTEGER",
    "recorded_at": "TIMESTAMP",
    "tags": "JSON",
    "suggested_replies": "JSON",
    "safety_flags": "JSON",
    "ai_status": "VARCHAR(30)",
    "prompt_version": "VARCHAR(50)",
    "schema_version": "INTEGER DEFAULT 1",
    "image_urls": "JSON",
    "user_note": "TEXT",
    "shared_at": "TIMESTAMP",
    "acknowledged_at": "TIMESTAMP",
    "reply_voice_id": "VARCHAR(36)",
    "reply_raw_transcript": "TEXT",
    "reply_confirmed_transcript": "TEXT",
    "replied_at": "TIMESTAMP",
}


def migrate() -> list[str]:
    inspector = inspect(engine)
    if "moments" not in inspector.get_table_names():
        raise RuntimeError("moments 表不存在。请先启动一次后端以创建基础表结构。")

    existing = {column["name"] for column in inspector.get_columns("moments")}
    added: list[str] = []
    with engine.begin() as connection:
        for name, ddl_type in MOMENT_COLUMNS.items():
            if name in existing:
                continue
            connection.execute(text(f"ALTER TABLE moments ADD COLUMN {name} {ddl_type}"))
            added.append(name)

        # Existing rows have NULL event_id and remain valid. New AI-generated
        # records use event_id as an idempotency key.
        connection.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_moments_event_id "
            "ON moments (event_id)"
        ))
    return added


if __name__ == "__main__":
    changed = migrate()
    if changed:
        print("Added moment columns: " + ", ".join(changed))
    else:
        print("Moment record schema is already current.")
