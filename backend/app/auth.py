from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import bcrypt
import jwt
from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Officer as OfficerDB
from app.database import engine

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 hours


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(officer_id: UUID, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(officer_id),
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def _get_current_officer(
    token: Optional[str] = Depends(oauth2_scheme),
    token_cookie: Optional[str] = Cookie(None, alias="access_token"),
) -> OfficerDB:
    # Accept token from Authorization header OR httpOnly cookie
    raw = token or token_cookie
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = jwt.decode(raw, settings.jwt_secret, algorithms=[ALGORITHM])
        officer_id = UUID(payload["sub"])
        role = payload["role"]
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    with Session(engine) as db:
        officer = db.get(OfficerDB, officer_id)
        if officer is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Officer not found")
        return officer


def get_current_officer(officer: OfficerDB = Depends(_get_current_officer)) -> OfficerDB:
    return officer


def require_role(*allowed_roles: str):
    def _dep(officer: OfficerDB = Depends(get_current_officer)) -> OfficerDB:
        if officer.role.value not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return officer
    return _dep
