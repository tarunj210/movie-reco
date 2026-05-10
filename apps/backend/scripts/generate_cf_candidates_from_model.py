from __future__ import annotations

import json
import os
from pathlib import Path

import joblib
import numpy as np
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

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


MODELS_DIR = BASE_DIR / "artifacts" / "models"

MODEL_DIR_ENV = os.getenv("NEUMF_MODEL_DIR")

if MODEL_DIR_ENV:
    MODEL_DIR = Path(MODEL_DIR_ENV)
else:
    candidate_dirs = [
        path
        for path in MODELS_DIR.iterdir()
        if path.is_dir() and path.name.startswith("neumf-local-")
    ]

    if not candidate_dirs:
        raise RuntimeError(
            "No local NeuMF model directory found under artifacts/models. "
            "Run scripts/train_neumf_existing.py first."
        )

    MODEL_DIR = sorted(
        candidate_dirs,
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[0]


USER_ENCODER_PATH = MODEL_DIR / "user_encoder.joblib"
ITEM_ENCODER_PATH = MODEL_DIR / "item_encoder.joblib"
ITEM_VECTORS_PATH = MODEL_DIR / "item_vectors.npy"
METADATA_PATH = MODEL_DIR / "training_metadata.json"


TOP_K = int(os.getenv("CF_CANDIDATES_TOP_K", "50"))
MAX_USERS = int(os.getenv("CF_CANDIDATES_MAX_USERS", "0"))

POSITIVE_RATING_THRESHOLD = float(os.getenv("CF_POSITIVE_RATING_THRESHOLD", "4.0"))
NEGATIVE_RATING_THRESHOLD = float(os.getenv("CF_NEGATIVE_RATING_THRESHOLD", "2.0"))


def load_artifacts():
    print(f"Loading NeuMF artifacts from: {MODEL_DIR}")

    if not USER_ENCODER_PATH.exists():
        raise FileNotFoundError(USER_ENCODER_PATH)

    if not ITEM_ENCODER_PATH.exists():
        raise FileNotFoundError(ITEM_ENCODER_PATH)

    if not ITEM_VECTORS_PATH.exists():
        raise FileNotFoundError(ITEM_VECTORS_PATH)

    user_encoder = joblib.load(USER_ENCODER_PATH)
    item_encoder = joblib.load(ITEM_ENCODER_PATH)
    item_vectors = np.load(ITEM_VECTORS_PATH)

    metadata = {}

    if METADATA_PATH.exists():
        with open(METADATA_PATH, "r", encoding="utf-8") as f:
            metadata = json.load(f)

    model_version = metadata.get("model_version") or MODEL_DIR.name

    print(f"Loaded item vectors: {item_vectors.shape}")
    print(f"Model version: {model_version}")

    return user_encoder, item_encoder, item_vectors, model_version


def normalize_vectors(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.clip(norms, 1e-8, None)


def get_user_ids_to_process(user_encoder) -> list[int]:
    """
    Process only users known to the retrained model.
    """

    user_ids = [int(x) for x in user_encoder.classes_.tolist()]

    if MAX_USERS and len(user_ids) > MAX_USERS:
        user_ids = user_ids[:MAX_USERS]

    return user_ids


def get_user_seen_positive_negative_movies(user_id: int) -> tuple[set[int], set[int], set[int]]:
    """
    Returns:
    - seen_movie_ids: all ratings + all feedback movies
    - positive_movie_ids: liked/high-rated movies
    - negative_movie_ids: disliked/low-rated movies
    """

    ratings_query = text("""
        SELECT
            movieid,
            rating
        FROM ratings
        WHERE userid = :user_id
    """)

    feedback_query = text("""
        SELECT
            movie_id,
            rating,
            liked,
            disliked
        FROM user_movie_feedback
        WHERE user_id = :user_id
    """)

    seen_movie_ids: set[int] = set()
    positive_movie_ids: set[int] = set()
    negative_movie_ids: set[int] = set()

    with engine.begin() as conn:
        rating_rows = conn.execute(
            ratings_query,
            {
                "user_id": user_id,
            },
        ).mappings().all()

        feedback_rows = conn.execute(
            feedback_query,
            {
                "user_id": user_id,
            },
        ).mappings().all()

    for row in rating_rows:
        movie_id = int(row["movieid"])
        rating = float(row["rating"])

        seen_movie_ids.add(movie_id)

        if rating >= POSITIVE_RATING_THRESHOLD:
            positive_movie_ids.add(movie_id)

        if rating <= NEGATIVE_RATING_THRESHOLD:
            negative_movie_ids.add(movie_id)

    for row in feedback_rows:
        movie_id = int(row["movie_id"])
        seen_movie_ids.add(movie_id)

        rating_value = row["rating"]
        liked = bool(row["liked"])
        disliked = bool(row["disliked"])

        if rating_value is not None:
            rating_value = float(rating_value)

        if liked or (rating_value is not None and rating_value >= POSITIVE_RATING_THRESHOLD):
            positive_movie_ids.add(movie_id)

        if disliked or (rating_value is not None and rating_value <= NEGATIVE_RATING_THRESHOLD):
            negative_movie_ids.add(movie_id)

    return seen_movie_ids, positive_movie_ids, negative_movie_ids


def safe_movie_ids_to_item_indices(movie_ids: set[int], item_encoder) -> list[int]:
    """
    Converts raw movie IDs to item indices, skipping unknown movies.
    """

    known_movie_ids = set(int(x) for x in item_encoder.classes_.tolist())

    valid_movie_ids = [
        int(movie_id)
        for movie_id in movie_ids
        if int(movie_id) in known_movie_ids
    ]

    if not valid_movie_ids:
        return []

    return [
        int(idx)
        for idx in item_encoder.transform(valid_movie_ids)
    ]


def item_indices_to_movie_ids(item_indices: np.ndarray, item_encoder) -> list[int]:
    return [
        int(movie_id)
        for movie_id in item_encoder.inverse_transform(item_indices)
    ]


def generate_cf_candidates_for_user(
    user_id: int,
    item_encoder,
    item_vectors: np.ndarray,
    top_k: int,
) -> list[dict]:
    seen_movie_ids, positive_movie_ids, negative_movie_ids = (
        get_user_seen_positive_negative_movies(user_id)
    )

    positive_item_indices = safe_movie_ids_to_item_indices(
        positive_movie_ids,
        item_encoder,
    )

    negative_item_indices = safe_movie_ids_to_item_indices(
        negative_movie_ids,
        item_encoder,
    )

    seen_item_indices = set(
        safe_movie_ids_to_item_indices(
            seen_movie_ids,
            item_encoder,
        )
    )

    if not positive_item_indices:
        return []

    positive_vectors = item_vectors[positive_item_indices]
    user_profile = positive_vectors.mean(axis=0)

    user_profile_norm = np.linalg.norm(user_profile)

    if user_profile_norm <= 1e-8:
        return []

    user_profile = user_profile / user_profile_norm

    scores = item_vectors @ user_profile

    # Exclude already seen movies.
    for idx in seen_item_indices:
        scores[idx] = -1.0

    # Strongly exclude disliked/negative movies.
    for idx in negative_item_indices:
        scores[idx] = -1.0

    top_indices = np.argsort(-scores)[:top_k]
    top_scores = scores[top_indices]

    top_movie_ids = item_indices_to_movie_ids(
        top_indices,
        item_encoder,
    )

    candidates: list[dict] = []

    for rank, (movie_id, score) in enumerate(
        zip(top_movie_ids, top_scores),
        start=1,
    ):
        if score <= 0:
            continue

        candidates.append(
            {
                "user_id": user_id,
                "movie_id": int(movie_id),
                "score": float(score),
                "rank": rank,
                "reason": "Generated from retrained collaborative filtering embeddings",
            }
        )

    return candidates


def save_user_cf_candidates(
    user_id: int,
    candidates: list[dict],
    model_version: str,
) -> None:
    delete_query = text("""
        DELETE FROM user_cf_candidates
        WHERE user_id = :user_id
    """)

    insert_query = text("""
        INSERT INTO user_cf_candidates (
            user_id,
            movie_id,
            score,
            rank,
            reason,
            model_version,
            generated_at
        )
        VALUES (
            :user_id,
            :movie_id,
            :score,
            :rank,
            :reason,
            :model_version,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (user_id, movie_id)
        DO UPDATE SET
            score = EXCLUDED.score,
            rank = EXCLUDED.rank,
            reason = EXCLUDED.reason,
            model_version = EXCLUDED.model_version,
            generated_at = CURRENT_TIMESTAMP
    """)

    with engine.begin() as conn:
        conn.execute(
            delete_query,
            {
                "user_id": user_id,
            },
        )

        for candidate in candidates:
            conn.execute(
                insert_query,
                {
                    "user_id": candidate["user_id"],
                    "movie_id": candidate["movie_id"],
                    "score": candidate["score"],
                    "rank": candidate["rank"],
                    "reason": candidate["reason"],
                    "model_version": model_version,
                },
            )


def generate_all_cf_candidates() -> None:
    user_encoder, item_encoder, item_vectors, model_version = load_artifacts()

    item_vectors = normalize_vectors(item_vectors)

    user_ids = get_user_ids_to_process(user_encoder)

    print(f"Users to process: {len(user_ids):,}")
    print(f"Top K per user: {TOP_K}")

    total_saved = 0

    for index, user_id in enumerate(user_ids, start=1):
        candidates = generate_cf_candidates_for_user(
            user_id=user_id,
            item_encoder=item_encoder,
            item_vectors=item_vectors,
            top_k=TOP_K,
        )

        if candidates:
            save_user_cf_candidates(
                user_id=user_id,
                candidates=candidates,
                model_version=model_version,
            )

            total_saved += len(candidates)

        if index % 100 == 0:
            print(
                f"Processed users: {index:,}/{len(user_ids):,} "
                f"| total saved candidates: {total_saved:,}"
            )

    print("")
    print("CF candidate generation completed.")
    print(f"Users processed: {len(user_ids):,}")
    print(f"Total candidates saved: {total_saved:,}")
    print(f"Model version: {model_version}")


def main() -> None:
    generate_all_cf_candidates()


if __name__ == "__main__":
    main()