from collections import defaultdict
from app.services.loaders import content_map

def get_aggregated_content_scores(
    liked_movies,
    seen_movies,
    per_movie_top_k: int = 25,       
    max_per_director: int = 2,        # new — caps score accumulation per director
    director_penalty: float = 0.3,    # new — penalty multiplier for over-represented directors
):
    candidate_scores = defaultdict(float)
    contribution_count = defaultdict(int)
    director_count = defaultdict(int)  # tracks how many times each director appears

    for source_movie_id, user_rating in liked_movies:
        recs = content_map.get(source_movie_id, [])

        # take top 25 recs from each source movie (was 10)
        top_recs = recs[:per_movie_top_k]

        for rec in top_recs:
            target_movie_id = rec["movie_id"]
            similarity_score = rec["score"]
            director = rec.get("director", "unknown")

            if target_movie_id in seen_movies:
                continue

            # FIX 2: apply heavy penalty if this director is already over-represented
            if director_count[director] >= max_per_director:
                similarity_score *= director_penalty

            candidate_scores[target_movie_id] += similarity_score * user_rating
            contribution_count[target_movie_id] += 1
            director_count[director] += 1

    return candidate_scores, contribution_count


def normalize_scores(score_dict):
    if not score_dict:
        return {}

    values = list(score_dict.values())
    min_v = min(values)
    max_v = max(values)

    if max_v == min_v:
        return {k: 1.0 for k in score_dict}

    return {
        k: (v - min_v) / (max_v - min_v)
        for k, v in score_dict.items()
    }

