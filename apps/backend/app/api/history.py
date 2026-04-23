from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(prefix="/users", tags=["history"])

@router.get("/me/history")
def user_history(
    user_id: int,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    q = text("""
    SELECT
        r.movieid AS "movieId",
        m.title   AS "title",
        m.genres  AS "genres",
        m.poster_path AS "poster_path",
        m.director AS "director",
        r.timestamp AS "timestamp"
    FROM ratings r
    JOIN movies_enriched m
      ON r.movieid = m.movieid
    WHERE r.userid = :uid
      AND r.rating >= 3.5
    ORDER BY r.timestamp DESC
    LIMIT :lim
    """)

    rows = db.execute(q, {"uid": user_id, "lim": int(limit)}).mappings().all()

    history = []
    for r in rows:
        history.append({
            "movieId": int(r["movieId"]),
            "title": r["title"],
            "genres": r.get("genres", ""),
            "poster": r.get("poster_path", ""),
            "director": r.get("director", ""),
            "timestamp": int(r["timestamp"]) if r["timestamp"] else None,
        })

    return {"user_id": user_id, "history": history}