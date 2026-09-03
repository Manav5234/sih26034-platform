from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.schemas.enums import EvidenceSourceType
from app.schemas.geometry import BBox


class Evidence(BaseModel):
    id: UUID
    source_type: EvidenceSourceType
    raw_text: Optional[str] = None
    confidence: float
    image_id: Optional[UUID] = None
    bbox: Optional[BBox] = None
    preprocessing_variant: Optional[str] = None
    extracted_at: datetime
