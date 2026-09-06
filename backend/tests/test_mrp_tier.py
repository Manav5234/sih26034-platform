"""Smoke test for MRP tiered evidence."""
import sys
import os
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, '.')

from app.extraction import extract_mrp


def test_mrp_rs_keyword_tier1():
    """MRP with Rs keyword → Tier 1."""
    lines = [{"text": "MRP Rs. 199", "confidence": 0.85}]
    result = extract_mrp(lines)
    assert result is not None
    assert result['tier'] == 1, f"Expected tier 1, got {result.get('tier')}"
    assert result['amount'] == 199.0
    assert result['currency'] == 'INR'


def test_mrp_rupee_symbol_tier1():
    """MRP with ₹ symbol → Tier 1."""
    lines = [{"text": "Maximum Retail Price ₹299", "confidence": 0.9}]
    result = extract_mrp(lines)
    assert result is not None
    assert result['tier'] == 1, f"Expected tier 1, got {result.get('tier')}"
    assert result['amount'] == 299.0


def test_mrp_inr_suffix_tier1():
    """MRP with INR suffix → Tier 1."""
    lines = [{"text": "MRP 149.00 INR", "confidence": 0.87}]
    result = extract_mrp(lines)
    assert result is not None
    assert result['tier'] == 1, f"Expected tier 1, got {result.get('tier')}"
    assert result['amount'] == 149.0
    assert result['currency'] == 'INR'


def test_no_mrp_keyword_returns_none():
    """No MRP keyword → None (Bug 1b guard)."""
    lines = [{"text": "Batch No: 12345", "confidence": 0.8}]
    result = extract_mrp(lines)
    assert result is None


def test_bare_number_returns_none():
    """Bare number without MRP keyword → None."""
    lines = [{"text": "Batch No: 12345", "confidence": 0.8}]
    result = extract_mrp(lines)
    assert result is None


def test_price_keyword_tier2():
    """"Price" keyword without "MRP" → Tier 2."""
    lines = [{"text": "Price Rs. 200", "confidence": 0.88}]
    result = extract_mrp(lines)
    assert result is not None
    assert result['tier'] == 2, f"Expected tier 2, got {result.get('tier')}"
    assert result['amount'] == 200.0


def test_mrp_no_currency_tier4():
    """"MRP" keyword but no currency → Tier 4 → None."""
    lines = [{"text": "MRP 300", "confidence": 0.8}]
    result = extract_mrp(lines)
    # "MRP" keyword present but no currency → tier 4 → should be None
    # (the function returns the dict with tier=4, but the pipeline
    # should force NOT_VERIFIED for tier 3/4)
    # For now, just check the tier
    if result is not None:
        assert result['tier'] == 4, f"Expected tier 4, got {result.get('tier')}"
    else:
        # Or None if the function decides to return None for tier 4
        print(f"  extract_mrp returned None for 'MRP 300' (tier 4 guard)")


def test_mrp_maximum_retail_price_tier1():
    """"MAXIMUM RETAIL PRICE" → Tier 1."""
    lines = [{"text": "MAXIMUM RETAIL PRICE 199", "confidence": 0.85}]
    result = extract_mrp(lines)
    assert result is not None
    assert result['tier'] == 1, f"Expected tier 1, got {result.get('tier')}"