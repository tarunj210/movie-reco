from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_user_content_candidates(
    db: Session,
    user_id: int,
    limit: int = 50,
) -> list[dict]:
    """
    Reads async-generated feedback-based content candidates for a user.

    These are created by workers/content_worker.py and stored in
    user_content_candidates.
    """

    query = text("""
        SELECT
            ucc.user_id,
            ucc.movie_id,
            ucc.score AS feedback_content_score,
            ucc.reason,
            ucc.run_id,
            ucc.generated_at,

            m.title,
            m.genres,
            m.overview,
            m.poster_path,
            m.director,
            m.keywords,
            m.release_date
        FROM user_content_candidates ucc
        LEFT JOIN movies_enriched m
            ON ucc.movie_id = m.movieid
        WHERE ucc.user_id = :user_id
        ORDER BY ucc.score DESC
        LIMIT :limit
    """)

    rows = db.execute(
        query,
        {
            "user_id": user_id,
            "limit": limit,
        },
    ).mappings().all()

    candidates: list[dict] = []

    for row in rows:
        candidates.append(
            {
                "movie_id": int(row["movie_id"]),
                "title": row["title"],
                "genres": row["genres"],
                "overview": row["overview"],
                "poster_path": row["poster_path"],
                "director": row["director"],
                "keywords": row["keywords"],
                "release_date": row["release_date"],
                "feedback_content_score": float(row["feedback_content_score"]),
                "reason": row["reason"],
                "run_id": row["run_id"],
                "generated_at": row["generated_at"],
                "source": "feedback_content",
            }
        )

    return candidates