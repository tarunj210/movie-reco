from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


BASE_DIR = Path(__file__).resolve().parents[1]

APP_ENV_FILE = os.getenv("APP_ENV_FILE", ".env.local")
ENV_FILE = BASE_DIR / APP_ENV_FILE

load_dotenv(ENV_FILE, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(f"DATABASE_URL is not set in {ENV_FILE}")

engine = create_engine(DATABASE_URL)


def init_feedback_tables() -> None:
    with engine.begin() as conn:
        print("Creating interaction_events table if not exists...")

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS interaction_events (
                id BIGSERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                movie_id INTEGER,
                event_type VARCHAR(50) NOT NULL,
                event_value FLOAT,
                source VARCHAR(100),
                rank INTEGER,
                event_metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_interaction_events_user_id
            ON interaction_events(user_id);
        """))

        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_interaction_events_movie_id
            ON interaction_events(movie_id);
        """))

        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_interaction_events_event_type
            ON interaction_events(event_type);
        """))

        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_interaction_events_created_at
            ON interaction_events(created_at);
        """))

        print("Creating user_profile_summary table if not exists...")

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_profile_summary (
                user_id INTEGER PRIMARY KEY,
                preferred_genres JSONB DEFAULT '[]'::jsonb,
                preferred_directors JSONB DEFAULT '[]'::jsonb,
                preferred_keywords JSONB DEFAULT '[]'::jsonb,
                recent_movie_ids JSONB DEFAULT '[]'::jsonb,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

    print("Feedback tables initialized successfully.")


if __name__ == "__main__":
    init_feedback_tables()