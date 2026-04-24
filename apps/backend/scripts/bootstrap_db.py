from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set in your environment or .env file")

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "artifacts"

RATINGS_CSV = DATA_DIR / "ratings_small.csv"
MOVIES_CSV = DATA_DIR / "movies.csv"

if not RATINGS_CSV.exists():
    raise FileNotFoundError(f"ratings_small.csv not found at: {RATINGS_CSV}")
if not MOVIES_CSV.exists():
    raise FileNotFoundError(f"movies.csv not found at: {MOVIES_CSV}")

engine = create_engine(DATABASE_URL)


def required_tables_exist() -> bool:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    required = {"users", "movies_enriched", "ratings"}
    return required.issubset(existing_tables)


def bootstrap() -> None:
    if required_tables_exist():
        print("Required tables already exist. Skipping bootstrap.")
        return

    print("Loading CSV files...")
    ratings = pd.read_csv(RATINGS_CSV)
    movies = pd.read_csv(MOVIES_CSV)

    required_ratings_cols = {"userId", "movieId", "rating", "timestamp"}
    required_movies_cols = {"movieId", "title", "genres"}

    missing_ratings = required_ratings_cols - set(ratings.columns)
    missing_movies = required_movies_cols - set(movies.columns)

    if missing_ratings:
        raise ValueError(f"ratings_small.csv missing columns: {missing_ratings}")
    if missing_movies:
        raise ValueError(f"movies.csv missing columns: {missing_movies}")

    ratings = ratings.rename(
        columns={
            "userId": "userid",
            "movieId": "movieid",
        }
    )[["userid", "movieid", "rating", "timestamp"]]

    movies = movies.rename(
        columns={
            "movieId": "movieid",
        }
    )[["movieid", "title", "genres"]]

    # Add columns expected by the backend
    movies["overview"] = ""
    movies["poster_path"] = ""
    movies["director"] = ""
    movies["keywords"] = ""
    movies["release_date"] = ""

    users = ratings[["userid"]].drop_duplicates().sort_values("userid").copy()
    users["passwd"] = users["userid"].astype(str)

    print(f"Ratings rows: {len(ratings):,}")
    print(f"Movies rows: {len(movies):,}")
    print(f"Users rows: {len(users):,}")

    with engine.begin() as conn:
        print("Dropping old tables if they exist...")
        conn.execute(text("DROP TABLE IF EXISTS ratings"))
        conn.execute(text("DROP TABLE IF EXISTS movies_enriched"))
        conn.execute(text("DROP TABLE IF EXISTS users"))

    print("Writing tables to Postgres...")
    users.to_sql("users", engine, if_exists="replace", index=False)
    movies.to_sql("movies_enriched", engine, if_exists="replace", index=False)
    ratings.to_sql("ratings", engine, if_exists="replace", index=False)

    with engine.begin() as conn:
        print("Adding primary keys and indexes...")
        conn.execute(text("ALTER TABLE users ADD PRIMARY KEY (userid)"))
        conn.execute(text("ALTER TABLE movies_enriched ADD PRIMARY KEY (movieid)"))
        conn.execute(text("CREATE INDEX idx_ratings_userid ON ratings(userid)"))
        conn.execute(text("CREATE INDEX idx_ratings_movieid ON ratings(movieid)"))
        conn.execute(text("CREATE INDEX idx_ratings_timestamp ON ratings(timestamp)"))

    print("Bootstrap complete.")
    print("Created tables:")
    print("- users(userid, passwd)")
    print("- movies_enriched(movieid, title, genres, overview, poster_path, director, keywords, release_date)")
    print("- ratings(userid, movieid, rating, timestamp)")
    print("Login rule for now: user_id = password")


if __name__ == "__main__":
    bootstrap()