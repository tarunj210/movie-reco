from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class InteractionEventRequest(BaseModel):
    user_id: int
    movie_id: int | None = None
    event_type: str = Field(..., examples=["movie_click", "movie_rating"])
    event_value: float | None = None
    source: str | None = None
    rank: int | None = None
    metadata: dict[str, Any] | None = None


class InteractionEventResponse(BaseModel):
    id: int
    user_id: int
    movie_id: int | None
    event_type: str
    event_value: float | None
    message: str

    feedback_updated: bool = False
    feedback_count: int | None = None
    content_refresh_job_created: bool = False
    content_refresh_job_id: int | None = None