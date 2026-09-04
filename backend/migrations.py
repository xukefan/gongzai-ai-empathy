"""Small idempotent migrations for the development-to-production database."""

from sqlalchemy import inspect, text


def migrate_schema(engine) -> None:
    inspector = inspect(engine)
    if "voice_records" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("voice_records")}
    columns = {
        "transcript": "TEXT",
        "transcription_status": "VARCHAR(32)",
        "transcription_error": "TEXT",
        "transcription_provider": "VARCHAR(64)",
        "transcription_request_id": "VARCHAR(64)",
        "transcribed_at": "TIMESTAMP",
    }
    with engine.begin() as connection:
        for name, sql_type in columns.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE voice_records ADD COLUMN {name} {sql_type}"))
        if "transcription_status" not in existing:
            connection.execute(
                text("UPDATE voice_records SET transcription_status = 'pending' WHERE transcription_status IS NULL")
            )
