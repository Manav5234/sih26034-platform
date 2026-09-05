from datetime import date, datetime, timezone
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
    Product as ProdDB,
    Scan as ScanDB,
    Image as ImageDB,
    Declaration as DeclDB,
    Evidence as EvDB,
    ComplianceResult as CRDB,
    Inspection as InspectionDB,
    InspectionLocation as InspectionLocationDB,
    AuditLog as AuditLogDB,
    VerificationState,
    ScanStatus,
)
from app.database import engine
from app.storage import storage
from app.pipeline import run_pipeline

from app.schemas.api import (
    AuthLoginRequest,
    AuthLoginResponse,
    AuthOfficer,
    DashboardResponse,
    HealthResponse,
    ImageUploadResponse,
    PaginatedInspections,
    PaginatedProducts,
    PaginatedScans,
    ProductListItem,
    ScanComplianceResponse,
    ScanCreateResponse,
    ScanEvidenceGroup,
    ScanListItem,
    InspectionListItem,
)
from app.schemas.declaration import Declaration
from app.schemas.enums import (
    OfficerRole,
)
from app.schemas.evidence import Evidence
from app.schemas.geometry import BBox
from app.schemas.inspection import Inspection, InspectionAction, InspectionRequest, InspectionLocationOut
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

        # Run pipeline (OCR + barcode + extraction + rule engine)
        iq, declarations, overall, barcode_evidence, product_id = run_pipeline(scan_id, image_ids, db)

        scan.status = ScanStatus.COMPLETED
        scan.overall_status = overall
        scan.image_quality = iq
        scan.warnings = []
        if product_id:
            scan.product_id = product_id

        for decl in declarations:
            db.add(decl)

        for ev in barcode_evidence:
            db.add(ev)

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

        # Declaration-linked evidence
        decls = (
            db.query(DeclDB)
            .options(joinedload(DeclDB.evidence))
            .filter(DeclDB.scan_id == scan_id)
            .all()
        )
        groups = [
            ScanEvidenceGroup(
                declaration_id=d.id,
                field_name=d.field_name,
                evidence=[_db_ev_to_schema(e) for e in d.evidence],
            )
            for d in decls
        ]

        # Barcode/QR evidence (not linked to any declaration)
        unlinked_evs = (
            db.query(EvDB)
            .join(ImageDB, EvDB.image_id == ImageDB.id)
            .filter(
                ImageDB.scan_id == scan_id,
                EvDB.declaration_id.is_(None),
            )
            .all()
        )
        if unlinked_evs:
            groups.append(
                ScanEvidenceGroup(
                    declaration_id=None,
                    field_name="barcode_qr",
                    evidence=[_db_ev_to_schema(e) for e in unlinked_evs],
                )
            )

        return groups


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
# Scans list
# ---------------------------------------------------------------------------

@app.get("/scans", response_model=PaginatedScans)
def list_scans(
    status: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    officer_id: Optional[UUID] = None,
    barcode: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _officer: OfficerDB = Depends(get_current_officer),
):
    with Session(engine) as db:
        q = db.query(ScanDB)

        if status:
            try:
                q = q.filter(ScanDB.overall_status == VerificationState(status))
            except ValueError:
                pass

        if date_from:
            q = q.filter(ScanDB.created_at >= datetime.combine(date_from, datetime.min.time()))
        if date_to:
            q = q.filter(ScanDB.created_at <= datetime.combine(date_to, datetime.max.time()))

        # Filter by officer_id: scans that have inspections by this officer
        if officer_id:
            officer_scan_ids = (
                db.query(InspectionDB.scan_id)
                .filter(InspectionDB.officer_id == officer_id)
                .distinct()
                .subquery()
            )
            q = q.filter(ScanDB.id.in_(db.query(officer_scan_ids)))

        # Filter by barcode: scans with barcode evidence matching this code
        if barcode:
            barcode_scan_ids = (
                db.query(ImageDB.scan_id)
                .join(EvDB, EvDB.image_id == ImageDB.id)
                .filter(
                    EvDB.raw_text.ilike(f"%{barcode}%"),
                    EvDB.source_type.in_(["BARCODE", "QR"]),
                )
                .distinct()
                .subquery()
            )
            q = q.filter(ScanDB.id.in_(db.query(barcode_scan_ids)))

        total = q.count()
        rows = q.order_by(ScanDB.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

        items = []
        for s in rows:
            # Check if scan has any inspection
            has_inspection = db.query(InspectionDB).filter(InspectionDB.scan_id == s.id).first() is not None
            decl_count = db.query(DeclDB).filter(DeclDB.scan_id == s.id).count()

            # Get product name from linked product
            product_name = None
            barcode_val = None
            if s.product_id:
                prod = db.get(ProdDB, s.product_id)
                if prod:
                    product_name = prod.identity
                    barcode_val = prod.barcode_code

            # If no product linked, try barcode evidence
            if not barcode_val:
                bc_ev = (
                    db.query(EvDB)
                    .join(ImageDB, EvDB.image_id == ImageDB.id)
                    .filter(
                        ImageDB.scan_id == s.id,
                        EvDB.source_type.in_(["BARCODE", "QR"]),
                    )
                    .first()
                )
                if bc_ev and bc_ev.raw_text:
                    # raw_text format: "EAN-13: 8901542001406"
                    parts = bc_ev.raw_text.split(": ", 1)
                    barcode_val = parts[1] if len(parts) > 1 else bc_ev.raw_text

            items.append(ScanListItem(
                id=s.id,
                status=s.status.value,
                overall_status=s.overall_status.value if s.overall_status else None,
                product_name=product_name,
                barcode=barcode_val,
                has_inspection=has_inspection,
                declarations_count=decl_count,
                created_at=s.created_at,
            ))

        return PaginatedScans(items=items, total=total, page=page, page_size=page_size)


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
# Inspection (officer review workflow)
# ---------------------------------------------------------------------------

@app.post("/inspection", response_model=Inspection)
def create_inspection(
    body: InspectionRequest,
    officer: OfficerDB = Depends(get_current_officer),
):
    """Officer reviews declarations on a scan and takes actions.

    Actions:
      - confirm: officer agrees with the AI verdict (no value change)
      - correct: officer provides a corrected value (stored in officer_correction)
      - mark_unresolved: officer explicitly marks as unresolved (distinct from AI NOT_VERIFIED)

    Every action creates an audit_log entry.  The original AI extracted_value
    and evidence are never overwritten — corrections are additive.
    """
    with Session(engine) as db:
        # Validate scan exists
        scan = db.get(ScanDB, body.scan_id)
        if not scan:
            raise HTTPException(404, "Scan not found")

        actions_data = []
        for action in body.actions:
            decl = db.get(DeclDB, action.declaration_id)
            if not decl:
                raise HTTPException(404, f"Declaration {action.declaration_id} not found")
            if decl.scan_id != body.scan_id:
                raise HTTPException(400, f"Declaration {action.declaration_id} does not belong to scan {body.scan_id}")

            old_verdict = decl.verdict.value if hasattr(decl.verdict, "value") else str(decl.verdict)

            if action.action == "confirm":
                # Record confirmation — no value change
                pass

            elif action.action == "correct":
                if action.new_value is None:
                    raise HTTPException(400, "new_value is required for 'correct' action")
                # Store correction on the declaration — do NOT overwrite extracted_value
                correction = {
                    "officer_id": str(officer.id),
                    "officer_name": officer.name,
                    "corrected_value": action.new_value,
                    "reason": action.reason,
                    "corrected_at": datetime.utcnow().isoformat(),
                    "original_verdict": old_verdict,
                    "original_reason": decl.reason or "",
                }
                decl.officer_correction = correction
                # Update verdict to reflect officer override
                decl.verdict = VerificationState.SATISFIED
                decl.reason = f"officer corrected: {action.reason}"

            elif action.action == "mark_unresolved":
                correction = {
                    "officer_id": str(officer.id),
                    "officer_name": officer.name,
                    "corrected_value": None,
                    "reason": action.reason,
                    "corrected_at": datetime.utcnow().isoformat(),
                    "original_verdict": old_verdict,
                    "original_reason": decl.reason or "",
                }
                decl.officer_correction = correction
                decl.verdict = VerificationState.NOT_VERIFIED
                decl.reason = f"officer marked unresolved: {action.reason}"

            else:
                raise HTTPException(400, f"Unknown action: {action.action}")

            # Record action data for inspection record
            action_record = {
                "declaration_id": str(action.declaration_id),
                "field_name": decl.field_name,
                "action": action.action,
                "old_value": action.old_value,
                "new_value": action.new_value,
                "reason": action.reason,
            }
            actions_data.append(action_record)

            # Create audit log entry
            audit = AuditLogDB(
                id=uuid4(),
                officer_id=officer.id,
                action=f"inspection_{action.action}",
                target_type="declaration",
                target_id=action.declaration_id,
                payload={
                    "scan_id": str(body.scan_id),
                    "field_name": decl.field_name,
                    "old_value": action.old_value,
                    "new_value": action.new_value,
                    "reason": action.reason,
                },
                created_at=datetime.utcnow(),
            )
            db.add(audit)

        # Create inspection record
        inspection = InspectionDB(
            id=uuid4(),
            scan_id=body.scan_id,
            officer_id=officer.id,
            actions=actions_data,
            notes=body.notes,
            created_at=datetime.utcnow(),
        )
        db.add(inspection)
        db.flush()

        # Save geolocation if provided
        location_out = None
        if body.location:
            loc = InspectionLocationDB(
                id=uuid4(),
                inspection_id=inspection.id,
                latitude=body.location.latitude,
                longitude=body.location.longitude,
                accuracy_meters=body.location.accuracy_meters,
                source=body.location.source,
                address_text=body.location.address_text,
                captured_at=datetime.utcnow(),
            )
            db.add(loc)
            location_out = InspectionLocationOut(
                latitude=loc.latitude,
                longitude=loc.longitude,
                accuracy_meters=loc.accuracy_meters,
                source=loc.source,
                address_text=loc.address_text,
                captured_at=loc.captured_at,
            )

        db.commit()
        db.refresh(inspection)

        return Inspection(
            id=inspection.id,
            scan_id=inspection.scan_id,
            officer_id=inspection.officer_id,
            actions=[InspectionAction(**a) for a in inspection.actions],
            notes=inspection.notes,
            location=location_out,
            created_at=inspection.created_at,
        )


@app.get("/inspections", response_model=PaginatedInspections)
def list_inspections(
    status: Optional[str] = None,
    officer_id: Optional[UUID] = None,
    scan_id: Optional[UUID] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _officer: OfficerDB = Depends(get_current_officer),
):
    with Session(engine) as db:
        q = db.query(InspectionDB)
        if officer_id:
            q = q.filter(InspectionDB.officer_id == officer_id)
        if scan_id:
            q = q.filter(InspectionDB.scan_id == scan_id)
        if date_from:
            q = q.filter(InspectionDB.created_at >= datetime.combine(date_from, datetime.min.time()))
        if date_to:
            q = q.filter(InspectionDB.created_at <= datetime.combine(date_to, datetime.max.time()))

        # Status filter: filter by the scan's overall_status
        if status:
            try:
                target_status = VerificationState(status)
                scan_ids_with_status = (
                    db.query(ScanDB.id)
                    .filter(ScanDB.overall_status == target_status)
                    .subquery()
                )
                q = q.filter(InspectionDB.scan_id.in_(db.query(scan_ids_with_status)))
            except ValueError:
                pass

        total = q.count()
        rows = q.order_by(InspectionDB.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

        items = []
        for r in rows:
            officer = db.get(OfficerDB, r.officer_id)
            items.append(InspectionListItem(
                id=r.id,
                scan_id=r.scan_id,
                officer_id=r.officer_id,
                officer_name=officer.name if officer else None,
                actions_count=len(r.actions or []),
                notes=r.notes,
                created_at=r.created_at,
            ))

        return PaginatedInspections(items=items, total=total, page=page, page_size=page_size)


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

@app.get("/products", response_model=PaginatedProducts)
def list_products(
    search: Optional[str] = None,
    brand: Optional[str] = None,
    category: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _officer: OfficerDB = Depends(get_current_officer),
):
    from sqlalchemy import func, case
    with Session(engine) as db:
        q = db.query(ScanDB.product_id).distinct().subquery()
        product_ids = [r[0] for r in db.query(q).all() if r[0] is not None]

        pq = db.query(ProdDB)
        if not product_ids:
            return PaginatedProducts(items=[], total=0, page=page, page_size=page_size)

        pq = pq.filter(ProdDB.id.in_(product_ids))
        if search:
            pq = pq.filter(
                ProdDB.identity.ilike(f"%{search}%")
                | ProdDB.brand.ilike(f"%{search}%")
                | ProdDB.manufacturer.ilike(f"%{search}%")
            )
        if brand:
            pq = pq.filter(ProdDB.brand.ilike(f"%{brand}%"))
        if category:
            pq = pq.filter(ProdDB.category.ilike(f"%{category}%"))

        total = pq.count()
        rows = pq.order_by(ProdDB.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

        items = []
        for p in rows:
            # Latest scan status for this product
            latest_scan = (
                db.query(ScanDB.overall_status)
                .filter(ScanDB.product_id == p.id)
                .order_by(ScanDB.created_at.desc())
                .first()
            )
            scan_count = db.query(ScanDB).filter(ScanDB.product_id == p.id).count()
            items.append(ProductListItem(
                id=p.id,
                identity=p.identity,
                brand=p.brand,
                category=p.category,
                manufacturer=p.manufacturer,
                barcode_code=p.barcode_code,
                mrp_amount=p.mrp_amount,
                latest_scan_status=latest_scan[0].value if latest_scan and latest_scan[0] else None,
                total_scans=scan_count,
                created_at=p.created_at,
            ))

        return PaginatedProducts(items=items, total=total, page=page, page_size=page_size)


@app.get("/products/{product_id}", response_model=CanonicalProduct)
def get_product(product_id: UUID):
    with Session(engine) as db:
        p = db.get(ProdDB, product_id)
        if not p:
            raise HTTPException(404, "Product not found")
        # Get latest scan's declarations and evidence
        latest_scan = (
            db.query(ScanDB)
            .filter(ScanDB.product_id == product_id)
            .order_by(ScanDB.created_at.desc())
            .first()
        )
        decls = []
        evidences = []
        if latest_scan:
            for d in db.query(DeclDB).filter(DeclDB.scan_id == latest_scan.id).all():
                decls.append(_db_decl_to_schema(d))
                for e in d.evidence:
                    evidences.append(_db_ev_to_schema(e))
        return CanonicalProduct(
            id=p.id,
            identity=p.identity,
            brand=p.brand,
            category=p.category,
            manufacturer=p.manufacturer,
            packer=p.packer,
            importer=p.importer,
            country_of_origin=p.country_of_origin,
            quantity=Quantity(value=p.quantity_value, unit=p.quantity_unit) if p.quantity_value else None,
            mrp=MRP(amount=p.mrp_amount, currency=p.mrp_currency) if p.mrp_amount else None,
            dates=Dates(
                manufacture=p.date_manufacture,
                best_before=p.date_best_before,
                use_by=p.date_use_by,
            ),
            consumer_care=p.consumer_care,
            unit_sale_price=UnitSalePrice(amount=p.unit_sale_price_amount, currency=p.unit_sale_price_currency) if p.unit_sale_price_amount else None,
            barcode=Barcode(code=p.barcode_code, format=p.barcode_format) if p.barcode_code else None,
            declarations=decls,
            evidence=evidences,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(officer: OfficerDB = Depends(get_current_officer)):
    from datetime import timedelta
    with Session(engine) as db:
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())

        total = db.query(ScanDB).count()

        # Pending review = scans with 0 inspections
        from sqlalchemy import func, literal_column
        scans_with_inspection = (
            db.query(InspectionDB.scan_id)
            .distinct()
            .subquery()
        )
        pending = (
            db.query(ScanDB)
            .filter(~ScanDB.id.in_(db.query(scans_with_inspection)))
            .count()
        )

        # AI verdicts
        violations_ai = db.query(ScanDB).filter(ScanDB.overall_status == VerificationState.VIOLATION).count()
        not_verified = db.query(ScanDB).filter(ScanDB.overall_status == VerificationState.NOT_VERIFIED).count()
        conflict = db.query(ScanDB).filter(ScanDB.overall_status == VerificationState.CONFLICT).count()

        # Officer-confirmed violations: scans where officer confirmed a VIOLATION declaration
        officer_confirmed = 0
        scans_with_confirm = (
            db.query(DeclDB.scan_id)
            .join(AuditLogDB, AuditLogDB.target_id == DeclDB.id)
            .filter(
                AuditLogDB.action == "inspection_confirm",
                DeclDB.verdict == VerificationState.VIOLATION,
            )
            .distinct()
            .subquery()
        )
        officer_confirmed = db.query(ScanDB).filter(ScanDB.id.in_(db.query(scans_with_confirm))).count()

        # Time-based
        scans_today = db.query(ScanDB).filter(ScanDB.created_at >= today_start).count()
        scans_week = db.query(ScanDB).filter(ScanDB.created_at >= week_start).count()

        return DashboardResponse(
            total_scans=total,
            scans_pending_review=pending,
            violations_ai=violations_ai,
            violations_officer_confirmed=officer_confirmed,
            not_verified=not_verified,
            conflict=conflict,
            scans_today=scans_today,
            scans_this_week=scans_week,
        )


# ---------------------------------------------------------------------------
# Rules (still stubs)
# ---------------------------------------------------------------------------

@app.get("/rules", response_model=RuleSet)
def get_rules(effective_date: Optional[date] = None):
    raise HTTPException(404, "No active rule set")


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@app.get("/reports/{scan_id}")
def get_report_metadata(scan_id: UUID):
    """Check if a report exists and return metadata."""
    from app.db.models import ReportExport as ReportExportDB
    with Session(engine) as db:
        scan = db.get(ScanDB, scan_id)
        if not scan:
            raise HTTPException(404, "Scan not found")
        exports = db.query(ReportExportDB).filter(ReportExportDB.scan_id == scan_id).all()
        return {
            "scan_id": str(scan_id),
            "reports": [
                {
                    "id": str(e.id),
                    "format": e.format,
                    "status": e.status,
                    "file_path": e.file_path,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in exports
            ],
        }


@app.post("/reports/{scan_id}/pdf")
def download_report_pdf(scan_id: UUID, officer: OfficerDB = Depends(get_current_officer)):
    from app.db.models import ReportExport as ReportExportDB
    from app.report import assemble_report
    from app.report_pdf import render_pdf

    with Session(engine) as db:
        try:
            report_data = assemble_report(scan_id, db)
        except ValueError as e:
            raise HTTPException(404, str(e))

        pdf_bytes = render_pdf(report_data)

        # Store export record
        export = ReportExportDB(
            id=uuid4(),
            scan_id=scan_id,
            format="pdf",
            file_path=None,
            status="completed",
        )
        db.add(export)
        db.commit()

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=report-{scan_id}.pdf"},
    )


@app.post("/reports/{scan_id}/docx")
def download_report_docx(scan_id: UUID, officer: OfficerDB = Depends(get_current_officer)):
    from app.db.models import ReportExport as ReportExportDB
    from app.report import assemble_report
    from app.report_docx import render_docx

    with Session(engine) as db:
        try:
            report_data = assemble_report(scan_id, db)
        except ValueError as e:
            raise HTTPException(404, str(e))

        docx_bytes = render_docx(report_data)

        # Store export record
        export = ReportExportDB(
            id=uuid4(),
            scan_id=scan_id,
            format="docx",
            file_path=None,
            status="completed",
        )
        db.add(export)
        db.commit()

    return StreamingResponse(
        iter([docx_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=report-{scan_id}.docx"},
    )
