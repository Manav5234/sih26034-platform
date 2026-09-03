"""Scan pipeline — real image quality analysis + mocked declarations / evidence.

image_quality now uses the real OpenCV-based analyzer; everything else remains
mocked so the end‑to‑end flow works without a full OCR pipeline.
"""
import uuid
from datetime import datetime, timezone
from typing import List, Tuple

from app.db.models import (
    Declaration as DeclDB,
    Evidence as EvDB,
    ComplianceResult as CRDB,
    EvidenceSourceType,
    VerificationState,
)
from app.image_quality import ImageQualityAnalyzer


def _now():
    return datetime.now(timezone.utc)


def run_mocked_pipeline(
    scan_id: uuid.UUID,
    image_ids: List[uuid.UUID],
) -> Tuple[dict, List[DeclDB], VerificationState]:
    """Return (image_quality_dict, declarations, overall_status)."""

    # Read the first uploaded image from temp storage to run real quality checks.
    # The file path format is: /data/uploads/<scan_id>/<filename>

    image_quality: dict = {"blur": "low", "glare": "none", "perspective": "slight_tilt", "resolution": "300dpi", "recommended_action": "proceed"}

    # Try to locate and read the first image file for quality analysis
    scan_str = str(scan_id)
    upload_dir = f"/data/uploads/{scan_str}"
    if os.path.isdir(upload_dir):
        files = os.listdir(upload_dir)
        if files:
            first_file = os.path.join(upload_dir, files[0])
            try:
                bgr = cv2.imread(first_file)
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
                # If anything goes wrong (corrupt file, etc.) keep defaults
                pass

    # At least 3 declaration fields as specified
    field_specs = [
        {
            "field_name": "mrp",
            "extracted_value": {"amount": 499.0, "currency": "INR"},
            "rule_id": "LMR-2024-001",
            "raw_text": "MRP Rs. 499.00",
            "bbox": {"x": 120.0, "y": 45.0, "width": 200.0, "height": 30.0},
        },
        {
            "field_name": "net_quantity",
            "extracted_value": {"value": 500.0, "unit": "g"},
            "rule_id": "LMR-2024-002",
            "raw_text": "Net Qty. 500 g",
            "bbox": {"x": 120.0, "y": 85.0, "width": 180.0, "height": 25.0},
        },
        {
            "field_name": "manufacturer",
            "extracted_value": "FreshHarvest Pvt Ltd",
            "rule_id": "LMR-2024-003",
            "raw_text": "Mfd by: FreshHarvest Pvt Ltd",
            "bbox": {"x": 50.0, "y": 200.0, "width": 250.0, "height": 20.0},
        },
    ]

    declarations: List[DeclDB] = []
    for spec in field_specs:
        decl_id = uuid.uuid4()
        img_id = image_ids[0] if image_ids else None

        evidence = EvDB(
            id=uuid.uuid4(),
            source_type=EvidenceSourceType.OCR,
            raw_text=spec["raw_text"],
            confidence=0.85,
            image_id=img_id,
            bbox=spec["bbox"],
            preprocessing_variant="crop_2_denoised",
            extracted_at=_now(),
            declaration_id=decl_id,
        )

        decl = DeclDB(
            id=decl_id,
            scan_id=scan_id,
            field_name=spec["field_name"],
            extracted_value=spec["extracted_value"],
            rule_id=spec["rule_id"],
            verdict=VerificationState.NOT_VERIFIED,
            reason="mocked pipeline — not yet analyzed",
            confidence=0.0,
            officer_correction=None,
        )
        decl.evidence = [evidence]

        cr = CRDB(
            id=uuid.uuid4(),
            declaration_id=decl_id,
            rule_id=spec["rule_id"],
            status=VerificationState.NOT_VERIFIED,
            details={"mock": True},
        )
        decl.compliance_results = [cr]

        declarations.append(decl)

    return image_quality, declarations, VerificationState.NOT_VERIFIED
