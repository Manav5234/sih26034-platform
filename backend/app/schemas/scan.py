from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel

from app.schemas.enums import ScanStatus, VerificationState
from app.schemas.declaration import Declaration


class ImageInfo(BaseModel):
    id: UUID
    url: str
    uploaded_at: datetime


class ImageQuality(BaseModel):
    blur: str
    glare: str
    perspective: str
    resolution: str
    recommended_action: str


class Scan(BaseModel):
    id: UUID
    product_id: Optional[UUID] = None
    status: ScanStatus
    images: List[ImageInfo]
    image_quality: Optional[Dict[str, ImageQuality]] = None
    compliance_results: List[Declaration]
    overall_status: Optional[VerificationState] = None
    warnings: List[str]
    created_at: datetime
