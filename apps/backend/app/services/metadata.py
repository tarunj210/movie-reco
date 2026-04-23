from sqlalchemy import text
from sqlalchemy.orm import Session

def get_user_seen_and_liked_movies(user_id: int, db: Session, min_rating: float = 4.0):
    q = text("""
    SELECT movieid, rating
    FROM ratings
    WHERE userid = :uid
    """)

    rows = db.execute(q, {"uid": user_id}).mappings().all()

    seen_movies = set()
    liked_movies = []

    for row in rows:
        movie_id = int(row["movieid"])
        rating = float(row["rating"])

        seen_movies.add(movie_id)

        if rating >= min_rating:
            liked_movies.append((movie_id, rating))

    return seen_movies, liked_movies

def get_movie_metadata(movie_ids, db: Session):
    if not movie_ids:
        return {}

    q = text("""
    SELECT movieid, title, genres, overview, poster_path, director, keywords, release_date
    FROM movies_enriched
    WHERE movieid = ANY(:movie_ids)
    """)

    rows = db.execute(q, {"movie_ids": list(movie_ids)}).mappings().all()

    meta = {}
    for row in rows:
        meta[int(row["movieid"])] = {
            "title": row["title"],
            "genres": row.get("genres", ""),
            "overview": row.get("overview", ""),
            "poster_path": row.get("poster_path", ""),
            "director": row.get("director", ""),
            "keywords": row.get("keywords", ""),
            "release_date": row.get("release_date", "")
        }

    return meta