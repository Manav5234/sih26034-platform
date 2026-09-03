from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel


class InspectionAction(BaseModel):
    declaration_id: UUID
    action: str  # "confirm" | "correct" | "mark_unresolved"
    old_value: Any
    new_value: Optional[Any] = None
    reason: str


class Inspection(BaseModel):
    id: UUID
    scan_id: UUID
    officer_id: UUID
    actions: List[InspectionAction]
    notes: Optional[str] = None
    created_at: datetime
