from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.declaration import Declaration
from app.schemas.enums import ScanStatus, VerificationState
from app.schemas.evidence import Evidence


class HealthResponse(BaseModel):
    status: str
    service: str


class ScanCreateResponse(BaseModel):
    scan_id: UUID
    status: ScanStatus


class ImageUploadResponse(BaseModel):
    image_id: UUID


class ScanEvidenceGroup(BaseModel):
    declaration_id: UUID | None = None
    field_name: str
    evidence: list[Evidence]


class ScanComplianceResponse(BaseModel):
    declarations: list[Declaration]
    overall_status: VerificationState | None = None


class DashboardResponse(BaseModel):
    total_scans: int
    scans_pending_review: int
    violations_ai: int
    violations_officer_confirmed: int
    not_verified: int
    conflict: int
    scans_today: int
    scans_this_week: int
    pending_flags: int


class ProductListItem(BaseModel):
    id: UUID
    identity: str | None = None
    brand: str | None = None
    category: str | None = None
    manufacturer: str | None = None
    barcode_code: str | None = None
    mrp_amount: float | None = None
    latest_scan_status: str | None = None
    total_scans: int = 0
    created_at: datetime


class PaginatedProducts(BaseModel):
    items: list[ProductListItem]
    total: int
    page: int
    page_size: int


class ScanListItem(BaseModel):
    id: UUID
    status: str
    overall_status: str | None = None
    product_name: str | None = None
    barcode: str | None = None
    has_inspection: bool = False
    declarations_count: int = 0
    created_at: datetime


class PaginatedScans(BaseModel):
    items: list[ScanListItem]
    total: int
    page: int
    page_size: int


class InspectionListItem(BaseModel):
    id: UUID
    scan_id: UUID
    officer_id: UUID
    officer_name: str | None = None
    actions_count: int = 0
    notes: str | None = None
    created_at: datetime


class PaginatedInspections(BaseModel):
    items: list[InspectionListItem]
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
