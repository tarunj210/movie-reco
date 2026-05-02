from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


RATING_EVENT_TYPES = {"movie_rating", "rating"}


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

    event_id = result.scalar_one()
    return int(event_id)


def metadata_as_json(metadata: dict[str, Any] | None) -> str:
    import json

    if metadata is None:
        return "{}"

    return json.dumps(metadata)


def update_rating_from_event(
    db: Session,
    user_id: int,
    movie_id: int,
    rating: float,
) -> None:
    """
    For explicit rating events, update the ratings table.

    Current ratings table does not have a unique constraint, so we use:
    delete old user/movie rating -> insert new rating.
    """

    if rating < 0 or rating > 5:
        raise ValueError("rating must be between 0 and 5")

    delete_q = text("""
        DELETE FROM ratings
        WHERE userid = :user_id
          AND movieid = :movie_id
    """)

    insert_q = text("""
        INSERT INTO ratings (
            userid,
            movieid,
            rating,
            timestamp
        )
        VALUES (
            :user_id,
            :movie_id,
            :rating,
            EXTRACT(EPOCH FROM NOW())::BIGINT
        )
    """)

    db.execute(delete_q, {"user_id": user_id, "movie_id": movie_id})
    db.execute(
        insert_q,
        {
            "user_id": user_id,
            "movie_id": movie_id,
            "rating": rating,
        },
    )


def update_user_profile_summary_basic(
    db: Session,
    user_id: int,
    movie_id: int | None,
) -> None:
    """
    Basic first version.

    Keeps the latest interacted movie IDs in user_profile_summary.
    Later we can expand this to update genres/directors/keywords.
    """

    if movie_id is None:
        return

    q = text("""
        INSERT INTO user_profile_summary (
            user_id,
            recent_movie_ids,
            updated_at
        )
        VALUES (
            :user_id,
            jsonb_build_array(:movie_id),
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (user_id)
        DO UPDATE SET
            recent_movie_ids = (
                SELECT jsonb_agg(DISTINCT value)
                FROM (
                    SELECT value
                    FROM jsonb_array_elements(user_profile_summary.recent_movie_ids)
                    UNION ALL
                    SELECT to_jsonb(:movie_id)
                ) AS items(value)
            ),
            updated_at = CURRENT_TIMESTAMP
    """)

    db.execute(q, {"user_id": user_id, "movie_id": movie_id})


def save_interaction(
    db: Session,
    user_id: int,
    movie_id: int | None,
    event_type: str,
    event_value: float | None = None,
    source: str | None = None,
    rank: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> int:
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

    if event_type_clean in RATING_EVENT_TYPES:
        if movie_id is None:
            raise ValueError("movie_id is required for rating events")
        if event_value is None:
            raise ValueError("event_value is required for rating events")

        update_rating_from_event(
            db=db,
            user_id=user_id,
            movie_id=movie_id,
            rating=float(event_value),
        )

    update_user_profile_summary_basic(
        db=db,
        user_id=user_id,
        movie_id=movie_id,
    )

    return event_id