from __future__ import annotations

from datetime import datetime
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
    declaration_id: Optional[UUID] = None
    field_name: str
    evidence: List[Evidence]


class ScanComplianceResponse(BaseModel):
    declarations: List[Declaration]
    overall_status: Optional[VerificationState] = None


class DashboardResponse(BaseModel):
    total_scans: int
    scans_pending_review: int
    violations_ai: int
    violations_officer_confirmed: int
    not_verified: int
    conflict: int
    scans_today: int
    scans_this_week: int


class ProductListItem(BaseModel):
    id: UUID
    identity: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    manufacturer: Optional[str] = None
    barcode_code: Optional[str] = None
    mrp_amount: Optional[float] = None
    latest_scan_status: Optional[str] = None
    total_scans: int = 0
    created_at: datetime


class PaginatedProducts(BaseModel):
    items: List[ProductListItem]
    total: int
    page: int
    page_size: int


class ScanListItem(BaseModel):
    id: UUID
    status: str
    overall_status: Optional[str] = None
    product_name: Optional[str] = None
    barcode: Optional[str] = None
    has_inspection: bool = False
    declarations_count: int = 0
    created_at: datetime


class PaginatedScans(BaseModel):
    items: List[ScanListItem]
    total: int
    page: int
    page_size: int


class InspectionListItem(BaseModel):
    id: UUID
    scan_id: UUID
    officer_id: UUID
    officer_name: Optional[str] = None
    actions_count: int = 0
    notes: Optional[str] = None
    created_at: datetime


class PaginatedInspections(BaseModel):
    items: List[InspectionListItem]
    total: int
    page: int
    page_size: int


class AuthLoginRequest(BaseModel):
    email: str
    password: str


class AuthOfficer(BaseModel):
    id: UUID
    role: str


class AuthLoginResponse(BaseModel):
    token: str
    officer: AuthOfficer
