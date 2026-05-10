from __future__ import annotations

import json
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

OUTPUT_DIR = BASE_DIR / "artifacts" / "retraining"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_CSV_PATH = OUTPUT_DIR / "latest_training_interactions.csv"
OUTPUT_SUMMARY_PATH = OUTPUT_DIR / "latest_training_summary.json"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


POSITIVE_THRESHOLD = 4.0
NEGATIVE_THRESHOLD = 2.0

ORIGINAL_RATING_WEIGHT = 1.0
APP_FEEDBACK_WEIGHT = 2.0


def load_original_ratings() -> pd.DataFrame:
    """
    Loads the original historical ratings table.

    Expected columns:
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

    with engine.connect() as conn:
        df = pd.read_sql_query(query, conn)

    return df


def load_user_movie_feedback() -> pd.DataFrame:
    """
    Loads new app feedback collected from likes/dislikes/ratings.

    Expected columns:
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

    with engine.connect() as conn:
        df = pd.read_sql_query(query, conn)

    return df


def rating_to_label(rating: float) -> int | None:
    """
    Converts explicit rating into binary implicit-feedback label.

    rating >= 4.0 => positive
    rating <= 2.0 => negative
    otherwise ignored
    """

    if rating >= POSITIVE_THRESHOLD:
        return 1

    if rating <= NEGATIVE_THRESHOLD:
        return 0

    return None


def convert_original_ratings(ratings_df: pd.DataFrame) -> pd.DataFrame:
    """
    Converts original MovieLens-style ratings into training rows.

    Output columns:
    - user_id
    - movie_id
    - rating
    - label
    - weight
    - source
    - event_time
    """

    if ratings_df.empty:
        return pd.DataFrame(
            columns=[
                "user_id",
                "movie_id",
                "rating",
                "label",
                "weight",
                "source",
                "event_time",
            ]
        )

    rows: list[dict] = []

    for row in ratings_df.itertuples(index=False):
        rating = float(row.rating)
        label = rating_to_label(rating)

        if label is None:
            continue

        rows.append(
            {
                "user_id": int(row.user_id),
                "movie_id": int(row.movie_id),
                "rating": rating,
                "label": int(label),
                "weight": ORIGINAL_RATING_WEIGHT,
                "source": "original_rating",
                "event_time": int(row.timestamp) if row.timestamp is not None else None,
            }
        )

    return pd.DataFrame(rows)


def convert_app_feedback(feedback_df: pd.DataFrame) -> pd.DataFrame:
    """
    Converts app feedback into training rows.

    Rules:
    - explicit rating is used if available
    - liked=True becomes synthetic rating 5.0
    - disliked=True becomes synthetic rating 1.0
    - app feedback receives higher weight than original ratings
    """

    if feedback_df.empty:
        return pd.DataFrame(
            columns=[
                "user_id",
                "movie_id",
                "rating",
                "label",
                "weight",
                "source",
                "event_time",
            ]
        )

    rows: list[dict] = []

    for row in feedback_df.itertuples(index=False):
        rating_value: float | None = None

        if row.rating is not None and not pd.isna(row.rating):
            rating_value = float(row.rating)

        elif bool(row.liked):
            rating_value = 5.0

        elif bool(row.disliked):
            rating_value = 1.0

        if rating_value is None:
            continue

        label = rating_to_label(rating_value)

        if label is None:
            continue

        if bool(row.liked):
            source = "app_feedback_like"
        elif bool(row.disliked):
            source = "app_feedback_dislike"
        else:
            source = "app_feedback_rating"

        rows.append(
            {
                "user_id": int(row.user_id),
                "movie_id": int(row.movie_id),
                "rating": rating_value,
                "label": int(label),
                "weight": APP_FEEDBACK_WEIGHT,
                "source": source,
                "event_time": row.updated_at,
            }
        )

    return pd.DataFrame(rows)


def combine_training_data(
    original_training_df: pd.DataFrame,
    feedback_training_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Combines original ratings and app feedback.

    If the same user/movie exists in both:
    - keep app feedback
    - because app feedback is newer and has higher weight
    """

    combined_df = pd.concat(
        [
            original_training_df,
            feedback_training_df,
        ],
        ignore_index=True,
    )

    if combined_df.empty:
        return combined_df

    source_priority = {
        "original_rating": 1,
        "app_feedback_rating": 2,
        "app_feedback_like": 2,
        "app_feedback_dislike": 2,
    }

    combined_df["source_priority"] = combined_df["source"].map(source_priority).fillna(0)

    combined_df = (
        combined_df.sort_values(
            by=[
                "user_id",
                "movie_id",
                "source_priority",
                "weight",
            ],
            ascending=True,
        )
        .drop_duplicates(
            subset=[
                "user_id",
                "movie_id",
            ],
            keep="last",
        )
        .drop(columns=["source_priority"])
        .reset_index(drop=True)
    )

    combined_df = combined_df.sort_values(
        by=[
            "user_id",
            "movie_id",
        ],
        ascending=True,
    ).reset_index(drop=True)

    return combined_df


def build_summary(
    ratings_df: pd.DataFrame,
    feedback_df: pd.DataFrame,
    original_training_df: pd.DataFrame,
    feedback_training_df: pd.DataFrame,
    final_training_df: pd.DataFrame,
) -> dict:
    label_distribution = (
        final_training_df["label"].value_counts().to_dict()
        if not final_training_df.empty
        else {}
    )

    source_distribution = (
        final_training_df["source"].value_counts().to_dict()
        if not final_training_df.empty
        else {}
    )

    summary = {
        "input": {
            "original_ratings_rows": int(len(ratings_df)),
            "user_movie_feedback_rows": int(len(feedback_df)),
        },
        "converted": {
            "original_training_rows": int(len(original_training_df)),
            "feedback_training_rows": int(len(feedback_training_df)),
            "final_training_rows": int(len(final_training_df)),
        },
        "distribution": {
            "labels": {
                str(k): int(v)
                for k, v in label_distribution.items()
            },
            "sources": {
                str(k): int(v)
                for k, v in source_distribution.items()
            },
        },
        "output": {
            "csv_path": str(OUTPUT_CSV_PATH),
        },
    }

    return summary


def build_retraining_dataset() -> pd.DataFrame:
    print("Loading original ratings...")
    ratings_df = load_original_ratings()

    print("Loading app feedback...")
    feedback_df = load_user_movie_feedback()

    print(f"Original ratings rows: {len(ratings_df):,}")
    print(f"App feedback rows: {len(feedback_df):,}")

    print("Converting original ratings...")
    original_training_df = convert_original_ratings(ratings_df)

    print("Converting app feedback...")
    feedback_training_df = convert_app_feedback(feedback_df)

    print(f"Original training rows: {len(original_training_df):,}")
    print(f"Feedback training rows: {len(feedback_training_df):,}")

    print("Combining training data...")
    final_training_df = combine_training_data(
        original_training_df=original_training_df,
        feedback_training_df=feedback_training_df,
    )

    if final_training_df.empty:
        raise RuntimeError("No retraining rows generated.")

    summary = build_summary(
        ratings_df=ratings_df,
        feedback_df=feedback_df,
        original_training_df=original_training_df,
        feedback_training_df=feedback_training_df,
        final_training_df=final_training_df,
    )

    final_training_df.to_csv(
        OUTPUT_CSV_PATH,
        index=False,
    )

    with open(OUTPUT_SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(
            summary,
            f,
            indent=2,
            default=str,
        )

    print("")
    print("Retraining dataset generated successfully.")
    print(f"CSV output: {OUTPUT_CSV_PATH}")
    print(f"Summary output: {OUTPUT_SUMMARY_PATH}")
    print(f"Final training rows: {len(final_training_df):,}")

    print("")
    print("Label distribution:")
    print(final_training_df["label"].value_counts())

    print("")
    print("Source distribution:")
    print(final_training_df["source"].value_counts())

    return final_training_df


def main() -> None:
    build_retraining_dataset()


if __name__ == "__main__":
    main()