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
        "pendant_file_url": "VARCHAR(500)",
        "pendant_audio_status": "VARCHAR(32)",
        "pendant_audio_error": "TEXT",
        "pendant_audio_ready_at": "TIMESTAMP",
    }
    with engine.begin() as connection:
        for name, sql_type in columns.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE voice_records ADD COLUMN {name} {sql_type}"))
        if "transcription_status" not in existing:
            connection.execute(
                text("UPDATE voice_records SET transcription_status = 'pending' WHERE transcription_status IS NULL")
            )
        # Existing originals deliberately remain private until an owner asks
        # the server to create a pendant MP3 for them.
        connection.execute(
            text("UPDATE voice_records SET pendant_audio_status = 'unavailable' "
                 "WHERE pendant_audio_status IS NULL")
        )

    inspector = inspect(engine)
    if "heartbeat_events" in inspector.get_table_names():
        heartbeat_columns = {
            column["name"] for column in inspector.get_columns("heartbeat_events")
        }
        if "voice_id" not in heartbeat_columns:
            with engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE heartbeat_events ADD COLUMN voice_id VARCHAR(36)")
                )
        if "delivery_mode" not in heartbeat_columns:
            with engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE heartbeat_events ADD COLUMN delivery_mode VARCHAR(20)")
                )
                connection.execute(
                    text("UPDATE heartbeat_events SET delivery_mode = 'tuya' WHERE delivery_mode IS NULL")
                )
