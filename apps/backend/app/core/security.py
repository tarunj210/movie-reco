from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import HTTPException
from jose import jwt, JWTError

from app.core.config import JWT_SECRET, JWT_ALG, ACCESS_TOKEN_EXPIRE_MINUTES

def create_access_token(sub: str) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": sub, "iat": int(now.timestamp()), "exp": exp}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def verify_access_token(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return str(user_id)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")