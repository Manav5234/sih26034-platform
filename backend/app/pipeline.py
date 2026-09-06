"""Scan pipeline — OCR + barcode + provider lookup + evidence fusion + rule engine.

Multi-image pipeline (Phase 15):
  1. Resolve image paths with labels (front/back)
  2. Image quality analysis — per image, independent
  3. OCR — per image, results tagged with source label
  4. Barcode / QR detection — per image, deduplicate across images
  5. Provider lookup by decoded barcode
  6. Per-field evidence fusion (OCR + provider)
  7. Rule engine evaluation on fused declarations
"""
import logging
import math
import os
import tempfile
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import cv2
from sqlalchemy.orm import Session

from app.barcode import BarcodeDecoder
from app.db.models import (
    ComplianceResult as CRDB,
)
from app.db.models import (
    Declaration as DeclDB,
)
from app.db.models import (
    Evidence as EvDB,
)
from app.db.models import (
    EvidenceSourceType,
    VerificationState,
)
from app.db.models import (
    Image as ImageDB,
)
from app.db.models import (
    NutritionFact as NFDB,
)
from app.db.models import (
    Product as ProdDB,
)
from app.extraction import (
    extract_cautions,
    extract_expiry_date,
    extract_manufacture_date,
    extract_manufacturer,
    extract_mrp,
    extract_net_quantity,
    extract_nutrition_facts,
)
from app.fusion import fuse_field
from app.image_quality import ImageQualityAnalyzer
from app.ocr import run_ocr
from app.product_lookup import ProductLookupAdapter
from app.rule_engine import RuleEngine

logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc)


_MIN_CONFIDENCE = 0.6

# Panel-aware search order (Step 4e)
# Controls which image is searched FIRST. If the field is found on the
# "wrong" panel, it's still accepted — search order is advisory, not restrictive.
PANEL_SEARCH_ORDER: dict[str, list[str]] = {
    "mrp":             ["front", "back"],
    "net_quantity":    ["front", "back"],
    "brand":           ["front", "back"],
    "manufacturer":    ["back", "front"],
    "manufacture_date": ["back", "front"],
    "expiry_date":     ["back", "front"],
    "nutrition_facts": ["back", "front"],
    "cautions":        ["back", "front"],
}


def _compare_dates_chronologically(
    mfd_value: dict | None, exp_value: dict | None
) -> str | None:
    """Compare manufacture vs expiry date at shared granularity.

    Returns "ok", "conflict", or "incomparable" if dates can't be compared.
    """
    if not mfd_value or not exp_value:
        return "incomparable"

    mfd = mfd_value.get("value", {})
    exp = exp_value.get("value", {})

    # Compare at the finest granularity both dates share
    mfd_year = mfd.get("year")
    exp_year = exp.get("year")
    if mfd_year is None or exp_year is None:
        return "incomparable"

    if mfd_year != exp_year:
        return "conflict" if exp_year < mfd_year else "ok"

    mfd_month = mfd.get("month")
    exp_month = exp.get("month")
    if mfd_month is None or exp_month is None:
        return "incomparable"

    if exp_month < mfd_month:
        return "conflict"

    mfd_day = mfd.get("day")
    exp_day = exp.get("day")
    if mfd_day is None or exp_day is None:
        # Both have same month/year, can't compare day-level — assume ok
        return "ok"

    if exp_day < mfd_day:
        return "conflict"

    if exp_day == mfd_day and mfd_month == exp_month and mfd_year == exp_year:
        return "conflict"  # same day = effectively expired at manufacture

    return "ok"


def _needs_recrop(image_quality: dict, mrp: Any, nq: Any, mf: Any) -> bool:
    """Return True if a second targeted OCR pass is worth attempting."""
    if image_quality.get("blur", "low") != "low":
        return True
    if image_quality.get("resolution") == "low":
        return True
    if image_quality.get("perspective") == "severe":
        return True
    if mrp is None and nq is None and mf is None:
        return True
    return False


def _generate_ocr_variants(
    image_path: str, image_quality: dict
) -> list[tuple[str, str]]:
    """Generate selected OCR preprocessing variants based on quality metrics.

    Returns list of (variant_image_path, variant_name) tuples.
    Does NOT run OCR — only prepares the image variants to run OCR on.

    Variant selection is driven by image-quality metrics — we only run
    variants that address the observed quality issues.  This avoids
    running every possible variant and overwhelming the pipeline.

    Generated variants (in priority order):
    1. "original" — always included
    2. "upscaled_2x" — if resolution is low
    3. "contrast_enhanced" — if glare is high
    4. "deskewed" — if blur is high and a four-point contour is found
    """
    import cv2
    import numpy as np

    variants: list[tuple[str, str]] = []

    # Always include original image
    variants.append((image_path, "original"))

    # Read image once to avoid repeated I/O
    img = cv2.imread(image_path)
    if img is None:
        return variants

    h, w = img.shape[:2]
    blur = image_quality.get("blur", "low")
    glare = image_quality.get("glare", "none")
    resolution = image_quality.get("resolution", "adequate")

    # Upscale 2x for low-resolution images
    if resolution == "low":
        upscaled = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".png")
        try:
            os.close(tmp_fd)
            cv2.imwrite(tmp_path, upscaled)
            variants.append((tmp_path, "upscaled_2x"))
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    # Contrast-enhance for high-glare images using CLAHE
    if glare == "high":
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l2 = clahe.apply(l)
        enhanced = cv2.merge([l2, a, b])
        enhanced_bgr = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".png")
        try:
            os.close(tmp_fd)
            cv2.imwrite(tmp_path, enhanced_bgr)
            variants.append((tmp_path, "contrast_enhanced"))
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    # Deskew for high-blur images using contour-based perspective correction
    if blur == "high":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        contours, _ = cv2.findContours(
            cv2.Canny(gray, 50, 150, apertureSize=3),
            cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
        )
        if contours:
            largest = max(contours, key=cv2.contourArea)
            epsilon = 0.02 * cv2.arcLength(largest, True)
            approx = cv2.approxPolyDP(largest, epsilon, True)
            if len(approx) == 4:
                # Four-point contour found — apply perspective rectify
                (tl, tr, br, bl) = approx.reshape(4, 2)
                width_a = math.hypot(br[0] - bl[0], br[1] - bl[1])
                width_b = math.hypot(tr[0] - tl[0], tr[1] - tl[1])
                max_width = max(int(width_a), int(width_b))
                height_a = math.hypot(tr[0] - br[0], tr[1] - br[1])
                height_b = math.hypot(tl[0] - bl[0], tl[1] - bl[1])
                max_height = max(int(height_a), int(height_b))
                dst = np.array([
                    [0, 0], [max_width - 1, 0],
                    [max_width - 1, max_height - 1], [0, max_height - 1]],
                    dtype="float32")
                src = approx.reshape(4, 2).astype("float32")
                M = cv2.getPerspectiveTransform(src, dst)
                warped = cv2.warpPerspective(img, M, (max_width, max_height))
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".png")
                try:
                    os.close(tmp_fd)
                    cv2.imwrite(tmp_path, warped)
                    variants.append((tmp_path, "deskewed"))
                finally:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

    return variants


def _bottom_crop_ocr(image_path: str) -> list[dict]:
    """Crop the bottom third of the image, upscale 2x, and run OCR."""
    img = cv2.imread(image_path)
    if img is None:
        return []

    h, w = img.shape[:2]
    crop_y = int(h * 2 / 3)
    crop = img[crop_y:, :]
    upscaled = cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".png")
    try:
        os.close(tmp_fd)
        cv2.imwrite(tmp_path, upscaled)
        result = run_ocr(tmp_path)
        lines = result.get("lines", [])
        for line in lines:
            line["preprocessing_variant"] = "bottom_crop_2x"
        return lines
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _resolve_images(scan_id: uuid.UUID, image_ids: list[uuid.UUID], db: Session) -> list[dict]:
    """Resolve image IDs to paths with labels.

    Returns list of {"id": UUID, "path": str, "label": "front"|"back"} dicts.
    """
    images = []
    for img_id in image_ids:
        img_db = db.get(ImageDB, img_id)
        if not img_db:
            continue
        # Resolve URL path to filesystem path
        url = img_db.url  # e.g. /uploads/{scan_id}/{uuid}.jpg
        if not url.startswith("/uploads/"):
            continue
        rel = url.removeprefix("/uploads/")
        fs_path = f"/data/uploads/{rel}"
        if not os.path.isfile(fs_path):
            continue
        images.append({
            "id": img_db.id,
            "path": fs_path,
            "label": img_db.label or "front",
        })
    return images


def _needs_recrop(image_quality: dict, mrp: Any, nq: Any, mf: Any) -> bool:
    """Return True if a second targeted OCR pass is worth attempting."""
    if image_quality.get("blur", "low") != "low":
        return True
    if image_quality.get("resolution") == "low":
        return True
    if image_quality.get("perspective") == "severe":
        return True
    if mrp is None and nq is None and mf is None:
        return True
    return False


def _generate_ocr_variants_with_results(
    image_path: str, image_quality: dict,
    provider_result_fn
) -> list[dict]:
    """Run OCR on selected preprocessing variants and merge results.

    Args:
        image_path: path to the original image
        image_quality: quality metrics dict from image_quality.py
        provider_result_fn: callable taking image_path → OCR result dict

    Returns merged OCR lines from all selected variants, each tagged with
    their preprocessing_variant.  Variants that fail to process are silently
    skipped.
    """

    # Generate selected variants based on quality metrics
    variants = _generate_ocr_variants(image_path, image_quality)

    merged_lines: list[dict] = []
    seen_texts: set = set()  # simple dedup by text

    for variant_path, variant_name in variants:
        try:
            result = provider_result_fn(variant_path)
        except Exception as e:
            logger.warning("OCR variant %s failed for %s: %s", variant_name, image_path, e)
            continue

        lines = result.get("lines", [])
        for line in lines:
            # Tag the line with its preprocessing variant
            line_copy = dict(line)
            line_copy["preprocessing_variant"] = variant_name

            # Simple dedup: skip if we've already seen identical text
            line_text = line_copy.get("text", "").strip().lower()
            if line_text and line_text not in seen_texts:
                seen_texts.add(line_text)
                merged_lines.append(line_copy)
            elif line_text:
                # Still add but mark as duplicate source
                line_copy["_duplicate_of"] = line_text
                merged_lines.append(line_copy)

    return merged_lines


def _apply_ocr_normalization(lines: list[dict]) -> list[dict]:
    """Apply OCR error normalization to produce normalized variants.

    Generates context-dependent character substitutions (₹↔€, O↔0, I↔1,
    S↔5, B↔8) with confidence penalties.  Original text is preserved
    alongside normalized variants for evidence tracking.
    """
    from app.ocr_normalization import normalize_ocr_text

    normalized_lines: list[dict] = []
    for line in lines:
        text = line.get("text", "")
        orig_conf = line.get("confidence", 1.0)
        base = {"text": text, "confidence": orig_conf,
                "source_provider": line.get("source_provider", "tesseract"),
                "preprocessing_variant": line.get("preprocessing_variant", "single_pass")}

        # Always keep the original text as the first entry
        normalized_lines.append(dict(base))

        # Generate normalized variants with confidence penalties
        norm_result = normalize_ocr_text(text, orig_conf)
        for nv_text, nv_conf in norm_result:
            if nv_text != text:  # only add if actually different
                var_line = dict(base)
                var_line["text"] = nv_text
                var_line["confidence"] = nv_conf
                var_line["_normalized_from"] = "ocr_normalization"
                normalized_lines.append(var_line)

    return normalized_lines


def _ocr_with_recrop(image_path: str, image_quality: dict) -> list[dict]:
    """Run OCR with optional multi-pass preprocessing variants.

    Runs OCR with selected preprocessing variants (based on quality metrics)
    and merges results.  Each result carries the preprocessing_variant tag.

    If recrop is still needed after variant analysis, the bottom-crop 2x
    pass is also attempted.
    """
    # Use the provider-aware OCR extraction
    from app.ocr_provider import run_ocr_with_provider

    # First, try standard OCR
    mrk = run_ocr_with_provider(image_path)
    ocr_lines = mrk.get("lines", [])

    # Apply OCR error normalization to produce variants with confidence penalties
    ocr_lines = _apply_ocr_normalization(ocr_lines)

    # Integrate OCR ensemble — produce unified evidence set from all candidates
    # across providers and preprocessing variants.  This preserves ALL candidates
    # (never silently drops lower-confidence ones) and flags conflicts for
    # the fusion layer to resolve.
    from app.ocr_ensemble import ensemble_ocr_evidence, generate_field_candidates

    # Build candidates dict for the ensemble: field_name → list of OCREvidence
    # We convert the normalized lines (which are dicts) to OCREvidence candidates
    # using generate_field_candidates for each relevant field.
    all_candidates: dict[str, list[Any]] = {
        "mrp": [],
        "net_quantity": [],
        "manufacturer": [],
        "manufacture_date": [],
        "expiry_date": [],
        "cautions": [],
        "nutrition_facts": [],
    }

    # Convert each line to OCREvidence and generate field-specific candidates
    for line in ocr_lines:
        source_provider = line.get("source_provider", "tesseract")
        # Use duck-typing helpers from the ensemble module
        text = line.get("text", "").strip()
        bbox = line.get("bbox", [0, 0, 0, 0])
        confidence = line.get("confidence", 1.0)
        preprocessing = line.get("preprocessing_variant", "single_pass")

        # Generate candidates for each field using the ensemble helper
        for field_name in all_candidates.keys():
            field_candidates = generate_field_candidates(
                [line], field_name, source_provider,
            )
            all_candidates[field_name].extend(field_candidates)

    # Run the ensemble to produce unified evidence
    ensemble_results = ensemble_ocr_evidence(all_candidates)

    # Extract current fields to decide if additional variants are needed
    mrp = extract_mrp(ocr_lines) if ocr_lines else None
    nq = extract_net_quantity(ocr_lines) if ocr_lines else None
    mf = extract_manufacturer(ocr_lines) if ocr_lines else None

    # Generate and run selected preprocessing variants
    variant_lines = _generate_ocr_variants_with_results(
        image_path, image_quality,
        lambda p: run_ocr_with_provider(p),
    )

    if variant_lines:
        # Merge variant lines with original lines, avoiding duplicates
        existing_texts = {l.get("text", "").strip().lower() for l in ocr_lines}
        for vline in variant_lines:
            vt = vline.get("text", "").strip().lower()
            if vt and vt not in existing_texts:
                ocr_lines.append(vline)
            elif vt:
                # Already have this text from original — still update variant tag
                for ol in ocr_lines:
                    if ol.get("text", "").strip().lower() == vt:
                        ol["preprocessing_variant"] = vline.get("preprocessing_variant", "original")
                        break

    # Still attempt bottom-crop recrop if needed
    if _needs_recrop(image_quality, mrp, nq, mf):
        try:
            crop_lines = _bottom_crop_ocr(image_path)
            if crop_lines:
                for cl in crop_lines:
                    cl["preprocessing_variant"] = cl.get("preprocessing_variant", "bottom_crop_2x")
                    # Only add if not already present
                    ct = cl.get("text", "").strip().lower()
                    if ct and not any(ol.get("text", "").strip().lower() == ct for ol in ocr_lines):
                        ocr_lines.append(cl)
        except Exception as e:
            logger.warning("Bottom crop OCR failed for %s: %s", image_path, e)

    return ocr_lines


def _deduplicate_barcodes(all_barcodes: list[dict]) -> tuple[list[dict], list[str]]:
    """Deduplicate barcodes across images.

    Returns (deduplicated_barcodes, warnings).
    - Identical decodes from both images → kept once, source_image = "both"
    - Different decodes from different images → kept, flagged as mismatch
    """
    if not all_barcodes:
        return [], []

    # Group by decoded data value
    by_value: dict[str, list[dict]] = {}
    for bc in all_barcodes:
        val = bc["data"]
        if val not in by_value:
            by_value[val] = []
        by_value[val].append(bc)

    deduped = []
    warnings = []
    for value, bcs in by_value.items():
        sources = set(bc["source_image"] for bc in bcs)
        if len(bcs) > 1 and len(sources) > 1:
            # Same barcode found on both images — keep once, mark as "both"
            merged = dict(bcs[0])
            merged["source_image"] = "both"
            deduped.append(merged)
        elif len(bcs) > 1:
            # Same barcode found multiple times on same image — keep first
            deduped.append(bcs[0])
        else:
            deduped.append(bcs[0])

    # Check for mismatched barcodes across images
    non_qr = [bc for bc in deduped if bc["format"] != "QRCODE"]
    if len(non_qr) > 1:
        values = set(bc["data"] for bc in non_qr)
        if len(values) > 1:
            warnings.append(
                f"Barcode mismatch: different barcodes decoded from front vs back images: {values}"
            )

    return deduped, warnings


def run_pipeline(
    scan_id: uuid.UUID,
    image_ids: list[uuid.UUID],
    db: Session,
    inspection_date: date | None = None,
    product_category: str | None = None,
) -> tuple[dict, list[DeclDB], VerificationState, list[EvDB], uuid.UUID | None]:
    """Return (image_quality_dict, declarations, overall_status, barcode_evidence, product_id).

    Multi-image pipeline:
      1. Resolve image paths with labels
      2. Image quality — per image
      3. OCR — per image, tagged with source label
      4. Barcode — per image, deduplicated
      5. Provider lookup
      6. Fusion + declarations (existing extraction functions, merged OCR)
      7. Rule engine
    """
    if inspection_date is None:
        inspection_date = date.today()

    # ── Step 1: Resolve images ──
    images = _resolve_images(scan_id, image_ids, db)

    # ── Step 2: Image quality — per image ──
    image_quality = {}
    for img in images:
        try:
            bgr = cv2.imread(img["path"])
            if bgr is not None:
                analyzer = ImageQualityAnalyzer()
                sq = analyzer.analyze(bgr)
                image_quality[img["label"]] = {
                    "blur": sq["blur"],
                    "glare": sq["glare"],
                    "perspective": sq["perspective"],
                    "resolution": sq["resolution"],
                    "recommended_action": sq["recommended_action"],
                }
        except Exception:
            image_quality[img["label"]] = {
                "blur": "low", "glare": "none", "perspective": "slight_tilt",
                "resolution": "adequate", "recommended_action": "proceed",
            }

    # ── Step 3: OCR — per image ──
    # Store per-image OCR results for panel-aware extraction in Round 2
    ocr_by_label: dict[str, list[dict]] = {}
    for img in images:
        ocr_lines = _ocr_with_recrop(img["path"], image_quality.get(img["label"], {}))
        ocr_by_label[img["label"]] = ocr_lines

    # Merge all OCR lines for existing extraction functions (they don't know about panels yet)
    all_ocr_lines = []
    for label in ["front", "back"]:
        if label in ocr_by_label:
            all_ocr_lines.extend(ocr_by_label[label])

    # ── Step 3a: Panel-aware extraction ──
    # Extract fields using panel-aware search order.
    # Search order is advisory: if found on the "wrong" panel, still accepted.
    def _extract_with_panel_order(field_name: str, extract_fn, all_lines: list[dict], ocr_by: dict[str, list[dict]]):
        """Run extraction with panel-aware search order."""
        order = PANEL_SEARCH_ORDER.get(field_name, ["front", "back"])
        for label in order:
            panel_lines = ocr_by.get(label, [])
            if panel_lines:
                result = extract_fn(panel_lines)
                if result is not None:
                    return result, label
        # Fallback to merged lines
        result = extract_fn(all_lines)
        return result, "front"

    mrk, mrp_source_image = _extract_with_panel_order("mrp", extract_mrp, all_ocr_lines, ocr_by_label)
    nq, nq_source_image = _extract_with_panel_order("net_quantity", extract_net_quantity, all_ocr_lines, ocr_by_label)
    mf, mf_source_image = _extract_with_panel_order("manufacturer", extract_manufacturer, all_ocr_lines, ocr_by_label)
    mfd, mfd_source_image = _extract_with_panel_order("manufacture_date", extract_manufacture_date, all_ocr_lines, ocr_by_label)
    exp, exp_source_image = _extract_with_panel_order("expiry_date", extract_expiry_date, all_ocr_lines, ocr_by_label)
    caution_result, caution_source_image = _extract_with_panel_order("cautions", lambda lines: extract_cautions(lines), all_ocr_lines, ocr_by_label)
    nutrition_list = extract_nutrition_facts(all_ocr_lines)

    # ── Step 4: Barcode / QR detection — per image ──
    all_barcodes: list[dict] = []
    for img in images:
        try:
            decoder = BarcodeDecoder()
            barcodes = decoder.decode(img["path"])
            for bc in barcodes:
                bc["source_image"] = img["label"]
            all_barcodes.extend(barcodes)
        except Exception as e:
            logger.warning("Barcode decode failed for %s: %s", img["path"], e)

    barcodes, barcode_warnings = _deduplicate_barcodes(all_barcodes)

    barcode_evidence: list[EvDB] = []
    for bc in barcodes:
        source_type = EvidenceSourceType.QR if bc["format"] == "QRCODE" else EvidenceSourceType.BARCODE
        raw_text = f'{bc["format"]}: {bc["data"]}'
        if bc["format"] == "QRCODE":
            raw_text += f' (type={bc.get("payload_type", "unknown")})'

        # Find the image_id for this barcode's source
        src_label = bc.get("source_image", "front")
        src_img_id = None
        for img in images:
            if img["label"] == src_label or src_label == "both":
                src_img_id = img["id"]
                break
        if src_img_id is None and images:
            src_img_id = images[0]["id"]

        ev = EvDB(
            id=uuid.uuid4(),
            source_type=source_type,
            raw_text=raw_text,
            confidence=bc["confidence"],
            image_id=src_img_id,
            bbox=bc.get("bbox"),
            preprocessing_variant=None,
            extracted_at=_now(),
            declaration_id=None,
        )
        barcode_evidence.append(ev)

    # ── Step 5: Provider lookup by decoded barcode ──
    provider_data: dict | None = None
    barcode_value: str | None = None
    for bc in barcodes:
        if bc["format"] != "QRCODE":
            barcode_value = bc["data"]
            provider_data = ProductLookupAdapter.lookup(bc["data"], db=db)
            if provider_data:
                break

    # Persist product record
    product_id: uuid.UUID | None = None
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

    # ── Step 6: Evidence fusion + declarations ──
    ocr_mrp_raw = mrk.get("raw_text", "") if mrk else ""
    ocr_nq_raw = nq.get("raw_text", "") if nq else ""
    ocr_mf_raw = mf.get("raw_text", "") if mf else ""

    ocr_mrp = mrk if mrk else None
    ocr_nq = nq if nq else None
    ocr_mf = mf["name"] if mf else None
    ocr_mrp_conf = mrk["confidence"] if mrk else 0.0
    ocr_nq_conf = nq["confidence"] if nq else 0.0
    ocr_mf_conf = mf["confidence"] if mf else 0.0

    prov_mrp = provider_data.get("mrp") if provider_data else None
    prov_nq = provider_data.get("net_quantity") if provider_data else None
    prov_mf = provider_data.get("manufacturer") if provider_data else None

    fused_mrp = fuse_field("mrp", ocr_mrp, ocr_mrp_conf, prov_mrp, 1.0)
    fused_nq = fuse_field("net_quantity", ocr_nq, ocr_nq_conf, prov_nq, 1.0)
    fused_mf = fuse_field("manufacturer", ocr_mf, ocr_mf_conf, prov_mf, 1.0)

    declarations: list[DeclDB] = []

    # Map field names to their source image IDs
    field_source_images = {
        "mrp": mrp_source_image,
        "net_quantity": nq_source_image,
        "manufacturer": mf_source_image,
        "manufacture_date": mfd_source_image,
        "expiry_date": exp_source_image,
        "cautions": caution_source_image,
    }

    field_fusions = [
        ("mrp", "LMR-2024-001", fused_mrp, ocr_mrp_raw),
        ("net_quantity", "LMR-2024-002", fused_nq, ocr_nq_raw),
        ("manufacturer", "LMR-2024-003", fused_mf, ocr_mf_raw),
    ]

    for field_name, rule_id, fusion, raw_text in field_fusions:
        decl_id = uuid.uuid4()

        # Find the correct image_id for this field's evidence
        src_label = field_source_images.get(field_name, "front")
        src_img_id = None
        for img in images:
            if img["label"] == src_label:
                src_img_id = img["id"]
                break
        if src_img_id is None and images:
            src_img_id = images[0]["id"]

        evidence_entries: list[EvDB] = []
        for src in fusion.sources:
            ev = EvDB(
                id=uuid.uuid4(),
                source_type=EvidenceSourceType.OCR if src["source"] == "ocr" else EvidenceSourceType.PRODUCT_DATABASE,
                raw_text=raw_text if src["source"] == "ocr" else f"Provider lookup: {src['source']}",
                confidence=src["confidence"],
                image_id=src_img_id,
                bbox=None,
                preprocessing_variant="ocr_single_pass" if src["source"] == "ocr" else "provider_lookup",
                extracted_at=_now(),
                declaration_id=decl_id,
            )
            evidence_entries.append(ev)

        if fusion.status == "conflict":
            verdict = VerificationState.CONFLICT
            reason = f"conflicting evidence for '{field_name}': OCR={ocr_mrp if field_name=='mrp' else ocr_nq if field_name=='net_quantity' else ocr_mf} vs provider={prov_mrp if field_name=='mrp' else prov_nq if field_name=='net_quantity' else prov_mf}"
            extracted_value = None
        elif fusion.status == "missing":
            verdict = VerificationState.NOT_VERIFIED
            reason = f"{field_name} not found in any evidence source"
            extracted_value = None
        else:
            verdict = VerificationState.SATISFIED
            reason = None
            extracted_value = fusion.fused_value

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

    # ── Step 6b: OCR-only declarations (manufacture_date, expiry_date, cautions) ──
    # These don't have provider lookup — pure OCR extraction
    ocr_only_fields = [
        ("manufacture_date", "LMR-2024-004", mfd),
        ("expiry_date", "LMR-2024-005", exp),
    ]

    for field_name, rule_id, extracted in ocr_only_fields:
        decl_id = uuid.uuid4()
        src_label = field_source_images.get(field_name, "front")
        src_img_id = None
        for img in images:
            if img["label"] == src_label:
                src_img_id = img["id"]
                break
        if src_img_id is None and images:
            src_img_id = images[0]["id"]

        evidence_entries: list[EvDB] = []
        if extracted:
            raw = extracted.get("raw_text", "")
            conf = extracted.get("confidence", 0.0)
            ev = EvDB(
                id=uuid.uuid4(),
                source_type=EvidenceSourceType.OCR,
                raw_text=raw,
                confidence=conf,
                image_id=src_img_id,
                bbox=None,
                preprocessing_variant="ocr_single_pass",
                extracted_at=_now(),
                declaration_id=decl_id,
            )
            evidence_entries.append(ev)
            extracted_value = extracted
            verdict = VerificationState.SATISFIED if conf >= _MIN_CONFIDENCE else VerificationState.NOT_VERIFIED
            reason = None if verdict == VerificationState.SATISFIED else f"insufficient confidence ({conf:.2f} < {_MIN_CONFIDENCE})"
        else:
            extracted_value = None
            verdict = VerificationState.NOT_VERIFIED
            reason = f"{field_name} not found in any evidence source"

        decl = DeclDB(
            id=decl_id,
            scan_id=scan_id,
            field_name=field_name,
            extracted_value=extracted_value,
            rule_id=rule_id,
            verdict=verdict,
            reason=reason,
            confidence=extracted.get("confidence", 0.0) if extracted else 0.0,
            officer_correction=None,
        )
        decl.evidence = evidence_entries
        declarations.append(decl)

    # ── Step 6c: Chronological cross-check (manufacture vs expiry) ──
    date_comparison = _compare_dates_chronologically(mfd, exp)
    if date_comparison == "conflict":
        # Add a CONFLICT evidence entry linking both date declarations
        for decl in declarations:
            if decl.field_name in ("manufacture_date", "expiry_date"):
                conflict_ev = EvDB(
                    id=uuid.uuid4(),
                    source_type=EvidenceSourceType.OCR,
                    raw_text="Chronological conflict: expiry date is before manufacture date",
                    confidence=1.0,
                    image_id=None,
                    bbox=None,
                    preprocessing_variant="date_cross_check",
                    extracted_at=_now(),
                    declaration_id=decl.id,
                )
                decl.evidence.append(conflict_ev)
                decl.verdict = VerificationState.CONFLICT
                decl.reason = "expiry date is chronologically before manufacture date"

    # ── Step 6d: Cautions declaration ──
    caution_decl_id = uuid.uuid4()
    caution_src_label = field_source_images.get("cautions", "front")
    caution_src_img_id = None
    for img in images:
        if img["label"] == caution_src_label:
            caution_src_img_id = img["id"]
            break
    if caution_src_img_id is None and images:
        caution_src_img_id = images[0]["id"]

    caution_evidence: list[EvDB] = []
    if caution_result and caution_result.get("present"):
        caution_ev = EvDB(
            id=uuid.uuid4(),
            source_type=EvidenceSourceType.OCR,
            raw_text=caution_result.get("raw_text", ""),
            confidence=caution_result.get("confidence", 0.0),
            image_id=caution_src_img_id,
            bbox=None,
            preprocessing_variant="ocr_single_pass",
            extracted_at=_now(),
            declaration_id=caution_decl_id,
        )
        caution_evidence.append(caution_ev)
        caution_verdict = VerificationState.SATISFIED
        caution_extracted = caution_result
        caution_reason = None
    elif caution_result:
        # Extracted but present=False — store the dict so UI shows "Not present"
        caution_verdict = VerificationState.SATISFIED
        caution_extracted = caution_result
        caution_reason = None
    else:
        caution_verdict = VerificationState.NOT_VERIFIED
        caution_extracted = None
        caution_reason = "no caution/warning found on label"

    caution_decl = DeclDB(
        id=caution_decl_id,
        scan_id=scan_id,
        field_name="cautions",
        extracted_value=caution_extracted,
        rule_id="LMR-2024-007",
        verdict=caution_verdict,
        reason=caution_reason,
        confidence=caution_result.get("confidence", 0.0) if caution_result else 0.0,
        officer_correction=None,
    )
    caution_decl.evidence = caution_evidence
    declarations.append(caution_decl)

    # ── Step 6e: Nutrition facts declaration ──
    nutrition_decl_id = uuid.uuid4()
    # Find the best source image for nutrition (back-first)
    nutrition_src_label = "back" if "back" in ocr_by_label else "front"
    nutrition_src_img_id = None
    for img in images:
        if img["label"] == nutrition_src_label:
            nutrition_src_img_id = img["id"]
            break
    if nutrition_src_img_id is None and images:
        nutrition_src_img_id = images[0]["id"]

    nutrition_evidence: list[EvDB] = []
    if nutrition_list:
        # Overall verdict: SATISFIED if any nutrient extracted, NOT_VERIFIED otherwise
        has_nutrition = any(n.get("value") is not None for n in nutrition_list)
        avg_conf = sum(n["confidence"] for n in nutrition_list) / len(nutrition_list) if nutrition_list else 0.0

        # Create one evidence entry per nutrient
        for n in nutrition_list:
            nf_ev = EvDB(
                id=uuid.uuid4(),
                source_type=EvidenceSourceType.OCR,
                raw_text=n.get("raw_text", ""),
                confidence=n["confidence"],
                image_id=nutrition_src_img_id,
                bbox=None,
                preprocessing_variant="ocr_single_pass",
                extracted_at=_now(),
                declaration_id=nutrition_decl_id,
            )
            nutrition_evidence.append(nf_ev)

        nutrition_verdict = VerificationState.SATISFIED if has_nutrition else VerificationState.NOT_VERIFIED
        nutrition_extracted = nutrition_list
        nutrition_reason = None if has_nutrition else "no nutrition data found"
    else:
        nutrition_verdict = VerificationState.NOT_VERIFIED
        nutrition_extracted = None
        nutrition_reason = "no nutrition panel detected"
        avg_conf = 0.0

    nutrition_decl = DeclDB(
        id=nutrition_decl_id,
        scan_id=scan_id,
        field_name="nutrition_facts",
        extracted_value=nutrition_extracted,
        rule_id="LMR-2024-006",
        verdict=nutrition_verdict,
        reason=nutrition_reason,
        confidence=avg_conf,
        officer_correction=None,
    )
    nutrition_decl.evidence = nutrition_evidence
    declarations.append(nutrition_decl)

    # Persist nutrition facts to NutritionFact table
    for n in (nutrition_list or []):
        nf = NFDB(
            id=uuid.uuid4(),
            declaration_id=nutrition_decl_id,
            nutrient=n["nutrient"],
            value=n.get("value"),
            unit=n.get("unit", "g"),
            confidence=n["confidence"],
            raw_text=n.get("raw_text", ""),
        )
        db.add(nf)

    # ── Step 7: Rule engine ──
    engine = RuleEngine(db)
    overall, results = engine.evaluate(declarations, inspection_date, product_category)

    results_by_field = {r["field_name"]: r for r in results}
    for decl in declarations:
        r = results_by_field.get(decl.field_name)
        if r:
            decl.verdict = r["verdict"]
            decl.reason = r["reason"]
            decl.confidence = r["confidence"] if r["confidence"] is not None else 0.0

            # For nutrition_facts, store per-nutrient details in compliance_results
            details = {"reason": r["reason"]}
            if decl.field_name == "nutrition_facts" and nutrition_list:
                details["per_nutrient"] = [
                    {"nutrient": n["nutrient"], "value": n.get("value"),
                     "unit": n.get("unit"), "confidence": n["confidence"]}
                    for n in nutrition_list
                ]

            cr = CRDB(
                id=uuid.uuid4(),
                declaration_id=decl.id,
                rule_id=r["rule_id"],
                status=r["verdict"],
                details=details,
            )
            decl.compliance_results = [cr]

    # Merge barcode warnings into image quality if any
    if barcode_warnings:
        image_quality["_barcode_warnings"] = barcode_warnings

    return image_quality, declarations, overall, barcode_evidence, product_id
