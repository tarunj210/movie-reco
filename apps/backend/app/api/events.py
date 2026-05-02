from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.events import InteractionEventRequest, InteractionEventResponse
from app.services.events import save_interaction

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", response_model=InteractionEventResponse)
def create_event(
    payload: InteractionEventRequest,
    db: Session = Depends(get_db),
):
    try:
        result = save_interaction(
            db=db,
            user_id=payload.user_id,
            movie_id=payload.movie_id,
            event_type=payload.event_type,
            event_value=payload.event_value,
            source=payload.source,
            rank=payload.rank,
            metadata=payload.metadata,
        )

        db.commit()

        return InteractionEventResponse(
            id=result["event_id"],
            user_id=payload.user_id,
            movie_id=payload.movie_id,
            event_type=payload.event_type,
            event_value=payload.event_value,
            message="Event logged successfully",
            feedback_updated=result["feedback_updated"],
            feedback_count=result["feedback_count"],
            content_refresh_job_created=result["content_refresh_job_created"],
            content_refresh_job_id=result["content_refresh_job_id"],
        )

    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    except Exception:
        db.rollback()
        raise