from sqlalchemy.orm import Session

from app.services.user_cf_candidates import (
    get_user_cf_candidates,
)

from app.services.metadata import (
    get_user_seen_and_liked_movies,
    get_movie_metadata,
)

from app.services.content import (
    get_aggregated_content_scores,
    normalize_scores,
)

from app.services.collaborative import get_cf_scores_for_user

from app.services.recent_interactions import (
    rerank_with_recent_interactions,
)

from app.services.user_content_candidates import (
    get_user_content_candidates,
)

from app.services.recommendation_merger import (
    merge_all_recommendation_sources,
)

def get_hybrid_alpha(liked_movies_count: int) -> float:
    """
    More CF weight for users with richer history.
    More content weight for sparse users.
    """

    if liked_movies_count < 3:
        return 0.3

    elif liked_movies_count < 10:
        return 0.5

    return 0.65


def compute_hybrid_score(
    content_score: float,
    cf_score: float,
    alpha: float,
    content_only_weight: float = 0.85,
    cf_only_weight: float = 0.85,
    dual_signal_bonus: float = 0.12,
) -> float:
    """
    Combines normalized content and collaborative scores.
    """

    has_content = content_score > 0
    has_cf = cf_score > 0

    # both signals exist
    if has_content and has_cf:
        return (
            alpha * cf_score
            + (1 - alpha) * content_score
            + dual_signal_bonus
        )

    # only content
    if has_content:
        return content_only_weight * content_score

    # only collaborative
    if has_cf:
        return cf_only_weight * cf_score

    return 0.0


def merge_hybrid_scores(
    content_scores,
    cf_scores,
    alpha: float,
):
    """
    Merges normalized content and CF scores.
    """

    content_norm = normalize_scores(content_scores)
    cf_norm = normalize_scores(cf_scores)

    all_movie_ids = (
        set(content_norm.keys())
        | set(cf_norm.keys())
    )

    merged = {}

    for movie_id in all_movie_ids:

        c_score = content_norm.get(movie_id, 0.0)
        f_score = cf_norm.get(movie_id, 0.0)

        final_score = compute_hybrid_score(
            content_score=c_score,
            cf_score=f_score,
            alpha=alpha,
        )

        signal_count = (
            int(c_score > 0)
            + int(f_score > 0)
        )

        merged[movie_id] = {
            "content_score": round(float(c_score), 4),
            "cf_score": round(float(f_score), 4),
            "final_score": round(float(final_score), 4),
            "signal_count": signal_count,
        }

    return merged


def get_hybrid_recommendations_for_user(
    user_id: int,
    db: Session,
    limit: int = 30,
):
    """
    Main hybrid recommendation pipeline.
    """

    # -----------------------------------
    # 1. Get user history
    # -----------------------------------

    seen_movies, liked_movies = (
        get_user_seen_and_liked_movies(
            user_id=user_id,
            db=db,
            min_rating=4.0,
        )
    )

    if not liked_movies:
        return [], {
            "message": "No liked movies found for this user."
        }

    # -----------------------------------
    # 2. Content-based scores
    # -----------------------------------

    content_scores, contribution_count = (
        get_aggregated_content_scores(
            liked_movies=liked_movies,
            seen_movies=seen_movies,
            per_movie_top_k=10,
        )
    )

    # -----------------------------------
    # 3. Collaborative scores
    # -----------------------------------

    cf_scores = get_cf_scores_for_user(
        user_id=user_id,
        seen_movies=seen_movies,
    )

    if not content_scores and not cf_scores:
        return [], {
            "message": "No recommendations found."
        }

    # -----------------------------------
    # 4. Compute alpha
    # -----------------------------------

    alpha = get_hybrid_alpha(
        len(liked_movies)
    )

    # -----------------------------------
    # 5. Merge CF + Content scores
    # -----------------------------------

    merged_scores = merge_hybrid_scores(
        content_scores=content_scores,
        cf_scores=cf_scores,
        alpha=alpha,
    )

    # -----------------------------------
    # 6. Rank movies
    # -----------------------------------

    ranked = sorted(
        merged_scores.items(),
        key=lambda x: x[1]["final_score"],
        reverse=True,
    )[: limit * 5]

    candidate_movie_ids = [
        movie_id
        for movie_id, _ in ranked
    ]

    # -----------------------------------
    # 7. Fetch metadata
    # -----------------------------------

    metadata = get_movie_metadata(
        candidate_movie_ids,
        db,
    )

    # -----------------------------------
    # 8. Build candidate objects
    # -----------------------------------

    candidates = []

    for movie_id, score_bundle in ranked:

        movie_meta = metadata.get(movie_id)

        if not movie_meta:
            continue

        candidate = {
            "movieId": movie_id,
            "movie_id": movie_id,

            "title": movie_meta.get("title", ""),
            "genres": movie_meta.get("genres", ""),
            "overview": movie_meta.get("overview", ""),
            "poster": movie_meta.get("poster_path", ""),
            "poster_path": movie_meta.get("poster_path", ""),
            "director": movie_meta.get("director", ""),
            "keywords": movie_meta.get("keywords", ""),
            "release_date": movie_meta.get("release_date", ""),

            "content_score": round(
                float(score_bundle["content_score"]),
                4,
            ),

            "cf_score": round(
                float(score_bundle["cf_score"]),
                4,
            ),

            "final_score": round(
                float(score_bundle["final_score"]),
                4,
            ),

            "signal_count": score_bundle.get(
                "signal_count",
                0,
            ),

            "support_count": contribution_count.get(
                movie_id,
                0,
            ),

            "source": "hybrid",
        }

        candidates.append(candidate)

    # -----------------------------------
    # 9. Load async feedback-content recommendations
    # -----------------------------------

    feedback_content_candidates = get_user_content_candidates(
    db=db,
    user_id=user_id,
    limit=50,
)

    retrained_cf_candidates = get_user_cf_candidates(
        db=db,
        user_id=user_id,
        limit=50,
    )

    final_recommendations = merge_all_recommendation_sources(
        base_recommendations=candidates,
        feedback_content_candidates=feedback_content_candidates,
        retrained_cf_candidates=retrained_cf_candidates,
        limit=limit,
    )

    # -----------------------------------
    # 11. Optional recent interaction reranking
    # -----------------------------------

    try:
        final_recommendations = (
            rerank_with_recent_interactions(
                user_id=user_id,
                recommendations=final_recommendations,
                db=db,
            )
        )
    except Exception:
        pass

    # -----------------------------------
    # 12. Final metadata
    # -----------------------------------

    meta = {
    "alpha": alpha,
    "liked_movies_count": len(liked_movies),
    "seen_movies_count": len(seen_movies),
    "candidate_count": len(final_recommendations),
    "feedback_content_candidates_count": len(feedback_content_candidates),
    "retrained_cf_candidates_count": len(retrained_cf_candidates),
    }

    return final_recommendations, meta