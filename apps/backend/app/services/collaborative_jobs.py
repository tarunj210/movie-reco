from __future__ import annotations

import os
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


CF_RETRAIN_MIN_FEEDBACK = int(
    os.getenv("CF_RETRAIN_MIN_FEEDBACK", "20")
)


def count_total_explicit_feedback(db: Session) -> int:
    """
    Counts all explicit feedback rows across users.

    This is global, not per-user, because collaborative retraining
    is a model-level/global operation.
    """

    query = text("""
        SELECT COUNT(*) AS feedback_count
        FROM user_movie_feedback
        WHERE rating IS NOT NULL
           OR liked = TRUE
           OR disliked = TRUE
    """)

    result = db.execute(query).scalar_one()
    return int(result)


def get_active_collaborative_retrain_job(
    db: Session,
) -> dict[str, Any] | None:
    """
    Returns pending/running collaborative retrain job if one exists.

    This prevents creating duplicate global retraining jobs.
    """

    query = text("""
        SELECT
            id,
            status,
            feedback_count
        FROM collaborative_retrain_jobs
        WHERE status IN ('pending', 'running')
        ORDER BY created_at DESC
        LIMIT 1
    """)

    row = db.execute(query).mappings().first()

    if not row:
        return None

    return {
        "id": int(row["id"]),
        "status": str(row["status"]),
        "feedback_count": int(row["feedback_count"]),
    }


def get_latest_non_failed_retrain_feedback_count(
    db: Session,
) -> int:
    """
    Returns the highest feedback_count already covered by a previous
    collaborative retraining job.

    Example:
        threshold = 20
        latest completed feedback_count = 20
        current feedback_count = 25
        new feedback = 5
        no new job yet

        current feedback_count = 40
        new feedback = 20
        create new job
    """

    query = text("""
        SELECT COALESCE(MAX(feedback_count), 0) AS latest_feedback_count
        FROM collaborative_retrain_jobs
        WHERE status IN ('pending', 'running', 'completed')
    """)

    result = db.execute(query).scalar_one()
    return int(result)


def should_enqueue_collaborative_retrain_job(
    db: Session,
    current_feedback_count: int,
) -> bool:
    """
    Decides whether a new collaborative retraining job should be created.
    """

    if current_feedback_count < CF_RETRAIN_MIN_FEEDBACK:
        return False

    active_job = get_active_collaborative_retrain_job(db=db)

    if active_job:
        return False

    latest_covered_count = get_latest_non_failed_retrain_feedback_count(
        db=db
    )

    new_feedback_since_last_retrain = (
        current_feedback_count - latest_covered_count
    )

    return new_feedback_since_last_retrain >= CF_RETRAIN_MIN_FEEDBACK


def enqueue_collaborative_retrain_job(
    db: Session,
    triggered_by_user_id: int,
    feedback_count: int,
) -> int:
    """
    Inserts a pending collaborative retraining job.
    """

    query = text("""
        INSERT INTO collaborative_retrain_jobs (
            triggered_by_user_id,
            feedback_count,
            status,
            created_at
        )
        VALUES (
            :triggered_by_user_id,
            :feedback_count,
            'pending',
            CURRENT_TIMESTAMP
        )
        RETURNING id
    """)

    result = db.execute(
        query,
        {
            "triggered_by_user_id": triggered_by_user_id,
            "feedback_count": feedback_count,
        },
    )

    return int(result.scalar_one())


def maybe_enqueue_collaborative_retrain_job(
    db: Session,
    triggered_by_user_id: int,
) -> tuple[bool, int | None, str | None, int]:
    """
    Creates a collaborative retraining job only when the global feedback
    threshold has been crossed.

    Returns:
        job_created, job_id, job_status, current_feedback_count
    """

    current_feedback_count = count_total_explicit_feedback(db=db)

    active_job = get_active_collaborative_retrain_job(db=db)

    if active_job:
        return (
            False,
            active_job["id"],
            active_job["status"],
            current_feedback_count,
        )

    if not should_enqueue_collaborative_retrain_job(
        db=db,
        current_feedback_count=current_feedback_count,
    ):
        return False, None, None, current_feedback_count

    job_id = enqueue_collaborative_retrain_job(
        db=db,
        triggered_by_user_id=triggered_by_user_id,
        feedback_count=current_feedback_count,
    )

    return True, job_id, "pending", current_feedback_count