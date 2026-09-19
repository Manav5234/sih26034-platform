from app.ocr_ensemble import ensemble_ocr_evidence, generate_field_candidates


def _ocr_line(text: str, confidence: float, variant: str) -> dict:
    return {
        "text": text,
        "bbox": [0, 0, 100, 30],
        "confidence": confidence,
        "source_provider": "tesseract",
        "preprocessing_variant": variant,
    }


def test_mrp_disagreement_produces_conflict():
    lines = [
        _ocr_line("MRP Rs 50", 0.95, "original"),
        _ocr_line("MRP Rs 60", 0.93, "deskewed"),
    ]

    candidates = generate_field_candidates(
        lines,
        "mrp",
        "tesseract",
    )

    result = ensemble_ocr_evidence({"mrp": candidates})

    assert result["mrp"]["status"] == "conflict"
    assert result["mrp"]["verification_state"] == "CONFLICT"
    assert result["mrp"]["fused_value"] is None
    assert len(result["mrp"]["candidates"]) == 2