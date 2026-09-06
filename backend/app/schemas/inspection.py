from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class InspectionAction(BaseModel):
    declaration_id: UUID
    field_name: str | None = None
    action: str  # "confirm" | "correct" | "mark_unresolved"
    old_value: Any
    new_value: Any | None = None
    reason: str


class InspectionLocation(BaseModel):
    latitude: float
    longitude: float
    accuracy_meters: float | None = None
    source: str  # "GPS" | "MANUAL"
    address_text: str | None = None


class InspectionRequest(BaseModel):
    """Request body for POST /inspection. officer_id comes from JWT, not here."""
    scan_id: UUID
    actions: list[InspectionAction]
    notes: str | None = None
    location: InspectionLocation | None = None


class InspectionLocationOut(BaseModel):
    latitude: float
    longitude: float
    accuracy_meters: float | None = None
    source: str
    address_text: str | None = None
    captured_at: datetime


class Inspection(BaseModel):
    id: UUID
    scan_id: UUID
    officer_id: UUID
    actions: list[InspectionAction]
    notes: str | None = None
    location: InspectionLocationOut | None = None
    created_at: datetime
