from __future__ import annotations


def _get_movie_id(candidate: dict) -> int | None:
    movie_id = candidate.get("movie_id")

    if movie_id is None:
        movie_id = candidate.get("movieId")

    if movie_id is None:
        movie_id = candidate.get("movieid")

    if movie_id is None:
        return None

    return int(movie_id)


def _get_score(candidate: dict) -> float:
    """
    Handles different score keys from different recommendation sources.
    """

    score_keys = [
        "final_score",
        "hybrid_score",
        "score",
        "feedback_content_score",
        "retrained_cf_score",
        "content_score",
        "cf_score",
    ]

    for key in score_keys:
        value = candidate.get(key)

        if value is not None:
            try:
                return float(value)
            except Exception:
                continue

    return 0.0


def _append_source(existing_source: str | None, new_source: str) -> str:
    if not existing_source:
        return new_source

    sources = existing_source.split("+")
    if new_source not in sources:
        sources.append(new_source)

    return "+".join(sources)


def _merge_candidate_into_pool(
    merged: dict[int, dict],
    candidate: dict,
    source_name: str,
    rank_key: str,
    score_key: str,
    rank: int,
) -> None:
    movie_id = _get_movie_id(candidate)

    if movie_id is None:
        return

    candidate_score = _get_score(candidate)

    if movie_id in merged:
        existing = merged[movie_id]

        existing[score_key] = candidate_score
        existing[rank_key] = rank

        if candidate.get("reason"):
            existing["reason"] = candidate["reason"]

        if candidate.get("model_version"):
            existing["model_version"] = candidate["model_version"]

        existing_score = _get_score(existing)
        existing["final_score"] = max(existing_score, candidate_score)

        existing["source"] = _append_source(
            existing.get("source"),
            source_name,
        )

        # Fill missing metadata from new candidate if existing one is incomplete.
        for key in [
            "title",
            "genres",
            "overview",
            "poster",
            "poster_path",
            "director",
            "keywords",
            "release_date",
        ]:
            if not existing.get(key) and candidate.get(key):
                existing[key] = candidate[key]

    else:
        candidate_copy = dict(candidate)

        candidate_copy["movie_id"] = movie_id
        candidate_copy["movieId"] = movie_id

        candidate_copy[score_key] = candidate_score
        candidate_copy[rank_key] = rank
        candidate_copy["final_score"] = candidate_score
        candidate_copy["source"] = source_name

        merged[movie_id] = candidate_copy


def merge_all_recommendation_sources(
    base_recommendations: list[dict],
    feedback_content_candidates: list[dict],
    retrained_cf_candidates: list[dict],
    limit: int = 20,
) -> list[dict]:
    """
    Merges:
    - original hybrid recommendations
    - async feedback-based content candidates
    - retrained collaborative filtering candidates

    Rules:
    - deduplicate by movie_id
    - enrich duplicates with extra scores/source labels
    - keep strongest available score as final_score
    - sort by final_score
    """

    merged: dict[int, dict] = {}

    # 1. Original hybrid recommendations
    for rank, candidate in enumerate(base_recommendations, start=1):
        movie_id = _get_movie_id(candidate)

        if movie_id is None:
            continue

        candidate_copy = dict(candidate)

        candidate_copy["movie_id"] = movie_id
        candidate_copy["movieId"] = movie_id
        candidate_copy.setdefault("source", "hybrid")
        candidate_copy.setdefault("original_rank", rank)

        base_score = _get_score(candidate_copy)
        candidate_copy.setdefault("final_score", base_score)

        merged[movie_id] = candidate_copy

    # 2. Feedback content candidates
    for rank, candidate in enumerate(feedback_content_candidates, start=1):
        _merge_candidate_into_pool(
            merged=merged,
            candidate=candidate,
            source_name="feedback_content",
            rank_key="feedback_content_rank",
            score_key="feedback_content_score",
            rank=rank,
        )

    # 3. Retrained CF candidates
    for rank, candidate in enumerate(retrained_cf_candidates, start=1):
        _merge_candidate_into_pool(
            merged=merged,
            candidate=candidate,
            source_name="retrained_cf",
            rank_key="retrained_cf_rank",
            score_key="retrained_cf_score",
            rank=rank,
        )

    final_recommendations = list(merged.values())

    final_recommendations.sort(
        key=lambda item: float(item.get("final_score", 0.0)),
        reverse=True,
    )

    final_recommendations = final_recommendations[:limit]

    for idx, item in enumerate(final_recommendations, start=1):
        item["rank"] = idx

    return final_recommendations


def merge_hybrid_with_feedback_content(
    base_recommendations: list[dict],
    feedback_content_candidates: list[dict],
    limit: int = 20,
) -> list[dict]:
    """
    Backward-compatible wrapper for the older content-only merge.
    """

    return merge_all_recommendation_sources(
        base_recommendations=base_recommendations,
        feedback_content_candidates=feedback_content_candidates,
        retrained_cf_candidates=[],
        limit=limit,
    )