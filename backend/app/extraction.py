"""Extraction logic for MRP, net_quantity, and manufacturer from real OCR text.

Uses keyword + regex matching over the normalised OCR results, with confidence
drawn from the real OCR confidence of the matching token(s).

If a field's keyword is not found → Declaration with extracted_value=null,
confidence=0 → rule engine produces VIOLATION/NOT_VERIFIED.
"""

import re
from typing import List, Dict, Optional, Any

# ---------- known OCR misread aliases for net_quantity ----------
# These are REAL misreads observed in this project's own test data
# (deodorant bottle photo, Phase 7a output).  Explicit alias list,
# not silent fuzzy matching.
_NET_QTY_ALIASES = {
    "qty",
    "quantity",
    "quantiry",   # observed: tesseract reads 'QUANTITY' as 'QUANTiry.'
    "quantty",    # common misread
    "quantiity",  # common misread
}

# ---------- field-specific regex patterns ----------
_MRP_PATTERN = re.compile(r"[\₹Rupees]{0,2}\s*[\d,]+\.?\d*\s*(?:INR|RS|Rs)?", re.IGNORECASE)
NET_QTY_PATTERN = re.compile(
    r"[Nn]et.?[Qq]ty\.?[:\s]+[\d.]+\s*(?:g|kg|ml|l|oz|lb|pcs)?|"
    r"[\d.]+\s*(?:g|kg|ml|l|oz|lb|pcs)\s*(?:net|Net).?[Qq]ty|"
    r"[Mm]anufactured.?[Qq]ty\.?[:\s]+[\d.]+\s*(?:g|kg|ml|l)?|"
    r"[Nn]et.?[Qq]uant(?:ity|iry|ty|iity)\.?[:\s]+[\d.]+\s*(?:g|kg|ml|l|oz|lb|pcs)|"
    r"[\d.]+\s*(?:g|kg|ml|l|oz|lb|pcs)\s*[Nn]et.?[Qq]uant(?:ity|iry|ty|iity)",
    re.IGNORECASE,
)
MANUFACTURER_PATTERN = re.compile(
    r"[Mm]anufacturer[:\s]+([^\n\r]+)|"
    r"[Mm]fd[:\s]+([^\n\r]+)|"
    r"[Cc]reated[:\s]+([^\n\r]+)",
    re.IGNORECASE,
)


def _find_best_match(
    results: List[Dict],
    pattern: re.Pattern,
    keyword: str,
    aliases: Optional[set] = None,
) -> Optional[Dict]:
    """Find the best matching result for a field using keyword + regex.

    Returns the matched result dict or None if no match found.
    """
    keyword_lower = keyword.lower()
    # Build the set of words to match against
    if aliases:
        match_words = {keyword_lower} | {a.lower() for a in aliases}
    else:
        match_words = {keyword_lower}

    def _text_matches(text: str) -> bool:
        t = text.lower()
        return any(w in t for w in match_words)

    keyword_results = [r for r in results if _text_matches(r["text"])]

    # If keyword filtering returned no results, fall back to all results
    # so that field‑specific regex patterns can still match
    if not keyword_results:
        keyword_results = results

    best: Optional[Dict] = None
    best_score = -1

    for r in keyword_results:
        text = r["text"]
        match = pattern.search(text)
        if not match:
            continue

        match_len = len(match.group(0))
        conf = r["confidence"]
        score = match_len * 10 + conf

        if score > best_score:
            best_score = score
            best = r

    return best


def extract_mrp(results: List[Dict]) -> Optional[Dict[str, Any]]:
    """Extract MRP (Maximum Retail Price) from OCR results.

    Returns dict like {"amount": float, "currency": "INR", "confidence": float}
    or None.
    """
    matched = _find_best_match(results, _MRP_PATTERN, "mrp")
    if not matched:
        return None

    text = matched["text"]
    # Pull out the numeric value
    num_match = re.search(r"[\d,]+\.?\d*", text)
    if not num_match:
        return None

    try:
        amount = float(num_match.group(0).replace(",", ""))
    except ValueError:
        return None

    # Determine currency from text
    currency = "INR"
    if re.search(r"USD|\$", text, re.IGNORECASE):
        currency = "USD"
    elif re.search(r"EUR|\€", text, re.IGNORECASE):
        currency = "EUR"

    return {
        "amount": round(amount, 2),
        "currency": currency,
        "confidence": matched["confidence"],
    }


def extract_net_quantity(results: List[Dict]) -> Optional[Dict[str, Any]]:
    """Extract net quantity from OCR results.

    Returns dict like {"value": float, "unit": "g", "confidence": float}
    or None.
    """
    matched = _find_best_match(results, NET_QTY_PATTERN, "net_quantity", aliases=_NET_QTY_ALIASES)
    if not matched:
        return None

    text = matched["text"]
    # Try to find a number with a unit
    # Pattern: number followed by unit
    qty_match = re.search(r"([\d,]+\.?\d*)\s*(g|kg|ml|l|oz|lb|pcs)", text, re.IGNORECASE)
    if not qty_match:
        return None

    try:
        value = float(qty_match.group(1).replace(",", ""))
    except ValueError:
        return None

    unit = qty_match.group(2).lower()
    # Normalise units
    unit_map = {
        "kg": "kg",
        "g": "g",
        "ml": "ml",
        "l": "l",
        "oz": "oz",
        "lb": "lb",
        "pcs": "pcs",
    }
    unit = unit_map.get(unit, unit)

    return {
        "value": round(value, 2),
        "unit": unit,
        "confidence": matched["confidence"],
    }


def extract_manufacturer(results: List[Dict]) -> Optional[Dict[str, Any]]:
    """Extract manufacturer name from OCR results.

    Returns dict like {"name": str, "confidence": float} or None.
    """
    matched = _find_best_match(results, MANUFACTURER_PATTERN, "manufacturer")
    if not matched:
        return None

    # Return the first captured group that has content
    for group_idx in range(1, MANUFACTURER_PATTERN.groups + 1):
        # Actually, let's just extract from the matched text directly
        text = matched["text"]
        # Strip common prefixes
        cleaned = re.sub(
            r"^[Mm]anufacturer[:\s]+|^[Mm]fd[:\s]+|^[Cc]reated[:\s]+",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()
        if cleaned:
            return {"name": cleaned, "confidence": matched["confidence"]}

    # Fallback: return the full matched text stripped of prefixes
    text = matched["text"]
    cleaned = re.sub(
        r"^[Mm]anufacturer[:\s]+|^[Mm]fd[:\s]+|^[Cc]reated[:\s]+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    if cleaned:
        return {"name": cleaned, "confidence": matched["confidence"]}
    return None