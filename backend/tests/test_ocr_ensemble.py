"""Smoke test for OCR ensemble module."""
import sys
import os
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