from sqlalchemy import text
from sqlalchemy.orm import Session


def get_content_refresh_job(
    db: Session,
    job_id: int,
):
    query = text("""
        SELECT
            id,
            user_id,
            feedback_count,
            status,
            created_at,
            started_at,
            finished_at,
            error_message
        FROM content_refresh_jobs
        WHERE id = :job_id
    """)

    row = db.execute(
        query,
        {
            "job_id": job_id,
        },
    ).mappings().first()

    if not row:
        return None

    return dict(row)