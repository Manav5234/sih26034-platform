"""Tests for date extraction (manufacture_date, expiry_date)."""
import pytest
from app.extraction import extract_manufacture_date, extract_expiry_date


class TestManufactureDate:
    def test_mfd_with_dd_mm_yyyy(self):
        results = [{"text": "MFD 12/05/2025", "confidence": 0.90}]
        r = extract_manufacture_date(results)
        assert r is not None
        assert r["value"]["day"] == 12
        assert r["value"]["month"] == 5
        assert r["value"]["year"] == 2025
        assert r["confidence"] > 0.5

    def test_mfg_date_with_mm_yyyy(self):
        results = [{"text": "Mfg Date: 03/2026", "confidence": 0.85}]
        r = extract_manufacture_date(results)
        assert r is not None
        assert r["value"]["day"] is None
        assert r["value"]["month"] == 3
        assert r["value"]["year"] == 2026

    def test_manufactured_on_with_month_name(self):
        results = [{"text": "Manufactured on December 2024", "confidence": 0.88}]
        r = extract_manufacture_date(results)
        assert r is not None
        assert r["value"]["month"] == 12
        assert r["value"]["year"] == 2024

    def test_batch_date_with_two_digit_year(self):
        results = [{"text": "Batch Date: 15-08-25", "confidence": 0.92}]
        r = extract_manufacture_date(results)
        assert r is not None
        assert r["value"]["year"] == 2025  # normalized from 2-digit

    def test_no_mfd_keyword_returns_none(self):
        results = [{"text": "MRP Rs. 499.00", "confidence": 0.90}]
        r = extract_manufacture_date(results)
        assert r is None

    def test_garbled_date_returns_none(self):
        results = [{"text": "MFD abc/xyz/123", "confidence": 0.70}]
        r = extract_manufacture_date(results)
        assert r is None

    def test_empty_results_returns_none(self):
        r = extract_manufacture_date([])
        assert r is None


class TestExpiryDate:
    def test_exp_with_dd_mm_yyyy(self):
        results = [{"text": "EXP 25/12/2026", "confidence": 0.88}]
        r = extract_expiry_date(results)
        assert r is not None
        assert r["value"]["day"] == 25
        assert r["value"]["month"] == 12
        assert r["value"]["year"] == 2026

    def test_best_before_with_month_year(self):
        results = [{"text": "Best Before: 06/2027", "confidence": 0.85}]
        r = extract_expiry_date(results)
        assert r is not None
        assert r["value"]["month"] == 6
        assert r["value"]["year"] == 2027

    def test_use_by_keyword(self):
        results = [{"text": "Use By: Jan 2026", "confidence": 0.90}]
        r = extract_expiry_date(results)
        assert r is not None
        assert r["value"]["month"] == 1
        assert r["value"]["year"] == 2026

    def test_no_exp_keyword_returns_none(self):
        results = [{"text": "MRP Rs. 499.00", "confidence": 0.90}]
        r = extract_expiry_date(results)
        assert r is None

    def test_garbled_date_returns_none(self):
        results = [{"text": "Exp: xyz/abc/def", "confidence": 0.60}]
        r = extract_expiry_date(results)
        assert r is None
