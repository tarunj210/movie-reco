from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


DEFAULT_WEIGHTS = {
    "description": 0.35,
    "genres": 0.25,
    "keywords": 0.20,
    "director": 0.10,
    "cast": 0.05,
    "production": 0.05,
}

NEGATIVE_PENALTY_WEIGHT = 0.70


def _safe_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _parse_list_like(value: Any) -> list[str]:
    """
    Handles:
    - Python lists
    - stringified lists: "['Action', 'Drama']"
    - comma-separated strings
    - pipe-separated strings
    - empty/null values
    """

    if value is None:
        return []

    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]

    if isinstance(value, float) and pd.isna(value):
        return []

    s = str(value).strip()
    if not s:
        return []

    try:
        parsed = ast.literal_eval(s)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except Exception:
        pass

    if "|" in s:
        return [x.strip() for x in s.split("|") if x.strip()]

    if "," in s:
        return [x.strip() for x in s.split(",") if x.strip()]

    return [s]


def _sanitize_key(value: Any) -> str | None:
    if value is None:
        return None

    s = str(value).strip().lower()
    if not s:
        return None

    s = re.sub(r"\s+", "", s)
    return s or None


def _normalize_movie_columns(movies_df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalizes common column-name differences between:
    - MovieLens-style tables
    - enriched metadata CSVs
    - backend movies_enriched table
    """

    df = movies_df.copy()

    rename_map = {}

    if "movieid" in df.columns and "movie_id" not in df.columns:
        rename_map["movieid"] = "movie_id"

    if "movieId" in df.columns and "movie_id" not in df.columns:
        rename_map["movieId"] = "movie_id"

    if "vote_average" in df.columns and "voteaverage" not in df.columns:
        rename_map["vote_average"] = "voteaverage"

    if "vote_count" in df.columns and "votecount" not in df.columns:
        rename_map["vote_count"] = "votecount"

    df = df.rename(columns=rename_map)

    required = {"movie_id", "title"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"movies dataframe missing required columns: {missing}")

    optional_defaults = {
        "overview": "",
        "tagline": "",
        "description": "",
        "genres": [],
        "keywords": [],
        "director": "",
        "cast": [],
        "production_companies": [],
        "poster_path": "",
        "release_date": "",
        "year": "",
        "voteaverage": 0.0,
        "votecount": 0.0,
    }

    for col, default in optional_defaults.items():
        if col not in df.columns:
            df[col] = default

    df["movie_id"] = df["movie_id"].astype(int)
    df["title"] = df["title"].fillna("").astype(str)

    df["overview"] = df["overview"].fillna("").astype(str)
    df["tagline"] = df["tagline"].fillna("").astype(str)

    if "description" not in df.columns or df["description"].fillna("").eq("").all():
        df["description"] = df["overview"] + " " + df["tagline"]
    else:
        df["description"] = df["description"].fillna("").astype(str)

    df["genres"] = df["genres"].apply(_parse_list_like)
    df["keywords"] = df["keywords"].apply(_parse_list_like)
    df["cast"] = df["cast"].apply(_parse_list_like)
    df["production_companies"] = df["production_companies"].apply(_parse_list_like)

    df["director"] = df["director"].fillna("").astype(str)

    df["genres_text"] = df["genres"].apply(lambda x: " ".join(x))
    df["keywords_text"] = df["keywords"].apply(lambda x: " ".join(x))
    df["cast_text"] = df["cast"].apply(lambda x: " ".join(x[:5]))
    df["production_text"] = df["production_companies"].apply(lambda x: " ".join(x[:3]))
    df["director_text"] = df["director"].apply(lambda x: x.replace(" ", ""))

    return df


@dataclass
class ContentRecommendation:
    movie_id: int
    score: float
    source_movie_ids: list[int]
    reason: str


class ContentRecommender:
    """
    Backend-friendly version of your content recommender.

    It builds:
    - TF-IDF matrix for description/overview
    - Count matrices for genres, keywords, director, cast, production

    Then it generates recommendations from:
    - historical liked movies
    - new positive feedback
    - negative feedback
    """

    def __init__(self, movies_df: pd.DataFrame):
        self.movies = _normalize_movie_columns(movies_df)

        self.movie_id_to_idx = {
            int(movie_id): idx
            for idx, movie_id in enumerate(self.movies["movie_id"].tolist())
        }

        self.idx_to_movie_id = {
            idx: int(movie_id)
            for idx, movie_id in enumerate(self.movies["movie_id"].tolist())
        }

        self.desc_vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            min_df=1,
        )

        self.count_vectorizer = CountVectorizer(
            stop_words="english",
            ngram_range=(1, 1),
            min_df=1,
        )

        self.mat_desc = self.desc_vectorizer.fit_transform(self.movies["description"])

        self.mat_genres = self.count_vectorizer.fit_transform(
            self.movies["genres_text"]
        )

        self.mat_keywords = CountVectorizer(
            stop_words="english",
            ngram_range=(1, 1),
            min_df=1,
        ).fit_transform(self.movies["keywords_text"])

        self.mat_director = CountVectorizer(
            stop_words="english",
            ngram_range=(1, 1),
            min_df=1,
        ).fit_transform(self.movies["director_text"])

        self.mat_cast = CountVectorizer(
            stop_words="english",
            ngram_range=(1, 1),
            min_df=1,
        ).fit_transform(self.movies["cast_text"])

        self.mat_production = CountVectorizer(
            stop_words="english",
            ngram_range=(1, 1),
            min_df=1,
        ).fit_transform(self.movies["production_text"])

    def _valid_movie_ids(self, movie_ids: list[int]) -> list[int]:
        return [int(mid) for mid in movie_ids if int(mid) in self.movie_id_to_idx]

    def _aggregate_similarity(
        self,
        source_movie_ids: list[int],
        weights: dict[str, float] | None = None,
    ) -> np.ndarray:
        weights = weights or DEFAULT_WEIGHTS

        source_movie_ids = self._valid_movie_ids(source_movie_ids)

        if not source_movie_ids:
            return np.zeros(len(self.movies), dtype=float)

        source_indices = [self.movie_id_to_idx[mid] for mid in source_movie_ids]

        total_scores = np.zeros(len(self.movies), dtype=float)

        matrices = [
            ("description", self.mat_desc),
            ("genres", self.mat_genres),
            ("keywords", self.mat_keywords),
            ("director", self.mat_director),
            ("cast", self.mat_cast),
            ("production", self.mat_production),
        ]

        for name, matrix in matrices:
            weight = weights.get(name, 0.0)
            if weight <= 0:
                continue

            source_matrix = matrix[source_indices]

            profile_vector = sparse.csr_matrix(source_matrix.mean(axis=0))
            similarity = cosine_similarity(profile_vector, matrix).flatten()

            total_scores += similarity * weight

        return total_scores

    def _aggregate_similarity_weighted(
        self,
        source_movie_weights: dict[int, float],
        weights: dict[str, float] | None = None,
    ) -> np.ndarray:
        """
        Builds a weighted content profile from source movies.

        Example:
        historical liked movie -> weight 1.0
        new feedback liked movie -> weight 2.0
        """

        weights = weights or DEFAULT_WEIGHTS

        valid_items = {
            int(movie_id): float(weight)
            for movie_id, weight in source_movie_weights.items()
            if int(movie_id) in self.movie_id_to_idx and float(weight) > 0
        }

        if not valid_items:
            return np.zeros(len(self.movies), dtype=float)

        source_movie_ids = list(valid_items.keys())
        source_indices = [self.movie_id_to_idx[mid] for mid in source_movie_ids]
        source_weights = np.array(
            [valid_items[mid] for mid in source_movie_ids],
            dtype=float,
        )

        total_weight = float(source_weights.sum())
        if total_weight == 0:
            return np.zeros(len(self.movies), dtype=float)

        total_scores = np.zeros(len(self.movies), dtype=float)

        matrices = [
            ("description", self.mat_desc),
            ("genres", self.mat_genres),
            ("keywords", self.mat_keywords),
            ("director", self.mat_director),
            ("cast", self.mat_cast),
            ("production", self.mat_production),
        ]

        for name, matrix in matrices:
            feature_weight = weights.get(name, 0.0)
            if feature_weight <= 0:
                continue

            source_matrix = matrix[source_indices]

            weighted_source_matrix = source_matrix.multiply(source_weights[:, None])
            profile_vector = sparse.csr_matrix(
                weighted_source_matrix.sum(axis=0) / total_weight
            )

            similarity = cosine_similarity(profile_vector, matrix).flatten()
            total_scores += similarity * feature_weight

        return total_scores

    def generate_from_feedback(
        self,
        positive_movie_ids: list[int],
        negative_movie_ids: list[int] | None = None,
        top_k: int = 50,
        exclude_feedback_movies_from_generated_candidates: bool = False,
    ) -> list[ContentRecommendation]:
        """
        Generates content candidates from only explicit feedback movies.
        """

        negative_movie_ids = negative_movie_ids or []

        positive_movie_ids = self._valid_movie_ids(positive_movie_ids)
        negative_movie_ids = self._valid_movie_ids(negative_movie_ids)

        if not positive_movie_ids:
            return []

        positive_scores = self._aggregate_similarity(positive_movie_ids)
        negative_scores = self._aggregate_similarity(negative_movie_ids)

        final_scores = positive_scores - (NEGATIVE_PENALTY_WEIGHT * negative_scores)
        final_scores = np.maximum(final_scores, 0.0)

        for movie_id in negative_movie_ids:
            idx = self.movie_id_to_idx[movie_id]
            final_scores[idx] = 0.0

        if exclude_feedback_movies_from_generated_candidates:
            for movie_id in positive_movie_ids + negative_movie_ids:
                idx = self.movie_id_to_idx[movie_id]
                final_scores[idx] = 0.0

        candidate_indices = np.argsort(final_scores)[::-1]

        recommendations: list[ContentRecommendation] = []

        for idx in candidate_indices:
            score = float(final_scores[idx])

            if score <= 0:
                continue

            movie_id = self.idx_to_movie_id[idx]

            recommendations.append(
                ContentRecommendation(
                    movie_id=movie_id,
                    score=round(score, 6),
                    source_movie_ids=positive_movie_ids,
                    reason="Generated from movies you liked or rated highly",
                )
            )

            if len(recommendations) >= top_k:
                break

        return recommendations


    def generate_from_user_profile(
        self,
        historical_positive_movie_ids: list[int],
        feedback_positive_movie_ids: list[int],
        feedback_negative_movie_ids: list[int],
        exclude_movie_ids: list[int] | None = None,
        top_k: int = 50,
        exclude_feedback_movies_from_generated_candidates: bool = False,
    ) -> list[ContentRecommendation]:
        """
        Generates content candidates using both:
        - user's historical liked movies from ratings
        - user's new explicit feedback

        Historical likes are stable long-term signal.
        New feedback is stronger recent signal.
        Negative feedback penalizes similar movies.
        """
        exclude_movie_ids = exclude_movie_ids or []
        positive_weights: dict[int, float] = {}

        for movie_id in historical_positive_movie_ids:
            movie_id = int(movie_id)

            if movie_id in self.movie_id_to_idx:
                positive_weights[movie_id] = max(
                    positive_weights.get(movie_id, 0.0),
                    1.0,
                )

        for movie_id in feedback_positive_movie_ids:
            movie_id = int(movie_id)

            if movie_id in self.movie_id_to_idx:
                positive_weights[movie_id] = max(
                    positive_weights.get(movie_id, 0.0),
                    2.0,
                )

        negative_weights: dict[int, float] = {}

        for movie_id in feedback_negative_movie_ids:
            movie_id = int(movie_id)

            if movie_id in self.movie_id_to_idx:
                negative_weights[movie_id] = 1.5

        if not positive_weights:
            return []

        positive_scores = self._aggregate_similarity_weighted(positive_weights)
        negative_scores = self._aggregate_similarity_weighted(negative_weights)

        final_scores = positive_scores - (NEGATIVE_PENALTY_WEIGHT * negative_scores)
        final_scores = np.maximum(final_scores, 0.0)

        # Do not generate exact disliked movies as new content candidates.
        # This does not remove them from the current frontend display.
        for movie_id in feedback_negative_movie_ids:
            movie_id = int(movie_id)

            if movie_id in self.movie_id_to_idx:
                idx = self.movie_id_to_idx[movie_id]
                final_scores[idx] = 0.0

        for movie_id in exclude_movie_ids:
            movie_id = int(movie_id)

            if movie_id in self.movie_id_to_idx:
                idx = self.movie_id_to_idx[movie_id]
                final_scores[idx] = 0.0

        if exclude_feedback_movies_from_generated_candidates:
            all_feedback_movie_ids = (
                set(historical_positive_movie_ids)
                | set(feedback_positive_movie_ids)
                | set(feedback_negative_movie_ids)
            )

            for movie_id in all_feedback_movie_ids:
                movie_id = int(movie_id)

                if movie_id in self.movie_id_to_idx:
                    idx = self.movie_id_to_idx[movie_id]
                    final_scores[idx] = 0.0

        candidate_indices = np.argsort(final_scores)[::-1]

        source_movie_ids = sorted(
            {
                int(mid)
                for mid in list(historical_positive_movie_ids)
                + list(feedback_positive_movie_ids)
                if int(mid) in self.movie_id_to_idx
            }
        )

        recommendations: list[ContentRecommendation] = []

        for idx in candidate_indices:
            score = float(final_scores[idx])

            if score <= 0:
                continue

            movie_id = self.idx_to_movie_id[idx]

            recommendations.append(
                ContentRecommendation(
                    movie_id=movie_id,
                    score=round(score, 6),
                    source_movie_ids=source_movie_ids,
                    reason="Generated from your watch history and latest movie feedback",
                )
            )

            if len(recommendations) >= top_k:
                break

        return recommendations