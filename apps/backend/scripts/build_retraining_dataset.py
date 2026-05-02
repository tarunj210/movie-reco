from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


BASE_DIR = Path(__file__).resolve().parents[1]

APP_ENV_FILE = os.getenv("APP_ENV_FILE", ".env.local")
ENV_FILE = BASE_DIR / APP_ENV_FILE

load_dotenv(ENV_FILE, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(f"DATABASE_URL is not set in {ENV_FILE}")

OUTPUT_DIR = BASE_DIR / "artifacts" / "training"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_PATH = OUTPUT_DIR / "neumf_training_interactions.csv"

engine = create_engine(DATABASE_URL)


def load_original_ratings() -> pd.DataFrame:
    """
    Loads original historical ratings from the ratings table.

    Expected table columns:
    - userid
    - movieid
    - rating
    - timestamp
    """

    query = text("""
        SELECT
            userid AS user_id,
            movieid AS movie_id,
            rating,
            timestamp
        FROM ratings
    """)

    return pd.read_sql(query, engine)


def load_user_movie_feedback() -> pd.DataFrame:
    """
    Loads new app feedback collected from the frontend.

    Expected table columns:
    - user_id
    - movie_id
    - rating
    - liked
    - disliked
    - updated_at
    """

    query = text("""
        SELECT
            user_id,
            movie_id,
            rating,
            liked,
            disliked,
            updated_at
        FROM user_movie_feedback
    """)

    return pd.read_sql(query, engine)


def convert_original_ratings_to_training_rows(ratings: pd.DataFrame) -> pd.DataFrame:
    """
    Converts original ratings into implicit training labels.

    Rule:
    - rating >= 4.0 => positive label 1
    - rating <= 2.0 => negative label 0
    - rating around 3.0 => ignored
    """

    rows: list[dict] = []

    for row in ratings.itertuples(index=False):
        rating = float(row.rating)

        if rating >= 4.0:
            rows.append(
                {
                    "user_id": int(row.user_id),
                    "movie_id": int(row.movie_id),
                    "label": 1,
                    "weight": 1.0,
                    "source": "original_rating_positive",
                }
            )

        elif rating <= 2.0:
            rows.append(
                {
                    "user_id": int(row.user_id),
                    "movie_id": int(row.movie_id),
                    "label": 0,
                    "weight": 1.0,
                    "source": "original_rating_negative",
                }
            )

    return pd.DataFrame(rows)


def convert_feedback_to_training_rows(feedback: pd.DataFrame) -> pd.DataFrame:
    """
    Converts app feedback into implicit training labels.

    Rule:
    - liked = true => positive label 1
    - disliked = true => negative label 0
    - rating >= 4.0 => positive label 1
    - rating <= 2.0 => negative label 0
    - rating around 3.0 => ignored

    App feedback gets higher weight because it is newer and explicit.
    """

    rows: list[dict] = []

    for row in feedback.itertuples(index=False):
        rating = row.rating

        rating_value = None
        if rating is not None and not pd.isna(rating):
            rating_value = float(rating)

        liked = bool(row.liked)
        disliked = bool(row.disliked)

        is_positive = liked or (rating_value is not None and rating_value >= 4.0)
        is_negative = disliked or (rating_value is not None and rating_value <= 2.0)

        if is_positive:
            rows.append(
                {
                    "user_id": int(row.user_id),
                    "movie_id": int(row.movie_id),
                    "label": 1,
                    "weight": 2.0,
                    "source": "app_feedback_positive",
                }
            )

        elif is_negative:
            rows.append(
                {
                    "user_id": int(row.user_id),
                    "movie_id": int(row.movie_id),
                    "label": 0,
                    "weight": 2.0,
                    "source": "app_feedback_negative",
                }
            )

    return pd.DataFrame(rows)


def build_retraining_dataset() -> pd.DataFrame:
    print("Loading original ratings...")
    ratings = load_original_ratings()

    print("Loading app feedback...")
    feedback = load_user_movie_feedback()

    print(f"Original ratings rows: {len(ratings):,}")
    print(f"App feedback rows: {len(feedback):,}")

    original_training = convert_original_ratings_to_training_rows(ratings)
    feedback_training = convert_feedback_to_training_rows(feedback)

    print(f"Original training rows: {len(original_training):,}")
    print(f"Feedback training rows: {len(feedback_training):,}")

    combined = pd.concat(
        [original_training, feedback_training],
        ignore_index=True,
    )

    if combined.empty:
        raise RuntimeError("No training rows generated.")

    # If the same user/movie exists in both original ratings and new feedback,
    # keep the stronger/newer app feedback row.
    #
    # feedback weight = 2.0
    # original rating weight = 1.0
    combined = (
        combined.sort_values(["user_id", "movie_id", "weight"])
        .drop_duplicates(["user_id", "movie_id"], keep="last")
        .reset_index(drop=True)
    )

    combined = combined.sort_values(["user_id", "movie_id"]).reset_index(drop=True)

    return combined


def main() -> None:
    df = build_retraining_dataset()

    df.to_csv(OUTPUT_PATH, index=False)

    print("")
    print("Retraining dataset created successfully.")
    print(f"Output path: {OUTPUT_PATH}")
    print(f"Total rows: {len(df):,}")

    print("")
    print("Label distribution:")
    print(df["label"].value_counts())

    print("")
    print("Source distribution:")
    print(df["source"].value_counts())


if __name__ == "__main__":
    main()