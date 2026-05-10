from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ContentRefreshJobResponse(BaseModel):
    id: int
    user_id: int
    feedback_count: int

    status: str

    created_at: datetime

    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    error_message: Optional[str] = None