from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.schemas.enums import OfficerRole


class Officer(BaseModel):
    id: UUID
    name: str
    email: str
    role: OfficerRole
    created_at: datetime
