from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel


class InspectionAction(BaseModel):
    declaration_id: UUID
    field_name: Optional[str] = None
    action: str  # "confirm" | "correct" | "mark_unresolved"
    old_value: Any
    new_value: Optional[Any] = None
    reason: str


class InspectionLocation(BaseModel):
    latitude: float
    longitude: float
    accuracy_meters: Optional[float] = None
    source: str  # "GPS" | "MANUAL"
    address_text: Optional[str] = None


class InspectionRequest(BaseModel):
    """Request body for POST /inspection. officer_id comes from JWT, not here."""
    scan_id: UUID
    actions: List[InspectionAction]
    notes: Optional[str] = None
    location: Optional[InspectionLocation] = None


class InspectionLocationOut(BaseModel):
    latitude: float
    longitude: float
    accuracy_meters: Optional[float] = None
    source: str
    address_text: Optional[str] = None
    captured_at: datetime


class Inspection(BaseModel):
    id: UUID
    scan_id: UUID
    officer_id: UUID
    actions: List[InspectionAction]
    notes: Optional[str] = None
    location: Optional[InspectionLocationOut] = None
    created_at: datetime
