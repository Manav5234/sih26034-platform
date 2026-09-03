from __future__ import annotations

from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel

from app.schemas.enums import ScanStatus, VerificationState
from app.schemas.evidence import Evidence
from app.schemas.declaration import Declaration
from app.schemas.scan import Scan, ImageInfo
from app.schemas.inspection import Inspection
from app.schemas.product import CanonicalProduct
from app.schemas.rule import RuleSet
from app.schemas.officer import Officer


class HealthResponse(BaseModel):
    status: str
    service: str


class ScanCreateResponse(BaseModel):
    scan_id: UUID
    status: ScanStatus


class ImageUploadResponse(BaseModel):
    image_id: UUID


class ScanEvidenceGroup(BaseModel):
    declaration_id: UUID
    field_name: str
    evidence: List[Evidence]


class ScanComplianceResponse(BaseModel):
    declarations: List[Declaration]
    overall_status: Optional[VerificationState] = None


class DashboardResponse(BaseModel):
    total_scans: int
    violations: int
    not_verified_rate: float
    recent_inspections: List[Inspection]


class AuthLoginRequest(BaseModel):
    email: str
    password: str


class AuthOfficer(BaseModel):
    id: UUID
    role: str


class AuthLoginResponse(BaseModel):
    token: str
    officer: AuthOfficer
