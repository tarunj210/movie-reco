import pandas as pd
from collections import defaultdict
from app.core.config import CF_RECS_PATH, CONTENT_RECS_PATH
cf_map = defaultdict(list)
content_map = defaultdict(list)

def load_content_recommendations():
    global content_map

    df = pd.read_csv(CONTENT_RECS_PATH)

    content_map.clear()

    for _, row in df.iterrows():
        source_movie_id = int(row["source_movie_id"])
        target_movie_id = int(row["target_movie_id"])
        similarity_score = float(row["similarity_score"])
        rank = int(row["rank"]) if "rank" in row and pd.notna(row["rank"]) else None

        # FIX: include director in content_map to enable diversity penalty
        director = str(row["director"]) if "director" in row and pd.notna(row["director"]) else "unknown"

        content_map[source_movie_id].append({
            "movie_id": target_movie_id,
            "score": similarity_score,
            "rank": rank,
            "director": director,
        })

    print(f"Loaded content recommendations for {len(content_map)} source movies.")

def load_cf_recommendations():
    global cf_map

    df = pd.read_csv(CF_RECS_PATH)

    cf_map.clear()

    for _, row in df.iterrows():
        user_id = int(row["user_id"])
        movie_id = int(row["movie_id"])
        score = float(row["score"])
        rank = int(row["rank"]) if "rank" in row and pd.notna(row["rank"]) else None

        cf_map[user_id].append({
            "movie_id": movie_id,
            "score": score,
            "rank": rank,
        })

    print(f"Loaded CF recommendations for {len(cf_map)} users.")