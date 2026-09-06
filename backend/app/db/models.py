import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums (mirror app.schemas.enums but for SA Column types)
# ---------------------------------------------------------------------------

class VerificationState(str, enum.Enum):
    SATISFIED = "SATISFIED"
    VIOLATION = "VIOLATION"
    NOT_VERIFIED = "NOT_VERIFIED"
    CONFLICT = "CONFLICT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EvidenceSourceType(str, enum.Enum):
    OCR = "OCR"
    BARCODE = "BARCODE"
    QR = "QR"
    PRODUCT_DATABASE = "PRODUCT_DATABASE"
    MANUAL_ENTRY = "MANUAL_ENTRY"
    OFFICER_CORRECTION = "OFFICER_CORRECTION"
    PRIOR_RECORD = "PRIOR_RECORD"


class OfficerRole(str, enum.Enum):
    ADMIN = "ADMIN"
    INSPECTOR = "INSPECTOR"
    VIEWER = "VIEWER"


class ScanStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FlagStatus(str, enum.Enum):
    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


# ---------------------------------------------------------------------------
# Helpers (functions return fresh Column instances per table)
# ---------------------------------------------------------------------------

def _uuid_pk():
    return Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

def _created_at():
    return Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

def _updated_at():
    return Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

class Product(Base):
    __tablename__ = "products"

    id = _uuid_pk()
    identity = Column(String, nullable=True)
    brand = Column(String, nullable=True, index=True)
    category = Column(String, nullable=True, index=True)
    manufacturer = Column(String, nullable=True)
    packer = Column(String, nullable=True)
    importer = Column(String, nullable=True)
    country_of_origin = Column(String, nullable=True)
    quantity_value = Column(Float, nullable=True)
    quantity_unit = Column(String, nullable=True)
    mrp_amount = Column(Float, nullable=True)
    mrp_currency = Column(String, nullable=True)
    date_manufacture = Column(Date, nullable=True)
    date_best_before = Column(Date, nullable=True)
    date_use_by = Column(Date, nullable=True)
    consumer_care = Column(Text, nullable=True)
    unit_sale_price_amount = Column(Float, nullable=True)
    unit_sale_price_currency = Column(String, nullable=True)
    barcode_code = Column(String, nullable=True, index=True)
    barcode_format = Column(String, nullable=True)
    created_at = _created_at()
    updated_at = _updated_at()

    scans = relationship("Scan", back_populates="product")


class ProductCache(Base):
    """Cached external product lookup results keyed by barcode.

    MVP: cache indefinitely (product catalog data changes rarely).
    None values stored as JSON null to distinguish "queried but not found"
    from "never queried".
    """
    __tablename__ = "product_cache"

    barcode = Column(String, primary_key=True)
    result = Column(JSONB, nullable=True)  # null = not found; dict = found
    adapter = Column(String, nullable=True)  # which adapter returned the result
    fetched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


# ---------------------------------------------------------------------------
# Scans
# ---------------------------------------------------------------------------

class Scan(Base):
    __tablename__ = "scans"

    id = _uuid_pk()
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=True, index=True)
    status = Column(SAEnum(ScanStatus, name="scan_status"), nullable=False, default=ScanStatus.PENDING, index=True)
    overall_status = Column(SAEnum(VerificationState, name="verification_state"), nullable=True)
    warnings = Column(JSONB, nullable=False, default=list)
    image_quality = Column(JSONB, nullable=True)
    created_at = _created_at()

    product = relationship("Product", back_populates="scans")
    images = relationship("Image", back_populates="scan", cascade="all, delete-orphan")
    declarations = relationship("Declaration", back_populates="scan", cascade="all, delete-orphan")
    inspections = relationship("Inspection", back_populates="scan")
    flags = relationship("ConsumerFlag", back_populates="scan")


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------

class Image(Base):
    __tablename__ = "images"

    id = _uuid_pk()
    scan_id = Column(UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True)
    url = Column(Text, nullable=False)
    label = Column(String, nullable=True)  # "front" | "back" | None (pre-phase-15 images)
    uploaded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    scan = relationship("Scan", back_populates="images")
    evidence_items = relationship("Evidence", back_populates="image")


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

class Evidence(Base):
    __tablename__ = "evidence"

    id = _uuid_pk()
    source_type = Column(SAEnum(EvidenceSourceType, name="evidence_source_type"), nullable=False, index=True)
    raw_text = Column(Text, nullable=True)
    confidence = Column(Float, nullable=False)
    image_id = Column(UUID(as_uuid=True), ForeignKey("images.id", ondelete="SET NULL"), nullable=True, index=True)
    bbox = Column(JSONB, nullable=True)
    preprocessing_variant = Column(String, nullable=True)
    extracted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    image = relationship("Image", back_populates="evidence_items")
    declaration_id = Column(UUID(as_uuid=True), ForeignKey("declarations.id", ondelete="CASCADE"), nullable=True, index=True)
    declaration = relationship("Declaration", back_populates="evidence")


# ---------------------------------------------------------------------------
# Declarations
# ---------------------------------------------------------------------------

class Declaration(Base):
    __tablename__ = "declarations"

    id = _uuid_pk()
    scan_id = Column(UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True)
    field_name = Column(String, nullable=False, index=True)
    extracted_value = Column(JSONB, nullable=False)
    rule_id = Column(String, nullable=True, index=True)
    verdict = Column(SAEnum(VerificationState, name="verification_state"), nullable=False, index=True)
    reason = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False)
    officer_correction = Column(JSONB, nullable=True)
    created_at = _created_at()

    scan = relationship("Scan", back_populates="declarations")
    evidence = relationship("Evidence", back_populates="declaration", cascade="all, delete-orphan")
    compliance_results = relationship("ComplianceResult", back_populates="declaration", cascade="all, delete-orphan")
    nutrition_facts = relationship("NutritionFact", back_populates="declaration", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Compliance Results (links declarations → rules)
# ---------------------------------------------------------------------------

class ComplianceResult(Base):
    __tablename__ = "compliance_results"

    id = _uuid_pk()
    declaration_id = Column(UUID(as_uuid=True), ForeignKey("declarations.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_id = Column(String, ForeignKey("rules.rule_id"), nullable=True, index=True)
    status = Column(SAEnum(VerificationState, name="verification_state"), nullable=False)
    details = Column(JSONB, nullable=True)
    created_at = _created_at()

    declaration = relationship("Declaration", back_populates="compliance_results")
    rule = relationship("Rule", back_populates="compliance_results")


# ---------------------------------------------------------------------------
# Nutrition Facts (structured sub-schema for nutrition panel extraction)
# ---------------------------------------------------------------------------

class NutritionFact(Base):
    __tablename__ = "nutrition_facts"

    id = _uuid_pk()
    declaration_id = Column(UUID(as_uuid=True), ForeignKey("declarations.id", ondelete="CASCADE"), nullable=False, index=True)
    nutrient = Column(String, nullable=False)          # "energy", "carbohydrate", "sugars", etc.
    value = Column(Float, nullable=True)                # NULL if not legible (individual NOT_VERIFIED)
    unit = Column(String, nullable=False)               # "kcal", "g", "mg"
    confidence = Column(Float, nullable=False)          # per-nutrient confidence
    raw_text = Column(Text, nullable=True)              # original OCR text for this line

    declaration = relationship("Declaration", back_populates="nutrition_facts")


# ---------------------------------------------------------------------------
# Officers
# ---------------------------------------------------------------------------

class Officer(Base):
    __tablename__ = "officers"

    id = _uuid_pk()
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(SAEnum(OfficerRole, name="officer_role"), nullable=False, default=OfficerRole.VIEWER)
    created_at = _created_at()

    inspections = relationship("Inspection", back_populates="officer")
    audit_entries = relationship("AuditLog", back_populates="officer")


# ---------------------------------------------------------------------------
# Inspections
# ---------------------------------------------------------------------------

class Inspection(Base):
    __tablename__ = "inspections"

    id = _uuid_pk()
    scan_id = Column(UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True)
    officer_id = Column(UUID(as_uuid=True), ForeignKey("officers.id"), nullable=False, index=True)
    actions = Column(JSONB, nullable=False, default=list)
    notes = Column(Text, nullable=True)
    created_at = _created_at()

    scan = relationship("Scan", back_populates="inspections")
    officer = relationship("Officer", back_populates="inspections")
    location = relationship("InspectionLocation", back_populates="inspection", uselist=False)


class InspectionLocation(Base):
    __tablename__ = "inspection_locations"

    id = _uuid_pk()
    inspection_id = Column(UUID(as_uuid=True), ForeignKey("inspections.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    accuracy_meters = Column(Float, nullable=True)  # null if manual
    source = Column(String, nullable=False, default="GPS")  # "GPS" | "MANUAL"
    address_text = Column(Text, nullable=True)
    captured_at = Column(DateTime(timezone=True), nullable=False)

    inspection = relationship("Inspection", back_populates="location")


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------

class AuditLog(Base):
    __tablename__ = "audit_log"

    id = _uuid_pk()
    officer_id = Column(UUID(as_uuid=True), ForeignKey("officers.id"), nullable=True, index=True)
    action = Column(String, nullable=False)
    target_type = Column(String, nullable=False)
    target_id = Column(UUID(as_uuid=True), nullable=True)
    payload = Column(JSONB, nullable=True)
    created_at = _created_at()

    officer = relationship("Officer", back_populates="audit_entries")


# ---------------------------------------------------------------------------
# Rule Sets
# ---------------------------------------------------------------------------

class RuleSet(Base):
    __tablename__ = "rule_sets"

    id = _uuid_pk()
    source = Column(String, nullable=False)
    rule_version = Column(String, nullable=False)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    jurisdiction = Column(String, nullable=False)
    created_at = _created_at()

    rules = relationship("Rule", back_populates="rule_set", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

class Rule(Base):
    __tablename__ = "rules"

    rule_id = Column(String, primary_key=True)
    rule_set_id = Column(UUID(as_uuid=True), ForeignKey("rule_sets.id", ondelete="CASCADE"), nullable=False, index=True)
    source_document = Column(String, nullable=False)
    clause = Column(String, nullable=False)
    applicability = Column(Text, nullable=False)
    required_declaration = Column(String, nullable=False)
    validation_conditions = Column(JSONB, nullable=False)
    measurement_requirements = Column(JSONB, nullable=True)
    exceptions = Column(JSONB, nullable=False, default=list)
    effective_date = Column(Date, nullable=False)
    evidence_requirements = Column(JSONB, nullable=False, default=list)

    rule_set = relationship("RuleSet", back_populates="rules")
    compliance_results = relationship("ComplianceResult", back_populates="rule")


# ---------------------------------------------------------------------------
# Report Exports
# ---------------------------------------------------------------------------

class ReportExport(Base):
    __tablename__ = "report_exports"

    id = _uuid_pk()
    scan_id = Column(UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True)
    format = Column(String, nullable=False)  # "pdf" | "docx"
    file_path = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="pending")
    created_at = _created_at()


# ---------------------------------------------------------------------------
# Consumer Flags
# ---------------------------------------------------------------------------

class ConsumerFlag(Base):
    __tablename__ = "consumer_flags"

    id = _uuid_pk()
    scan_id = Column(UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True)
    reported_fields = Column(JSONB, nullable=False, default=list)
    reporter_note = Column(Text, nullable=True)
    reporter_contact = Column(Text, nullable=True)
    status = Column(SAEnum(FlagStatus, name="flag_status"), nullable=False, default=FlagStatus.NEW, index=True)
    created_at = _created_at()
    reviewed_by_officer_id = Column(UUID(as_uuid=True), ForeignKey("officers.id"), nullable=True, index=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    officer_notes = Column(Text, nullable=True)

    scan = relationship("Scan", back_populates="flags")
    reviewed_by_officer = relationship("Officer")
