from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel

from app.schemas.enums import VerificationState
from app.schemas.evidence import Evidence


class OfficerCorrection(BaseModel):
    officer_id: UUID
    officer_name: str | None = None
    corrected_value: Any
    reason: str
    corrected_at: datetime


class Declaration(BaseModel):
    id: UUID
    scan_id: UUID
    field_name: str
    extracted_value: Any
    evidence: list[Evidence]
    rule_id: str | None = None
    verdict: VerificationState
    reason: str
    confidence: float
    officer_correction: OfficerCorrection | None = None
