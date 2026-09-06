"""Compliance report generation — canonical data assembly + PDF/DOCX renderers.

One source of truth for report content; two renderers consume the same
assembled data structure.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import (
    Officer as OfficerDB,
)
from app.db.models import (
    Product as ProdDB,
)
from app.db.models import (
    Scan as ScanDB,
)

_MONTH_NAMES = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}


def _format_date_value(date_val: Any) -> str:
    """Format a date value dict into human-readable string."""
    if not isinstance(date_val, dict):
        return str(date_val) if date_val else "\u2014"
    val = date_val.get("value", date_val)
    if not isinstance(val, dict):
        return str(val) if val else "\u2014"
    year = val.get("year")
    month = val.get("month")
    day = val.get("day")
    if not year or not month:
        return "\u2014"
    month_name = _MONTH_NAMES.get(month, f"{month:02d}")
    if day:
        return f"{day} {month_name} {year}"
    return f"{month_name} {year}"


def _format_value(field_name: str, value: Any) -> str:
    """Format extracted_value dict into human-readable string."""
    if value is None:
        return "\u2014"
    if isinstance(value, dict):
        if field_name == "mrp":
            amount = value.get("amount", "?")
            currency = value.get("currency", "INR")
            sym = {"INR": "\u20b9", "USD": "$", "EUR": "\u20ac"}.get(currency, currency + " ")
            return f"{sym}{amount}"
        if field_name == "net_quantity":
            return f"{value.get('value', '?')} {value.get('unit', '')}"
        if field_name == "manufacturer":
            return value.get("name", str(value))
        if field_name in ("manufacture_date", "expiry_date"):
            return _format_date_value(value)
        if field_name == "cautions":
            if value.get("present"):
                return f"Present: {value.get('text', '')}"
            return "Not present"
        return str(value)
    if isinstance(value, list):
        if field_name == "nutrition_facts":
            return _format_nutrition_table(value)
        return str(value)
    return str(value)


def _format_nutrition_table(nutrients: list[dict[str, Any]]) -> str:
    """Format nutrition facts list as a readable table string."""
    if not nutrients:
        return "\u2014"
    lines = []
    for n in nutrients:
        val = n.get("value")
        unit = n.get("unit", "")
        name = n.get("nutrient", "").replace("_", " ").title()
        if val is not None:
            lines.append(f"{name}: {val} {unit}")
        else:
            lines.append(f"{name}: \u2014")
    return "; ".join(lines)


@dataclass
class FieldReport:
    field_name: str
    extracted_value: Any
    display_value: str
    verdict: str
    reason: str
    confidence: float
    rule_id: str | None
    evidence: list[dict[str, Any]]
    officer_correction: dict[str, Any] | None = None
    ai_verdict: str | None = None
    ai_reason: str | None = None


@dataclass
class LocationReport:
    latitude: float
    longitude: float
    accuracy_meters: float | None
    source: str
    address_text: str | None
    captured_at: str


@dataclass
class InspectionReport:
    officer_name: str
    actions: list[dict[str, Any]]
    notes: str | None
    location: LocationReport | None
    created_at: str


@dataclass
class ReportData:
    scan_id: str
    generated_at: str
    product: dict[str, Any] | None
    images: list[dict[str, Any]]
    fields: list[FieldReport]
    inspections: list[InspectionReport]
    overall_status: str | None
    summary: dict[str, int]


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

        oc = d.officer_correction
        ai_v = None
        ai_r = None
        if oc:
            ai_v = oc.get("original_verdict")
            ai_r = oc.get("original_reason")

        fields.append(FieldReport(
            field_name=d.field_name,
            extracted_value=d.extracted_value,
            display_value=_format_value(d.field_name, d.extracted_value),
            verdict=v,
            reason=d.reason or "",
            confidence=d.confidence,
            rule_id=d.rule_id,
            evidence=evidence_list,
            officer_correction=oc,
            ai_verdict=ai_v,
            ai_reason=ai_r,
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
