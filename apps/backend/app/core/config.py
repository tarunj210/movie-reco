from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env in backend root
# Example expected location:
# apps/backend/.env
BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        raise ValueError(f"Missing required environment variable: {name}")
    return value.strip()


def _get_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer") from exc


def _get_list_env(name: str, default: list[str] | None = None) -> list[str]:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default or []
    return [item.strip() for item in value.split(",") if item.strip()]


# -------------------------------------------------------------------
# Application
# -------------------------------------------------------------------
APP_NAME = os.getenv("APP_NAME", "movie-reco-backend")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
DEBUG = _get_bool_env("DEBUG", default=True)

HOST = os.getenv("HOST", "0.0.0.0")
PORT = _get_int_env("PORT", 8000)

# -------------------------------------------------------------------
# Database
# -------------------------------------------------------------------
DATABASE_URL = _get_required_env("DATABASE_URL")

# -------------------------------------------------------------------
# JWT / Auth
# -------------------------------------------------------------------
JWT_SECRET = _get_required_env("JWT_SECRET")
JWT_ALG = os.getenv("JWT_ALG", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = _get_int_env("ACCESS_TOKEN_EXPIRE_MINUTES", 60)

# -------------------------------------------------------------------
# CORS
# Comma-separated list in .env
# Example:
# ALLOWED_ORIGINS=http://localhost:5173,https://your-frontend-domain.com
# -------------------------------------------------------------------
ALLOWED_ORIGINS = _get_list_env(
    "ALLOWED_ORIGINS",
    default=["http://localhost:5173"],
)

# -------------------------------------------------------------------
# Data paths
# These are resolved relative to backend root:
# apps/backend/data/...
# -------------------------------------------------------------------
DATA_DIR = BASE_DIR / "data"

CF_RECS_PATH = Path(
    os.getenv("CF_RECS_PATH", str(DATA_DIR / "cf_top50_recommendations.csv"))
).resolve()

CONTENT_RECS_PATH = Path(
    os.getenv("CONTENT_RECS_PATH", str(DATA_DIR / "final_movie_recommendations_mapped.csv"))
).resolve()

# Optional future model/artifact path
MODEL_DIR = Path(
    os.getenv("MODEL_DIR", str(BASE_DIR / "models"))
).resolve()

# -------------------------------------------------------------------
# Existing schema/table constants from your current codebase
# -------------------------------------------------------------------
USERS_TABLE = "users"
USERS_USER_ID_COL = "userid"
USERS_PW_COL = "passwd"

RATINGS_TABLE = "ratings"
RATINGS_USER_ID_COL = "userid"
RATINGS_MOVIE_ID_COL = "movieid"
RATINGS_TS_COL = "timestamp"

MOVIES_TABLE = "movies_enriched"
MOVIES_MOVIE_ID_COL = "movieid"
MOVIES_TITLE_COL = "title"

# -------------------------------------------------------------------
# Optional OpenAI / LLM config for future use
# Safe to leave unset for now
# -------------------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

# -------------------------------------------------------------------
# Startup validation
# -------------------------------------------------------------------
def validate_paths() -> None:
    missing_files: list[str] = []

    if not CF_RECS_PATH.exists():
        missing_files.append(f"CF_RECS_PATH not found: {CF_RECS_PATH}")

    if not CONTENT_RECS_PATH.exists():
        missing_files.append(f"CONTENT_RECS_PATH not found: {CONTENT_RECS_PATH}")

    if missing_files:
        raise FileNotFoundError(" | ".join(missing_files))