"""Tests for caution/extraction symbol detection."""
import pytest
from app.extraction import extract_cautions


class TestCautions:
    def test_caution_present_on_label(self):
        results = [{"text": "Caution: Keep away from children", "confidence": 0.90}]
        r = extract_cautions(results)
        assert r is not None
        assert r["present"] is True

    def test_warning_keyword_detected(self):
        results = [{"text": "WARNING: Not suitable for infants", "confidence": 0.88}]
        r = extract_cautions(results)
        assert r is not None
        assert r["present"] is True

    def test_no_cautions_returns_not_present(self):
        results = [
            {"text": "MRP Rs. 499.00", "confidence": 0.90},
            {"text": "Net Qty 500g", "confidence": 0.88},
        ]
        r = extract_cautions(results)
        assert r is not None
        assert r["present"] is False

    def test_empty_results_returns_not_present(self):
        r = extract_cautions([])
        assert r is not None
        assert r["present"] is False

    def test_multiple_caution_lines(self):
        results = [
            {"text": "Warning: Contains nuts", "confidence": 0.85},
            {"text": "Store in a cool place", "confidence": 0.80},
            {"text": "Keep away from direct sunlight", "confidence": 0.78},
        ]
        r = extract_cautions(results)
        assert r is not None
        assert r["present"] is True
        assert "nuts" in r["text"].lower()

    def test_empty_text_returns_not_present(self):
        results = [{"text": "", "confidence": 0.90}]
        r = extract_cautions(results)
        assert r is not None
        assert r["present"] is False
