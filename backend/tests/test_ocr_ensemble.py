"""Smoke test for OCR ensemble module + provider chain honesty tests."""
import sys
import os
import unittest.mock as mock
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, '.')

from app.ocr_ensemble import (
    OCREvidence, _texts_agree, _bboxes_agree, _confidence_similar,
    generate_field_candidates, ensemble_ocr_evidence,
)


def test_texts_agree():
    """Test OCR text comparison for agreement."""
    c1 = OCREvidence(text='MRP Rs. 150', bbox=[10,20,50,15], confidence=0.9, source_provider='tesseract')
    c2 = OCREvidence(text='MRP Rs. 150', bbox=[12,22,52,17], confidence=0.88, source_provider='paddleocr')
    assert _texts_agree(c1, c2) == True

    c3 = OCREvidence(text='€1500', bbox=[10,20,50,15], confidence=0.81, source_provider='tesseract')
    c4 = OCREvidence(text='₹ 1500', bbox=[10,20,50,15], confidence=0.93, source_provider='paddleocr')
    assert _texts_agree(c3, c4) == False


def test_bboxes_agree():
    """Test bounding box IoU comparison."""
    c5 = OCREvidence(text='test', bbox=[10,20,50,15], confidence=0.9, source_provider='tesseract')
    c6 = OCREvidence(text='test', bbox=[12,22,52,17], confidence=0.88, source_provider='paddleocr')
    # These boxes heavily overlap, should agree
    assert _bboxes_agree(c5, c6, iou_threshold=0.5) == True


def test_confidence_similar():
    """Test confidence comparison."""
    c1 = OCREvidence(text='test', bbox=[10,20,50,15], confidence=0.9, source_provider='tesseract')
    c2 = OCREvidence(text='test', bbox=[12,22,52,17], confidence=0.88, source_provider='paddleocr')
    assert _confidence_similar(c1, c2, threshold=0.1) == True

    # 0.9 - 0.88 = 0.02, which is > 0.01
    assert _confidence_similar(c1, c2, threshold=0.01) == False


def test_ensemble_conflict():
    """Test ensemble produces CONFLICT when candidates disagree."""
    result = ensemble_ocr_evidence({
        'mrp': [
            OCREvidence(text='₹ 1500', bbox=[10,20,50,15], confidence=0.93, source_provider='paddleocr'),
            OCREvidence(text='€1500', bbox=[10,20,50,15], confidence=0.81, source_provider='tesseract'),
        ]
    })
    assert result['mrp']['status'] == 'conflict'
    assert result['mrp']['fused_value'] is None
    assert result['mrp']['verification_state'] == 'CONFLICT'
    assert len(result['mrp']['candidates']) == 2


def test_ensemble_agreement():
    """Test ensemble produces AGREED when single candidate."""
    result = ensemble_ocr_evidence({
        'mrp': [
            OCREvidence(text='₹ 1500', bbox=[10,20,50,15], confidence=0.93, source_provider='paddleocr'),
        ]
    })
    assert result['mrp']['status'] == 'agreed'
    assert result['mrp']['fused_value'] == '₹ 1500'
    assert result['mrp']['verification_state'] == 'VERIFIED'


def test_ensemble_missing():
    """Test ensemble returns NOT_VERIFIED for missing field."""
    result = ensemble_ocr_evidence({
        'mrp': []
    })
    assert result['mrp']['status'] == 'missing'
    assert result['mrp']['verification_state'] == 'NOT_VERIFIED'


def test_generate_field_candidates_mrp():
    """Test field candidate generation for MRP."""
    lines = [
        OCREvidence(text='MRP Rs. 299', bbox=[10,20,50,15], confidence=0.9, source_provider='tesseract', preprocessing_variant='original'),
        OCREvidence(text='Some random text', bbox=[10,20,50,15], confidence=0.5, source_provider='tesseract', preprocessing_variant='original'),
    ]
    candidates = generate_field_candidates(lines, 'mrp', 'tesseract', 'img1')
    assert len(candidates) >= 1
    assert any(c.text == 'MRP Rs. 299' for c in candidates)


def test_generate_field_candidates_net_qty():
    """Test field candidate generation for net_quantity."""
    lines = [
        OCREvidence(text='Net Qty 500g', bbox=[10,20,50,15], confidence=0.85, source_provider='tesseract', preprocessing_variant='original'),
    ]
    candidates = generate_field_candidates(lines, 'net_quantity', 'tesseract', 'img1')
    assert len(candidates) >= 1


def test_generate_field_candidates_manufacturer():
    """Test field candidate generation for manufacturer."""
    lines = [
        OCREvidence(text='Manufacturer: HUL Pvt Ltd', bbox=[10,20,80,15], confidence=0.9, source_provider='tesseract', preprocessing_variant='original'),
    ]
    candidates = generate_field_candidates(lines, 'manufacturer', 'tesseract', 'img1')
    assert len(candidates) >= 1


# ---------------------------------------------------------------------------
# Provider chain honesty tests — source_provider must be truthful
# ---------------------------------------------------------------------------

def test_provider_chain_order():
    """RapidOCR must be first in the chain, Tesseract second."""
    from app.ocr_provider import get_provider_chain
    chain = get_provider_chain()
    assert len(chain) == 2
    assert chain[0].name == "rapidocr"
    assert chain[1].name == "tesseract"


def test_rapidocr_provider_tags_source_honestly():
    """RapidOCRProvider.extract must set source_provider='rapidocr' on every result."""
    from app.ocr_provider import RapidOCRProvider
    provider = RapidOCRProvider()

    # Mock RapidOCR to return fake results
    # RapidOCR returns: list of [polygon, text, confidence_str]
    # polygon = [[x1,y1], [x2,y2], [x3,y3], [x4,y4]], confidence is str
    fake_result = [
        [[[10, 10], [200, 10], [200, 30], [10, 30]], "MRP Rs. 499", "0.92"],
        [[[10, 40], [200, 40], [200, 60], [10, 60]], "Net Qty 500g", "0.88"],
    ]

    with mock.patch.object(provider, '_ensure_loaded'):
        provider._initialized = True
        provider._engine = mock.MagicMock()
        provider._engine.return_value = (fake_result, [0.1, 0.05])

        result = provider.extract("/fake/image.png")

    assert len(result["tokens"]) == 2
    assert len(result["lines"]) == 2
    for item in result["tokens"]:
        assert item["source_provider"] == "rapidocr", (
            f"RapidOCRProvider must tag source_provider='rapidocr', "
            f"got '{item['source_provider']}'"
        )
    for item in result["lines"]:
        assert item["source_provider"] == "rapidocr"
    # Verify bbox conversion: polygon [[10,10],[200,10],[200,30],[10,30]] → [10,10,190,20]
    first_bbox = result["lines"][0]["bbox"]
    assert first_bbox == [10.0, 10.0, 190.0, 20.0]


def test_rapidocr_provider_empty_when_not_installed():
    """RapidOCRProvider returns empty results when rapidocr-onnxruntime is missing."""
    from app.ocr_provider import RapidOCRProvider
    provider = RapidOCRProvider()

    with mock.patch("builtins.__import__", side_effect=ImportError("no module")):
        result = provider.extract("/fake/image.png")

    assert result == {"tokens": [], "lines": []}


def test_tesseract_provider_tags_source_honestly():
    """TesseractProvider.extract must set source_provider='tesseract' on every result."""
    from app.ocr_provider import TesseractProvider
    provider = TesseractProvider()

    fake_ocr_result = {
        "tokens": [
            {"text": "MRP", "bbox": [10, 20, 50, 15], "confidence": 0.9},
        ],
        "lines": [
            {"text": "MRP Rs. 499", "bbox": [10, 20, 200, 15], "confidence": 0.88},
        ],
    }

    with mock.patch("app.ocr.run_ocr", return_value=fake_ocr_result):
        result = provider.extract("/fake/image.png")

    for item in result["tokens"]:
        assert item["source_provider"] == "tesseract", (
            f"TesseractProvider must tag source_provider='tesseract', "
            f"got '{item['source_provider']}'"
        )
    for item in result["lines"]:
        assert item["source_provider"] == "tesseract"


def test_run_ocr_with_provider_uses_rapidocr_first():
    """run_ocr_with_provider returns RapidOCR results when it succeeds."""
    from app.ocr_provider import run_ocr_with_provider, RapidOCRProvider, TesseractProvider

    rapid_result = {
        "tokens": [{"text": "Hello", "bbox": [0, 0, 50, 10], "confidence": 0.9,
                     "source_provider": "rapidocr", "preprocessing_variant": "single_pass"}],
        "lines": [{"text": "Hello", "bbox": [0, 0, 50, 10], "confidence": 0.9,
                    "source_provider": "rapidocr", "preprocessing_variant": "single_pass"}],
    }

    rapid_mock = mock.MagicMock()
    rapid_mock.extract.return_value = rapid_result

    tesseract_mock = mock.MagicMock()
    tesseract_mock.extract.return_value = {"tokens": [], "lines": []}

    chain = [rapid_mock, tesseract_mock]
    result = run_ocr_with_provider("/fake/img.png", provider_chain=chain)

    assert result["lines"][0]["source_provider"] == "rapidocr"
    rapid_mock.extract.assert_called_once()
    tesseract_mock.extract.assert_not_called()


def test_run_ocr_with_provider_falls_back_to_tesseract():
    """run_ocr_with_provider falls back to Tesseract when RapidOCR fails."""
    from app.ocr_provider import run_ocr_with_provider

    tesseract_result = {
        "tokens": [{"text": "World", "bbox": [0, 0, 50, 10], "confidence": 0.85,
                     "source_provider": "tesseract", "preprocessing_variant": "single_pass"}],
        "lines": [{"text": "World", "bbox": [0, 0, 50, 10], "confidence": 0.85,
                    "source_provider": "tesseract", "preprocessing_variant": "single_pass"}],
    }

    rapid_mock = mock.MagicMock()
    rapid_mock.extract.side_effect = RuntimeError("RapidOCR crashed")

    tesseract_mock = mock.MagicMock()
    tesseract_mock.extract.return_value = tesseract_result

    chain = [rapid_mock, tesseract_mock]
    result = run_ocr_with_provider("/fake/img.png", provider_chain=chain)

    assert result["lines"][0]["source_provider"] == "tesseract"
    rapid_mock.extract.assert_called_once()
    tesseract_mock.extract.assert_called_once()


def test_run_ocr_with_provider_never_relabels():
    """Crucial honesty test: when RapidOCR fails and Tesseract runs,
    every result must say 'tesseract', never 'rapidocr' or 'paddleocr'."""
    from app.ocr_provider import run_ocr_with_provider

    tesseract_result = {
        "tokens": [{"text": "X", "bbox": [0, 0, 10, 10], "confidence": 0.7,
                     "source_provider": "tesseract", "preprocessing_variant": "single_pass"}],
        "lines": [{"text": "X", "bbox": [0, 0, 10, 10], "confidence": 0.7,
                    "source_provider": "tesseract", "preprocessing_variant": "single_pass"}],
    }

    rapid_mock = mock.MagicMock()
    rapid_mock.extract.return_value = {"tokens": [], "lines": []}  # empty = not useful

    tesseract_mock = mock.MagicMock()
    tesseract_mock.extract.return_value = tesseract_result

    chain = [rapid_mock, tesseract_mock]
    result = run_ocr_with_provider("/fake/img.png", provider_chain=chain)

    for item in result["tokens"] + result["lines"]:
        assert item["source_provider"] == "tesseract"
        assert item["source_provider"] != "rapidocr"
        assert item["source_provider"] != "paddleocr"
        assert item["source_provider"] != "paddleocr_fallback"


def test_rapidocr_handles_malformed_confidence():
    """RapidOCRProvider must not crash on garbage confidence values."""
    from app.ocr_provider import RapidOCRProvider
    provider = RapidOCRProvider()

    # confidence as empty string, garbage, >1.0, negative
    fake_result = [
        [[[0, 0], [50, 0], [50, 10], [0, 10]], "Hello", ""],
        [[[0, 15], [50, 15], [50, 25], [0, 25]], "World", "not_a_number"],
        [[[0, 30], [50, 30], [50, 40], [0, 40]], "High", "1.5"],
        [[[0, 45], [50, 45], [50, 55], [0, 55]], "Neg", "-0.3"],
    ]

    with mock.patch.object(provider, '_ensure_loaded'):
        provider._initialized = True
        provider._engine = mock.MagicMock()
        provider._engine.return_value = (fake_result, [0.1])

        result = provider.extract("/fake/image.png")

    # Should produce 4 entries without crashing
    assert len(result["lines"]) == 4
    # Empty conf → 0.0, garbage → 0.0, >1.0 → clamped to 1.0, negative → clamped to 0.0
    assert result["lines"][0]["confidence"] == 0.0
    assert result["lines"][1]["confidence"] == 0.0
    assert result["lines"][2]["confidence"] == 1.0
    assert result["lines"][3]["confidence"] == 0.0
    # All tagged honestly
    for item in result["lines"]:
        assert item["source_provider"] == "rapidocr"


def test_rapidocr_handles_rapidocr_exception():
    """RapidOCRProvider must return empty on engine crash, not propagate."""
    from app.ocr_provider import RapidOCRProvider
    provider = RapidOCRProvider()

    with mock.patch.object(provider, '_ensure_loaded'):
        provider._initialized = True
        provider._engine = mock.MagicMock()
        provider._engine.side_effect = RuntimeError("ONNXruntime crashed")

        result = provider.extract("/fake/image.png")

    assert result == {"tokens": [], "lines": []}