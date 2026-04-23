from sqlalchemy.orm import Session
from app.services.metadata import get_user_seen_and_liked_movies, get_movie_metadata
from app.services.content import get_aggregated_content_scores, normalize_scores
from app.services.collaborative import get_cf_scores_for_user


def get_hybrid_alpha(liked_movies_count: int) -> float:
    """
    More CF weight for users with richer history.
    More content weight for sparse users.

    Thresholds lowered so CF contributes meaningfully earlier.
    """
    if liked_movies_count < 3:      # was 5
        return 0.3
    elif liked_movies_count < 10:   # was 15
        return 0.5                  # was 0.45
    return 0.65     

def compute_hybrid_score(
    content_score: float,
    cf_score: float,
    alpha: float,
    content_only_weight: float = 0.85,
    cf_only_weight: float = 0.85,
    dual_signal_bonus: float = 0.12,  # was 0.05 — stronger reward when both signals agree
) -> float:
    """
    Combines normalized content and collaborative scores.

    Logic:
    - If both scores exist, use weighted merge + agreement bonus.
    - If only one exists, keep it with a slight discount.
    - If neither exists, return 0.
    """
    has_content = content_score > 0
    has_cf = cf_score > 0

    if has_content and has_cf:
        return alpha * cf_score + (1 - alpha) * content_score + dual_signal_bonus

    if has_content:
        return content_only_weight * content_score

    if has_cf:
        return cf_only_weight * cf_score

    return 0.0

def merge_hybrid_scores(content_scores, cf_scores, alpha: float):
    """
    content_scores: dict[movie_id] -> raw content score
    cf_scores: dict[movie_id] -> raw collaborative score

    Returns:
        dict[movie_id] -> {
            "content_score": normalized_content,
            "cf_score": normalized_cf,
            "final_score": merged_score,
            "signal_count": 1 or 2
        }
    """
    content_norm = normalize_scores(content_scores)
    cf_norm = normalize_scores(cf_scores)

    all_movie_ids = set(content_norm.keys()) | set(cf_norm.keys())

    merged = {}

    for movie_id in all_movie_ids:
        c_score = content_norm.get(movie_id, 0.0)
        f_score = cf_norm.get(movie_id, 0.0)

        final_score = compute_hybrid_score(
            content_score=c_score,
            cf_score=f_score,
            alpha=alpha
        )

        signal_count = int(c_score > 0) + int(f_score > 0)

        merged[movie_id] = {
            "content_score": round(float(c_score), 4),
            "cf_score": round(float(f_score), 4),
            "final_score": round(float(final_score), 4),
            "signal_count": signal_count
        }

    return merged


def get_hybrid_recommendations_for_user(
    user_id: int,
    db: Session,
    limit: int = 30
):
    seen_movies, liked_movies = get_user_seen_and_liked_movies(
        user_id, db, min_rating=4.0
    )

    if not liked_movies:
        return [], {"message": "No liked movies found for this user."}

    content_scores, contribution_count = get_aggregated_content_scores(
        liked_movies=liked_movies,
        seen_movies=seen_movies,
        per_movie_top_k=10
    )

    cf_scores = get_cf_scores_for_user(user_id, seen_movies)

    if not content_scores and not cf_scores:
        return [], {"message": "No recommendations found."}

    alpha = get_hybrid_alpha(len(liked_movies))

    merged_scores = merge_hybrid_scores(
        content_scores=content_scores,
        cf_scores=cf_scores,
        alpha=alpha
    )

    ranked = sorted(
        merged_scores.items(),
        key=lambda x: x[1]["final_score"],
        reverse=True
    )[:limit * 3]

    top_movie_ids = [movie_id for movie_id, _ in ranked]
    metadata = get_movie_metadata(top_movie_ids, db)

    recommendations = []
    for movie_id, score_bundle in ranked:
        movie_meta = metadata.get(movie_id)
        if not movie_meta:
            continue

        recommendations.append({
            "movieId": movie_id,
            "title": movie_meta.get("title", ""),
            "genres": movie_meta.get("genres", ""),
            "overview": movie_meta.get("overview", ""),
            "poster": movie_meta.get("poster_path", ""),
            "director": movie_meta.get("director", ""),
            "keywords": movie_meta.get("keywords", ""),
            "content_score": round(float(score_bundle["content_score"]), 4),
            "cf_score": round(float(score_bundle["cf_score"]), 4),
            "final_score": round(float(score_bundle["final_score"]), 4),
            "signal_count": score_bundle.get("signal_count", 0),
            "support_count": contribution_count.get(movie_id, 0),
            "rank": len(recommendations) + 1
        })

        if len(recommendations) >= limit:
            break

    return recommendations, {"alpha": alpha}  