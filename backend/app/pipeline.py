"""Scan pipeline — OCR + barcode + provider lookup + evidence fusion + rule engine.

Steps:
  1. Image quality analysis
  2. OCR (pytesseract) + optional bottom-crop re-pass
  3. Barcode / QR detection (pyzbar)
  4. Provider lookup by decoded barcode (stub)
  5. Per-field evidence fusion (OCR + provider)
  6. Rule engine evaluation on fused declarations
"""
import os
import tempfile

import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import cv2
from sqlalchemy.orm import Session

from app.db.models import (
    Declaration as DeclDB,
    Evidence as EvDB,
    ComplianceResult as CRDB,
    Product as ProdDB,
    EvidenceSourceType,
    VerificationState,
)
from app.image_quality import ImageQualityAnalyzer
from app.ocr import run_ocr
from app.extraction import extract_mrp, extract_net_quantity, extract_manufacturer
from app.barcode import BarcodeDecoder
from app.product_lookup import ProductLookupAdapter
from app.fusion import fuse_field
from app.rule_engine import RuleEngine


def _now():
    return datetime.now(timezone.utc)


# Minimum OCR confidence a crop-pass result must meet to be accepted as a
# replacement for a None (not-found) first-pass result.  Matches the
# validation_conditions threshold from Phase 6 rule engine.
_MIN_CONFIDENCE = 0.6


def _needs_recrop(image_quality: dict, mrp: Any, nq: Any, mf: Any) -> bool:
    """Return True if a second targeted OCR pass is worth attempting.

    Heuristic: re-crop when image quality has any concern, or when the
    first pass found none of the three target fields.  The bottom-third
    crop is a practical heuristic — most product labels place MRP / net-qty
    / manufacturer info in the lower section of the front face.
    """
    if image_quality.get("blur", "low") != "low":
        return True
    if image_quality.get("resolution") == "low":
        return True
    if image_quality.get("perspective") == "severe":
        return True
    if mrp is None and nq is None and mf is None:
        return True
    return False


def _bottom_crop_ocr(image_path: str) -> List[Dict]:
    """Crop the bottom third of the image, upscale 2x, and run OCR.

    Heuristic: product labels place regulatory info (MRP, net qty,
    manufacturer) in the lower portion of the front face.  This is a
    practical observation, not a legal/standard assumption.
    """
    img = cv2.imread(image_path)
    if img is None:
        return []

    h, w = img.shape[:2]
    # Bottom third
    crop_y = int(h * 2 / 3)
    crop = img[crop_y:, :]

    # Upscale 2x with INTER_CUBIC for sharper OCR input
    upscaled = cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    # Write to temp file so run_ocr() can read it
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".png")
    try:
        os.close(tmp_fd)
        cv2.imwrite(tmp_path, upscaled)
        result = run_ocr(tmp_path)
        lines = result.get("lines", [])
        # Tag each line with the preprocessing variant for evidence transparency
        for line in lines:
            line["preprocessing_variant"] = "bottom_crop_2x"
        return lines
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def run_pipeline(
    scan_id: uuid.UUID,
    image_ids: List[uuid.UUID],
    db: Session,
    inspection_date: Optional[date] = None,
    product_category: Optional[str] = None,
) -> Tuple[dict, List[DeclDB], VerificationState, List[EvDB], Optional[uuid.UUID]]:
    """Return (image_quality_dict, declarations, overall_status, barcode_evidence, product_id).

    Pipeline:
      1. Image quality analysis
      2. OCR (pytesseract) + optional bottom-crop re-pass
      3. Barcode / QR detection (pyzbar)
      4. Provider lookup by decoded barcode (stub)
      5. Per-field evidence fusion (OCR + provider)
      6. Rule engine evaluation on fused declarations
    """
    if inspection_date is None:
        inspection_date = date.today()

    image_quality = {
        "blur": "low",
        "glare": "none",
        "perspective": "slight_tilt",
        "resolution": "adequate",
        "recommended_action": "proceed",
    }

    scan_str = str(scan_id)
    upload_dir = f"/data/uploads/{scan_str}"
    first_image_path: Optional[str] = None
    if os.path.isdir(upload_dir):
        files = os.listdir(upload_dir)
        if files:
            first_file = os.path.join(upload_dir, files[0])
            if os.path.isfile(first_file):
                first_image_path = first_file

    # ── Step 1: Image quality ──
    if first_image_path:
        try:
            bgr = cv2.imread(first_image_path)
            if bgr is not None:
                analyzer = ImageQualityAnalyzer()
                sq = analyzer.analyze(bgr)
                image_quality = {
                    "blur": sq["blur"],
                    "glare": sq["glare"],
                    "perspective": sq["perspective"],
                    "resolution": sq["resolution"],
                    "recommended_action": sq["recommended_action"],
                }
        except Exception:
            pass

    # ── Step 2: OCR ──
    ocr_data: Dict[str, List] = {"tokens": [], "lines": []}
    if first_image_path:
        try:
            ocr_data = run_ocr(first_image_path)
        except Exception:
            pass

    ocr_lines = ocr_data.get("lines", [])
    mrk = extract_mrp(ocr_lines)
    nq = extract_net_quantity(ocr_lines)
    mf = extract_manufacturer(ocr_lines)

    # Phase 7c — bottom-crop re-pass
    if first_image_path and _needs_recrop(image_quality, mrk, nq, mf):
        crop_lines = _bottom_crop_ocr(first_image_path)
        if crop_lines:
            ocr_lines = ocr_lines + crop_lines
            crop_mrk = extract_mrp(crop_lines)
            crop_nq = extract_net_quantity(crop_lines)
            crop_mf = extract_manufacturer(crop_lines)

            if mrk is None and crop_mrk is not None:
                if crop_mrk.get("confidence", 0) >= _MIN_CONFIDENCE:
                    mrk = crop_mrk
            elif mrk is not None and crop_mrk is not None:
                if crop_mrk.get("confidence", 0) > mrk.get("confidence", 0):
                    mrk = crop_mrk

            if nq is None and crop_nq is not None:
                if crop_nq.get("confidence", 0) >= _MIN_CONFIDENCE:
                    nq = crop_nq
            elif nq is not None and crop_nq is not None:
                if crop_nq.get("confidence", 0) > nq.get("confidence", 0):
                    nq = crop_nq

            if mf is None and crop_mf is not None:
                if crop_mf.get("confidence", 0) >= _MIN_CONFIDENCE:
                    mf = crop_mf
            elif mf is not None and crop_mf is not None:
                if crop_mf.get("confidence", 0) > mf.get("confidence", 0):
                    mf = crop_mf

    # ── Step 3: Barcode / QR detection ──
    barcodes: List[Dict] = []
    barcode_evidence: List[EvDB] = []
    if first_image_path:
        try:
            decoder = BarcodeDecoder()
            barcodes = decoder.decode(first_image_path)
            img_id = image_ids[0] if image_ids else None
            for bc in barcodes:
                source_type = EvidenceSourceType.QR if bc["format"] == "QRCODE" else EvidenceSourceType.BARCODE
                raw_text = f'{bc["format"]}: {bc["data"]}'
                if bc["format"] == "QRCODE":
                    raw_text += f' (type={bc["payload_type"]})'
                ev = EvDB(
                    id=uuid.uuid4(),
                    source_type=source_type,
                    raw_text=raw_text,
                    confidence=bc["confidence"],
                    image_id=img_id,
                    bbox=bc["bbox"],
                    preprocessing_variant=None,
                    extracted_at=_now(),
                    declaration_id=None,
                )
                barcode_evidence.append(ev)
        except Exception:
            pass

    # ── Step 4: Provider lookup by decoded barcode ──
    provider_data: Optional[Dict] = None
    barcode_value: Optional[str] = None
    for bc in barcodes:
        if bc["format"] != "QRCODE":
            barcode_value = bc["data"]
            provider_data = ProductLookupAdapter.lookup(bc["data"], db=db)
            if provider_data:
                break

    # Persist product record if barcode was found (creates or reuses existing)
    product_id: Optional[uuid.UUID] = None
    if barcode_value:
        existing = db.query(ProdDB).filter(ProdDB.barcode_code == barcode_value).first()
        if existing:
            product_id = existing.id
        else:
            prod = ProdDB(
                id=uuid.uuid4(),
                identity=provider_data.get("name") if provider_data else None,
                brand=provider_data.get("brand") if provider_data else None,
                category=provider_data.get("category") if provider_data else None,
                manufacturer=provider_data.get("manufacturer") if provider_data else None,
                quantity_value=provider_data.get("net_quantity", {}).get("value") if provider_data and provider_data.get("net_quantity") else None,
                quantity_unit=provider_data.get("net_quantity", {}).get("unit") if provider_data and provider_data.get("net_quantity") else None,
                mrp_amount=provider_data.get("mrp", {}).get("amount") if provider_data and provider_data.get("mrp") else None,
                mrp_currency=provider_data.get("mrp", {}).get("currency") if provider_data and provider_data.get("mrp") else None,
                barcode_code=barcode_value,
                barcode_format=barcodes[0]["format"] if barcodes else None,
            )
            db.add(prod)
            db.flush()
            product_id = prod.id

    # ── Step 5: Evidence fusion ──
    # Bug 1c fix: evidence raw_text comes FROM the extraction result, not
    # an independent keyword scan.  Each extraction function returns the
    # matched line text as "raw_text" — this is the sole source of truth.
    ocr_mrp_raw = mrk.get("raw_text", "") if mrk else ""
    ocr_nq_raw = nq.get("raw_text", "") if nq else ""
    ocr_mf_raw = mf.get("raw_text", "") if mf else ""

    # OCR extracted values (None if not found)
    ocr_mrp = mrk if mrk else None
    ocr_nq = nq if nq else None
    ocr_mf = mf["name"] if mf else None
    ocr_mrp_conf = mrk["confidence"] if mrk else 0.0
    ocr_nq_conf = nq["confidence"] if nq else 0.0
    ocr_mf_conf = mf["confidence"] if mf else 0.0

    # Provider extracted values
    prov_mrp = provider_data.get("mrp") if provider_data else None
    prov_nq = provider_data.get("net_quantity") if provider_data else None
    prov_mf = provider_data.get("manufacturer") if provider_data else None

    # Fuse each field
    fused_mrp = fuse_field("mrp", ocr_mrp, ocr_mrp_conf, prov_mrp, 1.0)
    fused_nq = fuse_field("net_quantity", ocr_nq, ocr_nq_conf, prov_nq, 1.0)
    fused_mf = fuse_field("manufacturer", ocr_mf, ocr_mf_conf, prov_mf, 1.0)

    # ── Step 6: Build Declarations from fused results ──
    declarations: List[DeclDB] = []
    img_id = image_ids[0] if image_ids else None

    field_fusions = [
        ("mrp", "LMR-2024-001", fused_mrp, ocr_mrp_raw),
        ("net_quantity", "LMR-2024-002", fused_nq, ocr_nq_raw),
        ("manufacturer", "LMR-2024-003", fused_mf, ocr_mf_raw),
    ]

    for field_name, rule_id, fusion, raw_text in field_fusions:
        decl_id = uuid.uuid4()

        # Build evidence entries for this declaration
        evidence_entries: List[EvDB] = []
        for src in fusion.sources:
            ev = EvDB(
                id=uuid.uuid4(),
                source_type=EvidenceSourceType.OCR if src["source"] == "ocr" else EvidenceSourceType.PRODUCT_DATABASE,
                raw_text=raw_text if src["source"] == "ocr" else f"Provider lookup: {src['source']}",
                confidence=src["confidence"],
                image_id=img_id,
                bbox=None,
                preprocessing_variant="ocr_single_pass" if src["source"] == "ocr" else "provider_lookup",
                extracted_at=_now(),
                declaration_id=decl_id,
            )
            evidence_entries.append(ev)

        # Set verdict based on fusion status
        if fusion.status == "conflict":
            verdict = VerificationState.CONFLICT
            reason = f"conflicting evidence for '{field_name}': OCR={ocr_mrp if field_name=='mrp' else ocr_nq if field_name=='net_quantity' else ocr_mf} vs provider={prov_mrp if field_name=='mrp' else prov_nq if field_name=='net_quantity' else prov_mf}"
            extracted_value = None  # do not guess which is right
        elif fusion.status == "missing":
            verdict = VerificationState.NOT_VERIFIED
            reason = f"{field_name} not found in any evidence source"
            extracted_value = None
        else:  # agreed
            verdict = VerificationState.SATISFIED
            reason = None
            extracted_value = fusion.fused_value

        # Bug 1d safety guardrail: if extracted_value is non-None but the
        # OCR evidence raw_text is empty, this is an internal inconsistency —
        # a value cannot be valid without backing evidence.  Force to None
        # rather than silently shipping a fabricated value.
        if extracted_value is not None and raw_text == "":
            has_provider = any(s["source"] != "ocr" for s in fusion.sources)
            if not has_provider:
                logger.warning(
                    "Evidence guardrail: %s has value %s but empty OCR raw_text "
                    "and no provider evidence — forcing NOT_VERIFIED",
                    field_name, extracted_value,
                )
                extracted_value = None
                verdict = VerificationState.NOT_VERIFIED
                reason = f"{field_name}: extraction produced value without evidence (guardrail)"

        decl = DeclDB(
            id=decl_id,
            scan_id=scan_id,
            field_name=field_name,
            extracted_value=extracted_value,
            rule_id=rule_id,
            verdict=verdict,
            reason=reason,
            confidence=fusion.fused_confidence,
            officer_correction=None,
        )
        decl.evidence = evidence_entries
        declarations.append(decl)

    # ── Step 7: Rule engine ──
    engine = RuleEngine(db)
    overall, results = engine.evaluate(declarations, inspection_date, product_category)

    # Update declarations with rule engine verdicts
    results_by_field = {r["field_name"]: r for r in results}
    for decl in declarations:
        r = results_by_field.get(decl.field_name)
        if r:
            # Rule engine may override conflict/missing with its own verdict
            decl.verdict = r["verdict"]
            decl.reason = r["reason"]
            decl.confidence = r["confidence"] if r["confidence"] is not None else 0.0

            cr = CRDB(
                id=uuid.uuid4(),
                declaration_id=decl.id,
                rule_id=r["rule_id"],
                status=r["verdict"],
                details={"reason": r["reason"]},
            )
            decl.compliance_results = [cr]

    return image_quality, declarations, overall, barcode_evidence, product_id