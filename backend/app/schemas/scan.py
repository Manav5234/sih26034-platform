from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.declaration import Declaration
from app.schemas.enums import ScanStatus, VerificationState


class ImageInfo(BaseModel):
    id: UUID
    url: str
    label: str | None = None
    uploaded_at: datetime


class ImageQuality(BaseModel):
    blur: str
    glare: str
    perspective: str
    resolution: str
    recommended_action: str


class Scan(BaseModel):
    id: UUID
    product_id: UUID | None = None
    status: ScanStatus
    images: list[ImageInfo]
    image_quality: dict[str, ImageQuality] | None = None
    compliance_results: list[Declaration]
    overall_status: VerificationState | None = None
    warnings: list[str]
    created_at: datetime
