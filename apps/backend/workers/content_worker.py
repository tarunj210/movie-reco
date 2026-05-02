from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# Make app imports work when running:
# python workers/content_worker.py
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from app.recommenders.content_recommender import ContentRecommender


APP_ENV_FILE = os.getenv("APP_ENV_FILE", ".env.local")
ENV_FILE = BASE_DIR / APP_ENV_FILE

load_dotenv(ENV_FILE, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(f"DATABASE_URL is not set in {ENV_FILE}")

CONTENT_WORKER_POLL_SECONDS = int(os.getenv("CONTENT_WORKER_POLL_SECONDS", "10"))
CONTENT_WORKER_BATCH_SIZE = int(os.getenv("CONTENT_WORKER_BATCH_SIZE", "5"))
CONTENT_RECS_TOP_K = int(os.getenv("CONTENT_RECS_TOP_K", "50"))

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def load_movies(engine: Engine) -> pd.DataFrame:
    query = text("""
        SELECT *
        FROM movies_enriched
    """)

    return pd.read_sql(query, engine)


def fetch_pending_jobs(engine: Engine, limit: int) -> list[dict]:
    query = text("""
        SELECT
            id,
            user_id,
            feedback_count
        FROM content_refresh_jobs
        WHERE status = 'pending'
        ORDER BY created_at ASC
        LIMIT :limit
    """)

    with engine.begin() as conn:
        rows = conn.execute(query, {"limit": limit}).mappings().all()

    return [dict(row) for row in rows]


def mark_job_running(engine: Engine, job_id: int) -> None:
    query = text("""
        UPDATE content_refresh_jobs
        SET status = 'running',
            started_at = CURRENT_TIMESTAMP
        WHERE id = :job_id
    """)

    with engine.begin() as conn:
        conn.execute(query, {"job_id": job_id})


def mark_job_completed(engine: Engine, job_id: int) -> None:
    query = text("""
        UPDATE content_refresh_jobs
        SET status = 'completed',
            finished_at = CURRENT_TIMESTAMP,
            error_message = NULL
        WHERE id = :job_id
    """)

    with engine.begin() as conn:
        conn.execute(query, {"job_id": job_id})


def mark_job_failed(engine: Engine, job_id: int, error_message: str) -> None:
    query = text("""
        UPDATE content_refresh_jobs
        SET status = 'failed',
            finished_at = CURRENT_TIMESTAMP,
            error_message = :error_message
        WHERE id = :job_id
    """)

    with engine.begin() as conn:
        conn.execute(
            query,
            {
                "job_id": job_id,
                "error_message": error_message[:2000],
            },
        )


def get_user_content_profile_movie_ids(
    engine: Engine,
    user_id: int,
) -> tuple[list[int], list[int], list[int], list[int]]:
    """
    Returns:
    - historical_positive_movie_ids: from ratings table, rating >= 4
    - feedback_positive_movie_ids: from user_movie_feedback, liked or rating >= 4
    - feedback_negative_movie_ids: from user_movie_feedback, disliked or rating <= 2
    - seen_movie_ids: all movies from ratings + all movies from user_movie_feedback
    """

    historical_positive_query = text("""
        SELECT movieid
        FROM ratings
        WHERE userid = :user_id
          AND rating >= 4.0
    """)

    historical_seen_query = text("""
        SELECT movieid
        FROM ratings
        WHERE userid = :user_id
    """)

    feedback_query = text("""
        SELECT
            movie_id,
            rating,
            liked,
            disliked
        FROM user_movie_feedback
        WHERE user_id = :user_id
    """)

    with engine.begin() as conn:
        historical_positive_rows = conn.execute(
            historical_positive_query,
            {"user_id": user_id},
        ).mappings().all()

        historical_seen_rows = conn.execute(
            historical_seen_query,
            {"user_id": user_id},
        ).mappings().all()

        feedback_rows = conn.execute(
            feedback_query,
            {"user_id": user_id},
        ).mappings().all()

    historical_positive_movie_ids = sorted(
        {int(row["movieid"]) for row in historical_positive_rows}
    )

    historical_seen_movie_ids = {
        int(row["movieid"]) for row in historical_seen_rows
    }

    feedback_positive_movie_ids: set[int] = set()
    feedback_negative_movie_ids: set[int] = set()
    feedback_seen_movie_ids: set[int] = set()

    for row in feedback_rows:
        movie_id = int(row["movie_id"])
        rating = row["rating"]
        liked = bool(row["liked"])
        disliked = bool(row["disliked"])

        feedback_seen_movie_ids.add(movie_id)

        rating_value = None
        if rating is not None:
            rating_value = float(rating)

        if liked or (rating_value is not None and rating_value >= 4.0):
            feedback_positive_movie_ids.add(movie_id)

        if disliked or (rating_value is not None and rating_value <= 2.0):
            feedback_negative_movie_ids.add(movie_id)

    seen_movie_ids = sorted(historical_seen_movie_ids | feedback_seen_movie_ids)

    return (
        historical_positive_movie_ids,
        sorted(feedback_positive_movie_ids),
        sorted(feedback_negative_movie_ids),
        seen_movie_ids,
    )


def save_user_content_candidates(
    engine: Engine,
    user_id: int,
    job_id: int,
    recommendations: list,
) -> None:
    delete_query = text("""
        DELETE FROM user_content_candidates
        WHERE user_id = :user_id
    """)

    insert_query = text("""
        INSERT INTO user_content_candidates (
            user_id,
            movie_id,
            score,
            source_movie_ids,
            reason,
            run_id,
            generated_at
        )
        VALUES (
            :user_id,
            :movie_id,
            :score,
            CAST(:source_movie_ids AS jsonb),
            :reason,
            :run_id,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (user_id, movie_id)
        DO UPDATE SET
            score = EXCLUDED.score,
            source_movie_ids = EXCLUDED.source_movie_ids,
            reason = EXCLUDED.reason,
            run_id = EXCLUDED.run_id,
            generated_at = CURRENT_TIMESTAMP
    """)

    with engine.begin() as conn:
        conn.execute(delete_query, {"user_id": user_id})

        for rec in recommendations:
            conn.execute(
                insert_query,
                {
                    "user_id": user_id,
                    "movie_id": rec.movie_id,
                    "score": rec.score,
                    "source_movie_ids": json.dumps(rec.source_movie_ids),
                    "reason": rec.reason,
                    "run_id": job_id,
                },
            )


def process_job(
    engine: Engine,
    recommender: ContentRecommender,
    job: dict,
) -> None:
    job_id = int(job["id"])
    user_id = int(job["user_id"])

    print(f"Processing content refresh job_id={job_id}, user_id={user_id}")

    mark_job_running(engine, job_id)

    try:
        (
        historical_positive_movie_ids,
        feedback_positive_movie_ids,
        feedback_negative_movie_ids,
        seen_movie_ids,
    ) = get_user_content_profile_movie_ids(
        engine=engine,
        user_id=user_id,
    )
        print(f"Historical positive movies: {historical_positive_movie_ids}")
        print(f"Feedback positive movies: {feedback_positive_movie_ids}")
        print(f"Feedback negative movies: {feedback_negative_movie_ids}")
        print(f"Seen movies to exclude: {seen_movie_ids}")

        recommendations = recommender.generate_from_user_profile(
            historical_positive_movie_ids=historical_positive_movie_ids,
            feedback_positive_movie_ids=feedback_positive_movie_ids,
            feedback_negative_movie_ids=feedback_negative_movie_ids,
            exclude_movie_ids=seen_movie_ids,
            top_k=CONTENT_RECS_TOP_K,
            exclude_feedback_movies_from_generated_candidates=False,
        )

        save_user_content_candidates(
            engine=engine,
            user_id=user_id,
            job_id=job_id,
            recommendations=recommendations,
        )

        mark_job_completed(engine, job_id)

        print(
            f"Completed content refresh job_id={job_id}. "
            f"Generated {len(recommendations)} candidates."
        )

    except Exception as exc:
        mark_job_failed(engine, job_id, str(exc))
        print(f"Failed content refresh job_id={job_id}: {exc}")
        raise


def run_once() -> None:
    print("Loading movies_enriched from database...")
    movies_df = load_movies(engine)

    print(f"Loaded movies: {len(movies_df):,}")
    print("Building content recommender...")
    recommender = ContentRecommender(movies_df)

    jobs = fetch_pending_jobs(
        engine=engine,
        limit=CONTENT_WORKER_BATCH_SIZE,
    )

    if not jobs:
        print("No pending content refresh jobs.")
        return

    for job in jobs:
        process_job(
            engine=engine,
            recommender=recommender,
            job=job,
        )


def run_forever() -> None:
    print("Starting content worker...")
    print(f"Polling every {CONTENT_WORKER_POLL_SECONDS} seconds")

    print("Loading movies_enriched from database...")
    movies_df = load_movies(engine)

    print(f"Loaded movies: {len(movies_df):,}")
    print("Building content recommender...")
    recommender = ContentRecommender(movies_df)

    while True:
        jobs = fetch_pending_jobs(
            engine=engine,
            limit=CONTENT_WORKER_BATCH_SIZE,
        )

        if not jobs:
            print("No pending jobs.")
        else:
            for job in jobs:
                process_job(
                    engine=engine,
                    recommender=recommender,
                    job=job,
                )

        time.sleep(CONTENT_WORKER_POLL_SECONDS)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process pending jobs once and exit.",
    )

    args = parser.parse_args()

    if args.once:
        run_once()
    else:
        run_forever()


if __name__ == "__main__":
    main()