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
        print("Creating interaction_events table...")

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

        print("Creating user_movie_feedback table...")

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_movie_feedback (
                user_id INTEGER NOT NULL,
                movie_id INTEGER NOT NULL,
                rating FLOAT,
                liked BOOLEAN DEFAULT FALSE,
                disliked BOOLEAN DEFAULT FALSE,
                source VARCHAR(100),
                last_event_type VARCHAR(50),
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, movie_id)
            );
        """))

        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_user_movie_feedback_user_id
            ON user_movie_feedback(user_id);
        """))

        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_user_movie_feedback_movie_id
            ON user_movie_feedback(movie_id);
        """))

        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_user_movie_feedback_liked
            ON user_movie_feedback(liked);
        """))

        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_user_movie_feedback_disliked
            ON user_movie_feedback(disliked);
        """))

        print("Creating content_refresh_jobs table...")

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS content_refresh_jobs (
                id BIGSERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                feedback_count INTEGER NOT NULL DEFAULT 0,
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                finished_at TIMESTAMP,
                error_message TEXT
            );
        """))

        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_content_refresh_jobs_user_id
            ON content_refresh_jobs(user_id);
        """))

        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_content_refresh_jobs_status
            ON content_refresh_jobs(status);
        """))

        print("Creating user_content_candidates table...")

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_content_candidates (
                user_id INTEGER NOT NULL,
                movie_id INTEGER NOT NULL,
                score FLOAT NOT NULL,
                source_movie_ids JSONB,
                reason TEXT,
                run_id BIGINT,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, movie_id)
            );
        """))

        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_user_content_candidates_user_id
            ON user_content_candidates(user_id);
        """))

        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_user_content_candidates_score
            ON user_content_candidates(score);
        """))

        print("Creating retraining_runs table...")

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS retraining_runs (
                id BIGSERIAL PRIMARY KEY,
                run_type VARCHAR(50) NOT NULL,
                status VARCHAR(50) DEFAULT 'pending',
                started_at TIMESTAMP,
                finished_at TIMESTAMP,
                feedback_cutoff TIMESTAMP,
                metrics_json JSONB,
                artifact_uri TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

        print("Creating model_versions table...")

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS model_versions (
                id BIGSERIAL PRIMARY KEY,
                model_name VARCHAR(100) NOT NULL,
                version VARCHAR(100) NOT NULL,
                artifact_uri TEXT NOT NULL,
                metrics_json JSONB,
                is_active BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

    print("Feedback/content refresh tables initialized successfully.")


if __name__ == "__main__":
    init_feedback_tables()