from app.services.loaders import cf_map

def get_cf_scores_for_user(user_id: int, seen_movies: set):
    scores = {}

    for rec in cf_map.get(user_id, []):
        movie_id = rec["movie_id"]
        score = rec["score"]

        if movie_id in seen_movies:
            continue

        scores[movie_id] = score

    return scores