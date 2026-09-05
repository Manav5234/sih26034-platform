"""Compliance report generation — canonical data assembly + PDF/DOCX renderers.

One source of truth for report content; two renderers consume the same
assembled data structure.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import (
    Scan as ScanDB,
    Declaration as DeclDB,
    Evidence as EvDB,
    Inspection as InspectionDB,
    InspectionLocation as InspectionLocationDB,
    Product as ProdDB,
    Image as ImageDB,
    Officer as OfficerDB,
    VerificationState,
)


@dataclass
class FieldReport:
    field_name: str
    extracted_value: Any
    verdict: str
    reason: str
    confidence: float
    rule_id: Optional[str]
    evidence: List[Dict[str, Any]]
    officer_correction: Optional[Dict[str, Any]] = None


@dataclass
class LocationReport:
    latitude: float
    longitude: float
    accuracy_meters: Optional[float]
    source: str
    address_text: Optional[str]
    captured_at: str


@dataclass
class InspectionReport:
    officer_name: str
    actions: List[Dict[str, Any]]
    notes: Optional[str]
    location: Optional[LocationReport]
    created_at: str


@dataclass
class ReportData:
    scan_id: str
    generated_at: str
    product: Optional[Dict[str, Any]]
    images: List[Dict[str, Any]]
    fields: List[FieldReport]
    inspections: List[InspectionReport]
    overall_status: Optional[str]
    summary: Dict[str, int]


def assemble_report(scan_id: UUID, db: Session) -> ReportData:
    """Build canonical report data from DB for a given scan."""
    scan = db.get(ScanDB, scan_id)
    if not scan:
        raise ValueError(f"Scan {scan_id} not found")

    # Product
    product = None
    if scan.product_id:
        p = db.get(ProdDB, scan.product_id)
        if p:
            product = {
                "name": p.identity,
                "brand": p.brand,
                "category": p.category,
                "manufacturer": p.manufacturer,
                "barcode": p.barcode_code,
                "mrp": f"{p.mrp_currency} {p.mrp_amount}" if p.mrp_amount else None,
                "quantity": f"{p.quantity_value} {p.quantity_unit}" if p.quantity_value else None,
            }

    # Images
    images = []
    for img in scan.images:
        images.append({"id": str(img.id), "url": img.url, "uploaded_at": img.uploaded_at.isoformat()})

    # Declarations (fields)
    fields = []
    verdict_counts = {"SATISFIED": 0, "VIOLATION": 0, "NOT_VERIFIED": 0, "CONFLICT": 0}
    for d in scan.declarations:
        v = d.verdict.value if hasattr(d.verdict, "value") else str(d.verdict)
        verdict_counts[v] = verdict_counts.get(v, 0) + 1

        evidence_list = []
        for e in d.evidence:
            source_label = {
                "OCR": "AI (OCR)",
                "BARCODE": "Barcode Scan",
                "QR": "QR Code",
                "PRODUCT_DATABASE": "Product Database",
                "MANUAL_ENTRY": "Manual Entry",
                "OFFICER_CORRECTION": "Officer Correction",
                "PRIOR_RECORD": "Prior Record",
            }.get(e.source_type.value if hasattr(e.source_type, "value") else str(e.source_type), str(e.source_type))

            evidence_list.append({
                "source_type": e.source_type.value if hasattr(e.source_type, "value") else str(e.source_type),
                "source_label": source_label,
                "raw_text": e.raw_text,
                "confidence": e.confidence,
            })

        fields.append(FieldReport(
            field_name=d.field_name,
            extracted_value=d.extracted_value,
            verdict=v,
            reason=d.reason or "",
            confidence=d.confidence,
            rule_id=d.rule_id,
            evidence=evidence_list,
            officer_correction=d.officer_correction,
        ))

    # Inspections
    inspections = []
    for insp in scan.inspections:
        officer = db.get(OfficerDB, insp.officer_id)
        officer_name = officer.name if officer else "Unknown"

        location = None
        if insp.location:
            loc = insp.location
            location = LocationReport(
                latitude=loc.latitude,
                longitude=loc.longitude,
                accuracy_meters=loc.accuracy_meters,
                source=loc.source,
                address_text=loc.address_text,
                captured_at=loc.captured_at.isoformat() if loc.captured_at else "",
            )

        inspections.append(InspectionReport(
            officer_name=officer_name,
            actions=insp.actions or [],
            notes=insp.notes,
            location=location,
            created_at=insp.created_at.isoformat(),
        ))

    return ReportData(
        scan_id=str(scan_id),
        generated_at=datetime.utcnow().isoformat(),
        product=product,
        images=images,
        fields=fields,
        inspections=inspections,
        overall_status=scan.overall_status.value if scan.overall_status else None,
        summary=verdict_counts,
    )
