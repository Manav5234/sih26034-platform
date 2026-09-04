"""Mocked product database lookup by barcode.

This is a stub that returns hardcoded data for known barcodes.  Later,
swap this for a real API call behind the same interface — nothing else
changes.  Mirrors the project's own principle: "do not trust one external
product database blindly."
"""

from __future__ import annotations

from typing import Dict, Optional

# Hardcoded product database keyed by barcode string.
# Each entry contains whatever fields the provider can supply.
_MOCK_DB: Dict[str, Dict] = {
    # Real deodorant bottle from test images (EAN13)
    "8901542001406": {
        "net_quantity": {"value": 60, "unit": "g"},
        "manufacturer": "FreshHarvest Ayurveda Pvt Ltd",
    },
    # Fake barcode for testing conflict: net_quantity deliberately differs
    # from a plausible OCR value (OCR would read "500g", lookup says "450g").
    "5901234123457": {
        "net_quantity": {"value": 450, "unit": "g"},
        "manufacturer": "TestCo Consumer Goods Ltd",
        "mrp": {"amount": 299.0, "currency": "INR"},
    },
    # Fake barcode for testing agreement: both OCR and lookup agree on 250ml
    "8901234567890": {
        "net_quantity": {"value": 250, "unit": "ml"},
        "manufacturer": "AgreeCorp Personal Care",
        "mrp": {"amount": 189.0, "currency": "INR"},
    },
}


class ProductLookupAdapter:
    """Look up product data by barcode from a (mocked) external database."""

    @staticmethod
    def lookup(barcode: str) -> Optional[Dict]:
        """Return product data dict or None if barcode not in database.

        Returned dict shape:
            {
                "net_quantity": {"value": float, "unit": str} | None,
                "manufacturer": str | None,
                "mrp": {"amount": float, "currency": str} | None,
            }

        Only keys the provider actually has data for are included.
        """
        return _MOCK_DB.get(barcode)
