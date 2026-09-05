"""Tests for extraction.py — Bug 1 (MRP fabrication guard), Bug 2 (correct null), Bug 3 (manufacturer proximity)."""
import pytest
from app.extraction import (
    extract_mrp,
    extract_net_quantity,
    extract_manufacturer,
    _MRP_PATTERN,
    NET_QTY_PATTERN,
    MANUFACTURER_PATTERN,
    _HEADER_SIGNALS,
)


class TestMRPNoFabrication:
    """Bug 1 regression: MRP extraction must NEVER fabricate a value from
    unrelated text when no MRP keyword is present."""

    def test_no_mrp_keyword_returns_none(self):
        """The Coca-Cola 2L bottle OCR dump has no MRP keyword — must return None."""
        # Simulated OCR lines from scan ce92521b (Coca-Cola 2L bottle)
        # Key property: NO line contains "mrp", "max", "retail", or "price"
        coca_cola_lines = [
            {"text": "+ 5 <=:", "confidence": 0.413},
            {"text": "a> - .", "confidence": 0.033},
            {"text": "GREENS: CARBHATED WATE, SUGAR, ACO", "confidence": 0.468},
            {"text": "fe (38), CAFFEINE (8/100), COLOUR (504), ays", "confidence": 0.344},
            {"text": "[NATURAL FLAVOURINGG SUBSTANCES).", "confidence": 0.627},
            {"text": "PER 100ml _PERSERVE _|& ts", "confidence": 0.490},
            {"text": "ENERGY Mikal | 44%", "confidence": 0.496},
            {"text": "TOTALSUGARS |10.6g", "confidence": 0.380},
            {"text": "NFG/NKTBY KANDHARI BEVERAGES PV. LD.", "confidence": 0.530},
            {"text": "21CANAL COLONY, NEAR DISTRICT ADMINISTRATION", "confidence": 0.604},
            {"text": "COMPLEX, AMRITSAR, PUNJAB", "confidence": 0.547},
            {"text": "ais FOR MANUFACTURER'S NAME, ADDRESS AND LICNO, 25, =", "confidence": 0.627},
            {"text": "Ps AD NET QUANTITY: ee Perey", "confidence": 0.350},
        ]
        result = extract_mrp(coca_cola_lines)
        assert result is None, (
            "MRP extraction must return None when no line contains an MRP keyword. "
            "Returning a value from 'PER 100ml' or similar would be fabrication."
        )

    def test_bare_number_without_currency_returns_none(self):
        """A line with only a bare number (no Rs/₹/INR) must not match."""
        lines = [
            {"text": "Batch No: 12345", "confidence": 0.8},
            {"text": "Exp Date: 2025-12", "confidence": 0.9},
        ]
        result = extract_mrp(lines)
        assert result is None

    def test_mrp_with_rs_keyword_matches(self):
        """A line with 'MRP' keyword AND Rs currency marker should match."""
        lines = [
            {"text": "MRP Rs. 199", "confidence": 0.85},
        ]
        result = extract_mrp(lines)
        assert result is not None
        assert result["amount"] == 199.0
        assert result["currency"] == "INR"
        assert result["raw_text"] == "MRP Rs. 199"

    def test_mrp_with_rupee_symbol_matches(self):
        """A line with ₹ symbol should match."""
        lines = [
            {"text": "Maximum Retail Price ₹299", "confidence": 0.9},
        ]
        result = extract_mrp(lines)
        assert result is not None
        assert result["amount"] == 299.0

    def test_mrp_with_inr_suffix_matches(self):
        """A line with INR suffix should match."""
        lines = [
            {"text": "MRP 149.00 INR", "confidence": 0.87},
        ]
        result = extract_mrp(lines)
        assert result is not None
        assert result["amount"] == 149.0
        assert result["currency"] == "INR"

    def test_mrp_keyword_but_no_currency_returns_none(self):
        """If the keyword 'MRP' is present but no currency marker, return None.
        This prevents extracting a bare number that happens to be near 'MRP' text."""
        lines = [
            {"text": "MRP reference code: ABC123", "confidence": 0.7},
        ]
        result = extract_mrp(lines)
        assert result is None

    def test_extract_mrp_returns_raw_text(self):
        """Extraction must include the matched line text."""
        lines = [
            {"text": "MRP Rs. 500", "confidence": 0.9},
        ]
        result = extract_mrp(lines)
        assert result is not None
        assert "raw_text" in result
        assert result["raw_text"] == "MRP Rs. 500"


class TestNetQuantityGarbledOCR:
    """Bug 2 regression: garbled OCR text must NOT produce a fabricated value.
    Scan ce92521b has 'NET QUANTITY: ee Perey' — the value is garbled."""

    def test_garbled_value_returns_none(self):
        """When the keyword matches but the value is garbled, return None."""
        lines = [
            {"text": "Ps AD NET QUANTITY: ee Perey", "confidence": 0.350},
        ]
        result = extract_net_quantity(lines)
        assert result is None, (
            "Net quantity must be None when the value portion is garbled. "
            "Returning a fabricated number from 'ee Perey' would be wrong."
        )

    def test_valid_net_qty_matches(self):
        """Valid 'NET QUANTITY: 150g' should match."""
        lines = [
            {"text": "NET QUANTITY: 150g", "confidence": 0.85},
        ]
        result = extract_net_quantity(lines)
        assert result is not None
        assert result["value"] == 150.0
        assert result["unit"] == "g"

    def test_net_qty_returns_raw_text(self):
        lines = [
            {"text": "Net Qty. 500 ml", "confidence": 0.8},
        ]
        result = extract_net_quantity(lines)
        assert result is not None
        assert result["raw_text"] == "Net Qty. 500 ml"


class TestManufacturerProximity:
    """Bug 3 regression: manufacturer extraction should find adjacent lines
    when the keyword matches a header/reference line."""

    def test_header_line_triggers_proximity_search(self):
        """When 'MANUFACTURER' appears in a reference header, search adjacent lines."""
        lines = [
            {"text": "NFG/NKTBY KANDHARI BEVERAGES PV. LD.", "confidence": 0.530},
            {"text": "21CANAL COLONY, NEAR DISTRICT ADMINISTRATION", "confidence": 0.604},
            {"text": "COMPLEX, AMRITSAR, PUNJAB", "confidence": 0.547},
            {"text": "ais FOR MANUFACTURER'S NAME, ADDRESS AND LICNO, 25, =", "confidence": 0.627},
        ]
        result = extract_manufacturer(lines)
        # Should find one of the adjacent lines with company-type indicators
        assert result is not None, (
            "Manufacturer extraction should find 'KANDHARI BEVERAGES PV. LD.' "
            "from adjacent lines when the keyword line is a reference header."
        )
        # Should contain the company name from a nearby line
        assert "BEVERAGES" in result["name"].upper() or "KANDHARI" in result["name"].upper()

    def test_standard_manufacturer_still_works(self):
        """Normal 'Manufacturer: HUL Pvt Ltd' format must still work."""
        lines = [
            {"text": "Manufacturer: Hindustan Unilever Ltd", "confidence": 0.9},
        ]
        result = extract_manufacturer(lines)
        assert result is not None
        assert "Hindustan Unilever" in result["name"]

    def test_mfd_format_still_works(self):
        """'Mfd by: Some Company' format must still work."""
        lines = [
            {"text": "Mfd by: Coca-Cola India Pvt Ltd", "confidence": 0.85},
        ]
        result = extract_manufacturer(lines)
        assert result is not None
        assert "Coca-Cola" in result["name"]

    def test_no_manufacturer_returns_none(self):
        """When no manufacturer keyword or nearby data exists, return None."""
        lines = [
            {"text": "Some random text", "confidence": 0.5},
            {"text": "More random text", "confidence": 0.6},
        ]
        result = extract_manufacturer(lines)
        assert result is None

    def test_manufacturer_returns_raw_text(self):
        lines = [
            {"text": "Manufacturer: TestCo Ltd", "confidence": 0.88},
        ]
        result = extract_manufacturer(lines)
        assert result is not None
        assert result["raw_text"] == "Manufacturer: TestCo Ltd"


class TestEvidenceRawTextIntegrity:
    """Bug 1c regression: every extraction function must return raw_text."""

    def test_mrp_always_has_raw_text(self):
        lines = [{"text": "MRP Rs. 100", "confidence": 0.9}]
        result = extract_mrp(lines)
        assert result is not None
        assert "raw_text" in result
        assert len(result["raw_text"]) > 0

    def test_net_qty_always_has_raw_text(self):
        lines = [{"text": "Net Qty: 250ml", "confidence": 0.85}]
        result = extract_net_quantity(lines)
        assert result is not None
        assert "raw_text" in result
        assert len(result["raw_text"]) > 0

    def test_manufacturer_always_has_raw_text(self):
        lines = [{"text": "Manufacturer: TestCo", "confidence": 0.88}]
        result = extract_manufacturer(lines)
        assert result is not None
        assert "raw_text" in result
        assert len(result["raw_text"]) > 0
