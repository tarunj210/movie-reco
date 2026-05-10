from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db

from app.schemas.content_refresh import (
    ContentRefreshJobResponse,
)

from app.services.content_refresh_jobs import (
    get_content_refresh_job,
)

router = APIRouter(
    prefix="/content-refresh",
    tags=["content-refresh"],
)


@router.get(
    "/jobs/{job_id}",
    response_model=ContentRefreshJobResponse,
)
def get_content_refresh_job_status(
    job_id: int,
    db: Session = Depends(get_db),
):
    job = get_content_refresh_job(
        db=db,
        job_id=job_id,
    )

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Content refresh job not found",
        )

    return job