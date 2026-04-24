from __future__ import annotations
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

APP_ENV_FILE = os.getenv("APP_ENV_FILE", ".env.local")
ENV_FILE = BASE_DIR / APP_ENV_FILE

load_dotenv(ENV_FILE, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError(f"DATABASE_URL is not set in {ENV_FILE}")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()