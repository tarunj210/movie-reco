from __future__ import annotations

import ast
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.metadata import get_movie_metadata


POSITIVE_EVENT_TYPES = {
    "movie_click",
    "movie_like",
    "like",
    "watch",
    "movie_watch",
    "movie_rating",
    "rating",
}

NEGATIVE_EVENT_TYPES = {
    "movie_dislike",
    "dislike",
    "hide",
    "not_interested",
}


def parse_metadata_list(value: Any) -> set[str]:
    """
    Converts genres/keywords stored as strings into a normalized set.

    Supports formats like:
    - "Action|Adventure|Sci-Fi"
    - "Action, Adventure, Sci-Fi"
    - "['Action', 'Adventure']"
    - empty/null values
    """

    if value is None:
        return set()

    s = str(value).strip()
    if not s:
        return set()

    try:
        parsed = ast.literal_eval(s)
        if isinstance(parsed, list):
            return {str(x).strip().lower() for x in parsed if str(x).strip()}
    except Exception:
        pass

    if "|" in s:
        return {x.strip().lower() for x in s.split("|") if x.strip()}

    if "," in s:
        return {x.strip().lower() for x in s.split(",") if x.strip()}

    return {s.lower()}


def get_recent_interaction_signals(
    db: Session,
    user_id: int,
    limit: int = 50,
) -> dict[str, Any]:
    """
    Reads recent user events and converts them into positive and negative signals.

    Positive signals:
    - clicks
    - likes
    - watches
    - ratings >= 4.0

    Negative signals:
    - dislikes
    - hide/not interested
    - ratings <= 2.0
    """

    q = text("""
        SELECT
            movie_id,
            event_type,
            event_value,
            created_at
        FROM interaction_events
        WHERE user_id = :user_id
          AND movie_id IS NOT NULL
        ORDER BY created_at DESC
        LIMIT :limit
    """)

    rows = db.execute(
        q,
        {
            "user_id": user_id,
            "limit": limit,
        },
    ).mappings().all()

    positive_movie_weights: dict[int, float] = {}
    negative_movie_ids: set[int] = set()

    for row in rows:
        movie_id = int(row["movie_id"])
        event_type = str(row["event_type"]).strip().lower()
        event_value = row["event_value"]

        if event_type in {"movie_rating", "rating"}:
            if event_value is None:
                continue

            rating = float(event_value)

            if rating >= 4.0:
                positive_movie_weights[movie_id] = max(
                    positive_movie_weights.get(movie_id, 0.0),
                    rating / 5.0,
                )
            elif rating <= 2.0:
                negative_movie_ids.add(movie_id)

        elif event_type in NEGATIVE_EVENT_TYPES:
            negative_movie_ids.add(movie_id)

        elif event_type in POSITIVE_EVENT_TYPES:
            positive_movie_weights[movie_id] = max(
                positive_movie_weights.get(movie_id, 0.0),
                0.6,
            )

    return {
        "positive_movie_weights": positive_movie_weights,
        "negative_movie_ids": negative_movie_ids,
    }


def compute_metadata_similarity(
    candidate_meta: dict[str, Any],
    recent_meta: dict[str, Any],
) -> float:
    """
    Computes a lightweight metadata similarity score between:
    - candidate movie
    - recently interacted movie

    Score is based on:
    - genre overlap
    - director match
    - keyword overlap
    """

    candidate_genres = parse_metadata_list(candidate_meta.get("genres"))
    recent_genres = parse_metadata_list(recent_meta.get("genres"))

    candidate_keywords = parse_metadata_list(candidate_meta.get("keywords"))
    recent_keywords = parse_metadata_list(recent_meta.get("keywords"))

    candidate_director = str(candidate_meta.get("director") or "").strip().lower()
    recent_director = str(recent_meta.get("director") or "").strip().lower()

    score = 0.0

    if candidate_genres and recent_genres:
        genre_union = candidate_genres | recent_genres
        genre_overlap = candidate_genres & recent_genres
        score += 0.55 * (len(genre_overlap) / max(len(genre_union), 1))

    if candidate_director and recent_director and candidate_director == recent_director:
        score += 0.25

    if candidate_keywords and recent_keywords:
        keyword_union = candidate_keywords | recent_keywords
        keyword_overlap = candidate_keywords & recent_keywords
        score += 0.20 * (len(keyword_overlap) / max(len(keyword_union), 1))

    return min(score, 1.0)


def compute_recent_interest_score(
    candidate: dict[str, Any],
    recent_movie_metadata: dict[int, dict[str, Any]],
    positive_movie_weights: dict[int, float],
) -> float:
    """
    Computes how well a candidate matches the user's recent positive interactions.
    """

    if not positive_movie_weights:
        return 0.0

    weighted_score = 0.0
    total_weight = 0.0

    for recent_movie_id, weight in positive_movie_weights.items():
        recent_meta = recent_movie_metadata.get(recent_movie_id)

        if not recent_meta:
            continue

        similarity = compute_metadata_similarity(candidate, recent_meta)

        weighted_score += similarity * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0

    return min(weighted_score / total_weight, 1.0)


def rerank_with_recent_interactions(
    db: Session,
    user_id: int,
    candidates: list[dict[str, Any]],
    recent_limit: int = 50,
    recent_weight: float = 0.18,
    negative_penalty: float = 0.35,
) -> list[dict[str, Any]]:
    """
    Reranks candidate recommendations using recent user interactions.

    This does not retrain the model.
    It dynamically adjusts ranking using fresh interaction signals.
    """

    if not candidates:
        return candidates

    signals = get_recent_interaction_signals(
        db=db,
        user_id=user_id,
        limit=recent_limit,
    )

    positive_movie_weights: dict[int, float] = signals["positive_movie_weights"]
    negative_movie_ids: set[int] = signals["negative_movie_ids"]

    if not positive_movie_weights and not negative_movie_ids:
        for item in candidates:
            item["recent_interest_score"] = 0.0
            item["dynamic_score"] = item.get("final_score", 0.0)
        return candidates

    recent_movie_metadata = get_movie_metadata(
        movie_ids=list(positive_movie_weights.keys()),
        db=db,
    )

    reranked: list[dict[str, Any]] = []

    for item in candidates:
        movie_id = int(item["movieId"])
        base_score = float(item.get("final_score", 0.0))

        recent_interest_score = compute_recent_interest_score(
            candidate=item,
            recent_movie_metadata=recent_movie_metadata,
            positive_movie_weights=positive_movie_weights,
        )

        dynamic_score = base_score + (recent_weight * recent_interest_score)

        if movie_id in negative_movie_ids:
            dynamic_score -= negative_penalty

        dynamic_score = max(dynamic_score, 0.0)

        updated_item = item.copy()
        updated_item["recent_interest_score"] = round(float(recent_interest_score), 4)
        updated_item["dynamic_score"] = round(float(dynamic_score), 4)

        reranked.append(updated_item)

    reranked.sort(
        key=lambda x: x.get("dynamic_score", x.get("final_score", 0.0)),
        reverse=True,
    )

    for idx, item in enumerate(reranked, start=1):
        item["rank"] = idx

    return reranked