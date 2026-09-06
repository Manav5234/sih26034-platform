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
    raw_text: str | None = None
    confidence: float
    image_id: UUID | None = None
    bbox: BBox | None = None
    preprocessing_variant: str | None = None
    extracted_at: datetime
