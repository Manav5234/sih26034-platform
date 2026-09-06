from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.enums import FlagStatus


class FlagCreateRequest(BaseModel):
    reported_fields: list[str]
    reporter_note: str | None = None
    reporter_contact: str | None = None


class FlagCreateResponse(BaseModel):
    id: UUID
    status: FlagStatus


class FlagListItem(BaseModel):
    id: UUID
    scan_id: UUID
    reported_fields: list[str]
    reporter_note: str | None = None
    status: FlagStatus
    created_at: datetime


class PaginatedFlags(BaseModel):
    items: list[FlagListItem]
    total: int
    page: int
    page_size: int


class FlagDetail(BaseModel):
    id: UUID
    scan_id: UUID
    reported_fields: list[str]
    reporter_note: str | None = None
    reporter_contact: str | None = None
    status: FlagStatus
    created_at: datetime
    reviewed_by_officer_id: UUID | None = None
    reviewed_at: datetime | None = None
    officer_notes: str | None = None


class FlagReviewRequest(BaseModel):
    status: FlagStatus  # ACKNOWLEDGED | RESOLVED | DISMISSED
    officer_notes: str | None = None
