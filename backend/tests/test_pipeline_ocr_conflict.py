"""End-to-end regression test for OCR disagreement propagation."""
from datetime import date
from uuid import uuid4
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import (
    Base,
    Scan,
    Image,
    RuleSet,
    Rule,
    ScanStatus,
    VerificationState,
)
from app.pipeline import run_pipeline


def test_mrp_ocr_disagreement_reaches_compliance_result():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # Minimal rule set required by RuleEngine.
        ruleset = RuleSet(
            id=uuid4(),
            rule_version="TEST-1",
            jurisdiction="India",
            effective_from=date(2020, 1, 1),
            effective_to=None,
        )
        db.add(ruleset)

        db.add(
            Rule(
                id=uuid4(),
                rule_set_id=ruleset.id,
                rule_id="LMR-2024-001",
                required_declaration="mrp",
                applicability="all",
                validation_conditions={
                    "must_be_present": True,
                    "format": "numeric",
                    "min_confidence": 0.5,
                },
            )
        )
        db.commit()

        scan = Scan(
            id=uuid4(),
            status=ScanStatus.PROCESSING,
        )
        db.add(scan)

        front = Image(
            id=uuid4(),
            scan_id=scan.id,
            url="/tmp/front.png",
            label="front",
        )
        back = Image(
            id=uuid4(),
            scan_id=scan.id,
            url="/tmp/back.png",
            label="back",
        )
        db.add_all([front, back])
        db.commit()

        ocr_calls = []

        def fake_ocr(path, quality):
            ocr_calls.append(path)

            if len(ocr_calls) == 1:
                return [
                    {
                        "text": "MRP Rs 50",
                        "bbox": [0, 0, 100, 30],
                        "confidence": 0.95,
                        "source_provider": "tesseract",
                        "preprocessing_variant": "original",
                    }
                ]

            return [
                {
                    "text": "MRP Rs 60",
                    "bbox": [0, 0, 100, 30],
                    "confidence": 0.93,
                    "source_provider": "tesseract",
                    "preprocessing_variant": "deskewed",
                }
            ]

        with patch(
            "app.pipeline._resolve_images",
            return_value=[
                {"id": front.id, "path": "/tmp/front.png", "label": "front"},
                {"id": back.id, "path": "/tmp/back.png", "label": "back"},
            ],
        ), patch(
            "app.pipeline._ocr_with_recrop",
            side_effect=fake_ocr,
        ), patch(
            "app.pipeline.cv2.imread",
            return_value=None,
        ), patch(
            "app.pipeline.BarcodeDecoder.decode",
            return_value=[],
        ):

            _, declarations, overall, _, _ = run_pipeline(
                scan.id,
                [front.id, back.id],
                db,
                inspection_date=date(2026, 9, 19),
                product_category=None,
            )

        mrp_decl = next(d for d in declarations if d.field_name == "mrp")

        assert mrp_decl.verdict == VerificationState.CONFLICT
        assert mrp_decl.extracted_value is None
        assert overall == VerificationState.CONFLICT

        compliance_result = mrp_decl.compliance_results[0]
        assert compliance_result.status == VerificationState.CONFLICT

    finally:
        db.close()
        engine.dispose()
