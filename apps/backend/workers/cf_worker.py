from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from app.services.recommendation_cache import (
    invalidate_user_recommendation_cache,
)


# apps/backend
BASE_DIR = Path(__file__).resolve().parents[1]

APP_ENV_FILE = os.getenv("APP_ENV_FILE", ".env.local")
ENV_FILE = BASE_DIR / APP_ENV_FILE

load_dotenv(ENV_FILE, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(f"DATABASE_URL is not set in {ENV_FILE}")

CF_WORKER_POLL_SECONDS = int(os.getenv("CF_WORKER_POLL_SECONDS", "30"))
CF_WORKER_BATCH_SIZE = int(os.getenv("CF_WORKER_BATCH_SIZE", "1"))

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def fetch_pending_jobs(engine: Engine, limit: int) -> list[dict]:
    query = text("""
        SELECT
            id,
            triggered_by_user_id,
            feedback_count,
            status,
            created_at
        FROM collaborative_retrain_jobs
        WHERE status = 'pending'
        ORDER BY created_at ASC
        LIMIT :limit
    """)

    with engine.begin() as conn:
        rows = conn.execute(query, {"limit": limit}).mappings().all()

    return [dict(row) for row in rows]


def mark_job_running(engine: Engine, job_id: int) -> None:
    query = text("""
        UPDATE collaborative_retrain_jobs
        SET
            status = 'running',
            started_at = CURRENT_TIMESTAMP,
            finished_at = NULL,
            error_message = NULL
        WHERE id = :job_id
    """)

    with engine.begin() as conn:
        conn.execute(query, {"job_id": job_id})


def mark_job_completed(
    engine: Engine,
    job_id: int,
    model_version: str,
) -> None:
    query = text("""
        UPDATE collaborative_retrain_jobs
        SET
            status = 'completed',
            finished_at = CURRENT_TIMESTAMP,
            model_version = :model_version,
            error_message = NULL
        WHERE id = :job_id
    """)

    with engine.begin() as conn:
        conn.execute(
            query,
            {
                "job_id": job_id,
                "model_version": model_version,
            },
        )


def mark_job_failed(
    engine: Engine,
    job_id: int,
    error_message: str,
) -> None:
    query = text("""
        UPDATE collaborative_retrain_jobs
        SET
            status = 'failed',
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


def create_model_version(job_id: int) -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"neumf-local-job-{job_id}-{timestamp}"


def run_python_script(
    script_path: Path,
    env: dict[str, str],
) -> None:
    """
    Runs a backend script using the same Python interpreter.

    This avoids import-time issues with train_neumf_existing.py because that
    script creates MODEL_VERSION and output paths from environment variables.
    """

    command = [
        sys.executable,
        str(script_path),
    ]

    print("")
    print("-" * 80)
    print(f"Running script: {script_path.name}")
    print("-" * 80)

    subprocess.run(
        command,
        cwd=str(BASE_DIR),
        env=env,
        check=True,
    )


def process_job(engine: Engine, job: dict) -> None:
    job_id = int(job["id"])
    model_version = create_model_version(job_id)

    model_dir = BASE_DIR / "artifacts" / "models" / model_version

    print("")
    print("=" * 80)
    print(f"Processing collaborative retraining job_id={job_id}")
    print(f"Triggered by user_id={job.get('triggered_by_user_id')}")
    print(f"Feedback count={job.get('feedback_count')}")
    print(f"Model version={model_version}")
    print(f"Model dir={model_dir}")
    print("=" * 80)

    mark_job_running(engine, job_id)

    job_env = os.environ.copy()
    job_env["APP_ENV_FILE"] = APP_ENV_FILE
    job_env["NEUMF_MODEL_VERSION"] = model_version
    job_env["NEUMF_MODEL_DIR"] = str(model_dir)

    try:
        # 1. Build latest retraining dataset from ratings + user_movie_feedback
        run_python_script(
            script_path=BASE_DIR / "scripts" / "build_retraining_dataset.py",
            env=job_env,
        )

        # 2. Train NeuMF using latest_training_interactions.csv
        run_python_script(
            script_path=BASE_DIR / "scripts" / "train_neumf_existing.py",
            env=job_env,
        )

        # 3. Generate user_cf_candidates from the newly trained model artifacts
        run_python_script(
            script_path=BASE_DIR / "scripts" / "generate_cf_candidates_from_model.py",
            env=job_env,
        )
        
        triggered_user_id = job.get("triggered_by_user_id")

        if triggered_user_id is not None:
            invalidate_user_recommendation_cache(
                user_id=int(triggered_user_id),
            )

        # 4. Mark job completed with the real model version
        mark_job_completed(
            engine=engine,
            job_id=job_id,
            model_version=model_version,
        )

        print("")
        print("=" * 80)
        print(f"Completed collaborative retraining job_id={job_id}")
        print(f"Model version={model_version}")
        print("=" * 80)

    except subprocess.CalledProcessError as exc:
        error_message = (
            f"Script failed with exit code {exc.returncode}: "
            f"{' '.join(exc.cmd)}"
        )

        mark_job_failed(
            engine=engine,
            job_id=job_id,
            error_message=error_message,
        )

        print("")
        print(f"Failed collaborative retraining job_id={job_id}")
        print(error_message)

        raise

    except Exception as exc:
        mark_job_failed(
            engine=engine,
            job_id=job_id,
            error_message=str(exc),
        )

        print("")
        print(f"Failed collaborative retraining job_id={job_id}")
        print(f"Error: {exc}")

        raise


def run_once() -> None:
    jobs = fetch_pending_jobs(
        engine=engine,
        limit=CF_WORKER_BATCH_SIZE,
    )

    if not jobs:
        print("No pending collaborative retraining jobs.")
        return

    for job in jobs:
        process_job(engine=engine, job=job)


def run_forever() -> None:
    print("Starting collaborative retraining worker...")
    print(f"Polling every {CF_WORKER_POLL_SECONDS} seconds")

    while True:
        jobs = fetch_pending_jobs(
            engine=engine,
            limit=CF_WORKER_BATCH_SIZE,
        )

        if not jobs:
            print("No pending collaborative retraining jobs.")
        else:
            for job in jobs:
                process_job(engine=engine, job=job)

        time.sleep(CF_WORKER_POLL_SECONDS)


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--once",
        action="store_true",
        help="Process pending collaborative retraining jobs once and exit.",
    )

    args = parser.parse_args()

    if args.once:
        run_once()
    else:
        run_forever()


if __name__ == "__main__":
    main()