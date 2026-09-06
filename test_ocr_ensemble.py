"""Smoke test for OCR ensemble module."""
import sys
sys.path.insert(0, '.')

from app.ocr_ensemble import (
    OCREvidence, _texts_agree, _bboxes_agree, _confidence_similar,
    ensemble_ocr_evidence,
)

# Test _texts_agree
c1 = OCREvidence(text='MRP Rs. 150', bbox=[10,20,50,15], confidence=0.9, source_provider='tesseract')
c2 = OCREvidence(text='MRP Rs. 150', bbox=[12,22,52,17], confidence=0.88, source_provider='paddleocr')
agree = _texts_agree(c1, c2)
assert agree == True, f"Expected texts to agree, got {agree}"

c3 = OCREvidence(text='€1500', bbox=[10,20,50,15], confidence=0.81, source_provider='tesseract')
c4 = OCREvidence(text='₹ 1500', bbox=[10,20,50,15], confidence=0.93, source_provider='paddleocr')
agree2 = _texts_agree(c3, c4)
assert agree2 == False, f"Expected texts to disagree, got {agree2}"

# Test _bboxes_agree
c5 = OCREvidence(text='test', bbox=[10,20,50,15], confidence=0.9, source_provider='tesseract')
c6 = OCREvidence(text='test', bbox=[12,22,52,17], confidence=0.88, source_provider='paddleocr')
bbox_agree = _bboxes_agree(c5, c6, iou_threshold=0.5)
print(f"BBoxes agree (IoU=0.5): {bbox_agree}")  # Should be True for overlapping boxes

# Test _confidence_similar
conf_sim = _confidence_similar(c1, c2, threshold=0.1)
assert conf_sim == True, f"Expected confidences similar, got {conf_sim}"

conf_sim2 = _confidence_similar(c1, c3, threshold=0.1)
assert conf_sim2 == False, f"Expected confidences dissimilar, got {conf_sim2}"

# Test ensemble with conflict (different currencies)
result = ensemble_ocr_evidence({
    'mrp': [
        OCREvidence(text='₹ 1500', bbox=[10,20,50,15], confidence=0.93, source_provider='paddleocr'),
        OCREvidence(text='€1500', bbox=[10,20,50,15], confidence=0.81, source_provider='tesseract'),
    ]
})
assert result['mrp']['status'] == 'conflict', f"Expected conflict status, got {result['mrp']['status']}"
assert result['mrp']['fused_value'] is None, "Expected fused_value to be None for conflict"
assert result['mrp']['verification_state'] == 'CONFLICT', f"Expected CONFLICT verdict, got {result['mrp']['verification_state']}"
assert len(result['mrp']['candidates']) == 2, "Expected both candidates preserved"

# Test ensemble with single candidate (agreement)
result2 = ensemble_ocr_evidence({
    'mrp': [
        OCREvidence(text='₹ 1500', bbox=[10,20,50,15], confidence=0.93, source_provider='paddleocr'),
    ]
})
assert result2['mrp']['status'] == 'agreed', f"Expected agreed status, got {result2['mrp']['status']}"
assert result2['mrp']['fused_value'] == '₹ 1500', f"Expected fused value '₹ 1500', got {result2['mrp']['fused_value']}"
assert result2['mrp']['verification_state'] == 'VERIFIED', f"Expected VERIFIED, got {result2['mrp']['verification_state']}"

# Test ensemble with missing field
result3 = ensemble_ocr_evidence({
    'mrp': []
})
assert result3['mrp']['status'] == 'missing', f"Expected missing status, got {result3['mrp']['status']}"
assert result3['mrp']['verification_state'] == 'NOT_VERIFIED', f"Expected NOT_VERIFIED, got {result3['mrp']['verification_state']}"

# Test to_dict conversion
c7 = OCREvidence(text='test', bbox=[1,2,3,4], confidence=0.5, source_provider='tesseract', image_id='img123', preprocessing_variant='deskewed', context_hints=['near_MRP'])
d = c7.to_dict()
assert d['text'] == 'test'
assert d['bbox'] == [1,2,3,4]
assert d['confidence'] == 0.5
assert d['source_provider'] == 'tesseract'
assert d['preprocessing_variant'] == 'deskewed'
assert d['context_hints'] == ['near_MRP']
assert 'context_hints' in d  # ensure it's in the dict output

print('All smoke tests PASSED!')