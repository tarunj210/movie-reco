from __future__ import annotations

import json
import os
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


RATING_EVENT_TYPES = {"movie_rating", "rating"}
LIKE_EVENT_TYPES = {"movie_like", "like"}
DISLIKE_EVENT_TYPES = {"movie_dislike", "dislike", "not_interested", "hide"}

EXPLICIT_FEEDBACK_EVENT_TYPES = (
    RATING_EVENT_TYPES | LIKE_EVENT_TYPES | DISLIKE_EVENT_TYPES
)

CONTENT_REFRESH_MIN_FEEDBACK = int(
    os.getenv("CONTENT_REFRESH_MIN_FEEDBACK", "3")
)


def metadata_as_json(metadata: dict[str, Any] | None) -> str:
    if metadata is None:
        return "{}"

    return json.dumps(metadata)


def log_interaction_event(
    db: Session,
    user_id: int,
    movie_id: int | None,
    event_type: str,
    event_value: float | None = None,
    source: str | None = None,
    rank: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> int:
    q = text("""
        INSERT INTO interaction_events (
            user_id,
            movie_id,
            event_type,
            event_value,
            source,
            rank,
            event_metadata
        )
        VALUES (
            :user_id,
            :movie_id,
            :event_type,
            :event_value,
            :source,
            :rank,
            CAST(:event_metadata AS jsonb)
        )
        RETURNING id
    """)

    result = db.execute(
        q,
        {
            "user_id": user_id,
            "movie_id": movie_id,
            "event_type": event_type,
            "event_value": event_value,
            "source": source,
            "rank": rank,
            "event_metadata": metadata_as_json(metadata),
        },
    )

    return int(result.scalar_one())


def derive_feedback_state(
    event_type: str,
    event_value: float | None,
) -> tuple[bool, float | None, bool, bool]:
    """
    Converts event into latest explicit feedback state.

    Returns:
        should_update_feedback, rating, liked, disliked
    """

    if event_type in RATING_EVENT_TYPES:
        if event_value is None:
            raise ValueError("event_value is required for rating events")

        rating = float(event_value)

        if rating < 0 or rating > 5:
            raise ValueError("rating must be between 0 and 5")

        liked = rating >= 4.0
        disliked = rating <= 2.0

        return True, rating, liked, disliked

    if event_type in LIKE_EVENT_TYPES:
        return True, None, True, False

    if event_type in DISLIKE_EVENT_TYPES:
        return True, None, False, True

    return False, None, False, False


def upsert_user_movie_feedback(
    db: Session,
    user_id: int,
    movie_id: int,
    rating: float | None,
    liked: bool,
    disliked: bool,
    source: str | None,
    last_event_type: str,
) -> None:
    q = text("""
        INSERT INTO user_movie_feedback (
            user_id,
            movie_id,
            rating,
            liked,
            disliked,
            source,
            last_event_type,
            updated_at
        )
        VALUES (
            :user_id,
            :movie_id,
            :rating,
            :liked,
            :disliked,
            :source,
            :last_event_type,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (user_id, movie_id)
        DO UPDATE SET
            rating = COALESCE(EXCLUDED.rating, user_movie_feedback.rating),
            liked = EXCLUDED.liked,
            disliked = EXCLUDED.disliked,
            source = COALESCE(EXCLUDED.source, user_movie_feedback.source),
            last_event_type = EXCLUDED.last_event_type,
            updated_at = CURRENT_TIMESTAMP
    """)

    db.execute(
        q,
        {
            "user_id": user_id,
            "movie_id": movie_id,
            "rating": rating,
            "liked": liked,
            "disliked": disliked,
            "source": source,
            "last_event_type": last_event_type,
        },
    )


def count_user_explicit_feedback(db: Session, user_id: int) -> int:
    """
    Counts latest explicit feedback rows for the user.

    This counts unique movie feedback rows, not raw interaction events.
    """

    q = text("""
        SELECT COUNT(*) AS feedback_count
        FROM user_movie_feedback
        WHERE user_id = :user_id
          AND (
              rating IS NOT NULL
              OR liked = TRUE
              OR disliked = TRUE
          )
    """)

    result = db.execute(q, {"user_id": user_id}).scalar_one()
    return int(result)


def has_active_content_refresh_job(db: Session, user_id: int) -> bool:
    q = text("""
        SELECT EXISTS (
            SELECT 1
            FROM content_refresh_jobs
            WHERE user_id = :user_id
              AND status IN ('pending', 'running')
        )
    """)

    return bool(db.execute(q, {"user_id": user_id}).scalar_one())


def get_latest_non_failed_refresh_feedback_count(
    db: Session,
    user_id: int,
) -> int:
    """
    Returns highest feedback_count already covered by a previous/pending/running job.

    This prevents creating a new content refresh job after every single interaction.
    Example:
      threshold = 3
      feedback_count = 3 -> create job
      feedback_count = 4 -> no new job
      feedback_count = 6 -> create next job
    """

    q = text("""
        SELECT COALESCE(MAX(feedback_count), 0) AS latest_feedback_count
        FROM content_refresh_jobs
        WHERE user_id = :user_id
          AND status IN ('pending', 'running', 'completed')
    """)

    result = db.execute(q, {"user_id": user_id}).scalar_one()
    return int(result)


def should_enqueue_content_refresh(
    db: Session,
    user_id: int,
    feedback_count: int,
) -> bool:
    if feedback_count < CONTENT_REFRESH_MIN_FEEDBACK:
        return False

    if has_active_content_refresh_job(db=db, user_id=user_id):
        return False

    latest_covered_count = get_latest_non_failed_refresh_feedback_count(
        db=db,
        user_id=user_id,
    )

    new_feedback_since_last_refresh = feedback_count - latest_covered_count

    return new_feedback_since_last_refresh >= CONTENT_REFRESH_MIN_FEEDBACK


def enqueue_content_refresh_job(
    db: Session,
    user_id: int,
    feedback_count: int,
) -> int:
    q = text("""
        INSERT INTO content_refresh_jobs (
            user_id,
            feedback_count,
            status,
            created_at
        )
        VALUES (
            :user_id,
            :feedback_count,
            'pending',
            CURRENT_TIMESTAMP
        )
        RETURNING id
    """)

    result = db.execute(
        q,
        {
            "user_id": user_id,
            "feedback_count": feedback_count,
        },
    )

    return int(result.scalar_one())


def maybe_enqueue_content_refresh_job(
    db: Session,
    user_id: int,
) -> tuple[bool, int | None, int]:
    feedback_count = count_user_explicit_feedback(db=db, user_id=user_id)

    if not should_enqueue_content_refresh(
        db=db,
        user_id=user_id,
        feedback_count=feedback_count,
    ):
        return False, None, feedback_count

    job_id = enqueue_content_refresh_job(
        db=db,
        user_id=user_id,
        feedback_count=feedback_count,
    )

    return True, job_id, feedback_count


def save_interaction(
    db: Session,
    user_id: int,
    movie_id: int | None,
    event_type: str,
    event_value: float | None = None,
    source: str | None = None,
    rank: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event_type_clean = event_type.strip().lower()

    event_id = log_interaction_event(
        db=db,
        user_id=user_id,
        movie_id=movie_id,
        event_type=event_type_clean,
        event_value=event_value,
        source=source,
        rank=rank,
        metadata=metadata,
    )

    should_update_feedback, rating, liked, disliked = derive_feedback_state(
        event_type=event_type_clean,
        event_value=event_value,
    )

    content_refresh_job_created = False
    content_refresh_job_id: int | None = None
    feedback_count: int | None = None

    if should_update_feedback:
        if movie_id is None:
            raise ValueError("movie_id is required for feedback events")

        upsert_user_movie_feedback(
            db=db,
            user_id=user_id,
            movie_id=movie_id,
            rating=rating,
            liked=liked,
            disliked=disliked,
            source=source,
            last_event_type=event_type_clean,
        )

        (
            content_refresh_job_created,
            content_refresh_job_id,
            feedback_count,
        ) = maybe_enqueue_content_refresh_job(
            db=db,
            user_id=user_id,
        )

    return {
        "event_id": event_id,
        "feedback_updated": should_update_feedback,
        "feedback_count": feedback_count,
        "content_refresh_job_created": content_refresh_job_created,
        "content_refresh_job_id": content_refresh_job_id,
    }