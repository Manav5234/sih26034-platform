from datetime import date, datetime
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session, joinedload

from app.auth import create_access_token, get_current_officer, require_role, verify_password
from app.config import settings
from app.db.models import (
    Officer as OfficerDB,
    Scan as ScanDB,
    Image as ImageDB,
    Declaration as DeclDB,
    Evidence as EvDB,
    ComplianceResult as CRDB,
    VerificationState,
    ScanStatus,
)
from app.database import engine
from app.storage import storage
from app.pipeline import run_mocked_pipeline

from app.schemas.api import (
    AuthLoginRequest,
    AuthLoginResponse,
    AuthOfficer,
    DashboardResponse,
    HealthResponse,
    ImageUploadResponse,
    ScanComplianceResponse,
    ScanCreateResponse,
    ScanEvidenceGroup,
)
from app.schemas.declaration import Declaration
from app.schemas.enums import (
    OfficerRole,
)
from app.schemas.evidence import Evidence
from app.schemas.geometry import BBox
from app.schemas.inspection import Inspection, InspectionAction
from app.schemas.officer import Officer
from app.schemas.product import CanonicalProduct, Barcode, Dates, MRP, Quantity, UnitSalePrice
from app.schemas.rule import Rule, RuleSet
from app.schemas.scan import ImageInfo, ImageQuality, Scan

app = FastAPI(title="SIH26034 Legal Metrology Compliance Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def _db_image_to_schema(img: ImageDB) -> ImageInfo:
    return ImageInfo(id=img.id, url=img.url, uploaded_at=img.uploaded_at)


def _db_ev_to_schema(ev: EvDB) -> Evidence:
    return Evidence(
        id=ev.id,
        source_type=ev.source_type.value,
        raw_text=ev.raw_text,
        confidence=ev.confidence,
        image_id=ev.image_id,
        bbox=BBox(**ev.bbox) if ev.bbox else None,
        preprocessing_variant=ev.preprocessing_variant,
        extracted_at=ev.extracted_at,
    )


def _db_decl_to_schema(d: DeclDB) -> Declaration:
    return Declaration(
        id=d.id,
        scan_id=d.scan_id,
        field_name=d.field_name,
        extracted_value=d.extracted_value,
        evidence=[_db_ev_to_schema(e) for e in d.evidence],
        rule_id=d.rule_id,
        verdict=d.verdict.value,
        reason=d.reason,
        confidence=d.confidence,
        officer_correction=d.officer_correction,
    )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(status="ok", service="sih26034-backend")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.post("/auth/login", response_model=AuthLoginResponse)
def login(body: AuthLoginRequest):
    with Session(engine) as db:
        officer = db.query(OfficerDB).filter_by(email=body.email).first()
        if not officer or not verify_password(body.password, officer.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = create_access_token(officer.id, officer.role.value)
        return AuthLoginResponse(
            token=token,
            officer=AuthOfficer(id=officer.id, role=officer.role.value),
        )


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------

@app.post("/scan", response_model=ScanCreateResponse)
async def create_scan(
    images: List[UploadFile] = File(...),
    officer: OfficerDB = Depends(get_current_officer),
):
    # Read + validate uploads once
    image_bytes: list[tuple[UploadFile, bytes]] = []
    for img in images:
        if img.content_type not in ALLOWED_MIME:
            raise HTTPException(400, f"Invalid file type: {img.content_type}. Allowed: jpeg, png, webp")
        raw = await img.read()
        if len(raw) > MAX_UPLOAD_BYTES:
            raise HTTPException(400, f"File too large (max {MAX_UPLOAD_BYTES // (1024*1024)}MB)")
        image_bytes.append((img, raw))

    scan_id = uuid4()

    with Session(engine) as db:
        scan = ScanDB(id=scan_id, status=ScanStatus.PENDING)
        db.add(scan)
        db.flush()

        image_ids: List[UUID] = []
        for img, raw in image_bytes:
            url = storage.save(str(scan_id), img.filename or "upload.jpg", raw)
            img_row = ImageDB(id=uuid4(), scan_id=scan_id, url=url)
            db.add(img_row)
            db.flush()
            image_ids.append(img_row.id)

        # Run mocked pipeline
        iq, declarations, overall = run_mocked_pipeline(scan_id, image_ids)

        scan.status = ScanStatus.COMPLETED
        scan.overall_status = overall
        scan.image_quality = iq
        scan.warnings = []

        for decl in declarations:
            db.add(decl)

        db.commit()

    return ScanCreateResponse(scan_id=scan_id, status=ScanStatus.COMPLETED)


@app.get("/scan/{scan_id}", response_model=Scan)
def get_scan(scan_id: UUID):
    with Session(engine) as db:
        scan = (
            db.query(ScanDB)
            .options(joinedload(ScanDB.images), joinedload(ScanDB.declarations).joinedload(DeclDB.evidence))
            .filter(ScanDB.id == scan_id)
            .first()
        )
        if not scan:
            raise HTTPException(404, "Scan not found")

        iq = None
        if scan.image_quality:
            iq = ImageQuality(**scan.image_quality)

        return Scan(
            id=scan.id,
            product_id=scan.product_id,
            status=scan.status.value,
            images=[_db_image_to_schema(i) for i in scan.images],
            image_quality=iq,
            compliance_results=[_db_decl_to_schema(d) for d in scan.declarations],
            overall_status=scan.overall_status.value if scan.overall_status else None,
            warnings=scan.warnings or [],
            created_at=scan.created_at,
        )


@app.post("/scan/{scan_id}/images", response_model=ImageUploadResponse)
async def upload_image(scan_id: UUID, images: List[UploadFile] = File(...)):
    with Session(engine) as db:
        scan = db.get(ScanDB, scan_id)
        if not scan:
            raise HTTPException(404, "Scan not found")

        img = images[0] if images else None
        if not img:
            raise HTTPException(400, "No file provided")
        if img.content_type not in ALLOWED_MIME:
            raise HTTPException(400, f"Invalid file type: {img.content_type}")
        raw = await img.read()
        if len(raw) > MAX_UPLOAD_BYTES:
            raise HTTPException(400, "File too large")

        url = storage.save(str(scan_id), img.filename or "upload.jpg", raw)
        img_row = ImageDB(id=uuid4(), scan_id=scan_id, url=url)
        db.add(img_row)
        db.commit()
        return ImageUploadResponse(image_id=img_row.id)


@app.post("/scan/{scan_id}/reanalyze", response_model=ScanCreateResponse)
def reanalyze_scan(scan_id: UUID):
    with Session(engine) as db:
        scan = db.get(ScanDB, scan_id)
        if not scan:
            raise HTTPException(404, "Scan not found")
        scan.status = ScanStatus.PROCESSING
        db.commit()
    return ScanCreateResponse(scan_id=scan_id, status=ScanStatus.PROCESSING)


@app.get("/scan/{scan_id}/evidence", response_model=List[ScanEvidenceGroup])
def get_scan_evidence(scan_id: UUID):
    with Session(engine) as db:
        scan = db.get(ScanDB, scan_id)
        if not scan:
            raise HTTPException(404, "Scan not found")

        decls = (
            db.query(DeclDB)
            .options(joinedload(DeclDB.evidence))
            .filter(DeclDB.scan_id == scan_id)
            .all()
        )
        return [
            ScanEvidenceGroup(
                declaration_id=d.id,
                field_name=d.field_name,
                evidence=[_db_ev_to_schema(e) for e in d.evidence],
            )
            for d in decls
        ]


@app.get("/scan/{scan_id}/compliance", response_model=ScanComplianceResponse)
def get_scan_compliance(scan_id: UUID):
    with Session(engine) as db:
        scan = db.get(ScanDB, scan_id)
        if not scan:
            raise HTTPException(404, "Scan not found")

        decls = (
            db.query(DeclDB)
            .options(joinedload(DeclDB.evidence))
            .filter(DeclDB.scan_id == scan_id)
            .all()
        )
        return ScanComplianceResponse(
            declarations=[_db_decl_to_schema(d) for d in decls],
            overall_status=scan.overall_status.value if scan.overall_status else None,
        )


# ---------------------------------------------------------------------------
# Uploaded file serving
# ---------------------------------------------------------------------------

@app.get("/uploads/{scan_id}/{filename}")
def serve_upload(scan_id: str, filename: str):
    p = storage.get_path(f"/uploads/{scan_id}/{filename}")
    if not p:
        raise HTTPException(404, "File not found")
    return FileResponse(str(p))


# ---------------------------------------------------------------------------
# Inspection (still stubs for now)
# ---------------------------------------------------------------------------

@app.post("/inspection", response_model=Inspection)
def create_inspection(body: Inspection):
    return Inspection(
        id=uuid4(), scan_id=body.scan_id, officer_id=body.officer_id,
        actions=body.actions, notes=body.notes, created_at=datetime.utcnow(),
    )


@app.get("/inspections", response_model=List[Inspection])
def list_inspections(
    officer_id: Optional[UUID] = None,
    scan_id: Optional[UUID] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return []


# ---------------------------------------------------------------------------
# Products (still stubs)
# ---------------------------------------------------------------------------

@app.get("/products", response_model=List[CanonicalProduct])
def list_products(
    name: Optional[str] = None,
    brand: Optional[str] = None,
    barcode: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return []


@app.get("/products/{product_id}", response_model=CanonicalProduct)
def get_product(product_id: UUID):
    raise HTTPException(404, "Product not found")


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(officer: OfficerDB = Depends(get_current_officer)):
    with Session(engine) as db:
        total = db.query(ScanDB).count()
        violations = db.query(ScanDB).filter(ScanDB.overall_status == VerificationState.VIOLATION).count()
        not_ver = db.query(ScanDB).filter(ScanDB.overall_status == VerificationState.NOT_VERIFIED).count()
        rate = (not_ver / total) if total else 0.0
        return DashboardResponse(
            total_scans=total,
            violations=violations,
            not_verified_rate=round(rate, 4),
            recent_inspections=[],
        )


# ---------------------------------------------------------------------------
# Rules (still stubs)
# ---------------------------------------------------------------------------

@app.get("/rules", response_model=RuleSet)
def get_rules(effective_date: Optional[date] = None):
    raise HTTPException(404, "No active rule set")


# ---------------------------------------------------------------------------
# Reports (stubs)
# ---------------------------------------------------------------------------

@app.post("/reports/{report_id}/pdf")
def download_report_pdf(report_id: UUID):
    return StreamingResponse(iter([b"%PDF-1.4 fake"]), media_type="application/pdf")


@app.post("/reports/{report_id}/docx")
def download_report_docx(report_id: UUID):
    return StreamingResponse(
        iter([b"PK fake docx"]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
