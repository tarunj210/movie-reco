from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.auth import LoginRequest
from app.core.security import create_access_token
from app.core.config import USERS_TABLE, USERS_USER_ID_COL, USERS_PW_COL

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    q = text(f"""
        SELECT
            {USERS_USER_ID_COL} AS userid,
            {USERS_PW_COL}      AS passwd
        FROM {USERS_TABLE}
        WHERE {USERS_USER_ID_COL} = :uid
        LIMIT 1
    """)

    row = db.execute(q, {"uid": int(payload.user_id)}).mappings().first()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # INTEGER password comparison (TEMPORARY)
    if int(payload.password) != row["passwd"]:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(sub=str(row["userid"]))
    return {"access_token": token}