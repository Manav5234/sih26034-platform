"""Extraction logic for MRP, net_quantity, and manufacturer from real OCR text.

Uses keyword + regex matching over the normalised OCR results, with confidence
drawn from the real OCR confidence of the matching token(s).

If a field's keyword is not found → Declaration with extracted_value=null,
confidence=0 → rule engine produces VIOLATION/NOT_VERIFIED.

Each extraction function returns a dict with an extra ``raw_text`` key containing
the OCR line text that produced the value.  This is the SOLE source of evidence
text — the pipeline must use it, never an independent keyword scan.
"""

import logging
import re
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

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

# Bug 1a fix: require a currency marker (₹, Rs, RS, INR) near the number.
# A bare number with no currency context must never match.
_MRP_PATTERN = re.compile(
    r"(?:₹|Rs\.?|RS\.?|INR)\s*[\d,]+\.?\d*|"   # currency BEFORE number
    r"[\d,]+\.?\d*\s*(?:₹|Rs\.?|RS\.?|INR)",     # currency AFTER number
    re.IGNORECASE,
)
_MRP_ALIASES = {"max", "retail", "price"}

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

# Bug 3: header/reference lines that indicate the keyword is a label, not data
_HEADER_SIGNALS = re.compile(
    r"REFER|NAME.*ADDRESS|LIC\s*NO|FOR\s+MANUFACTURER|LABEL|DETAILS",
    re.IGNORECASE,
)


def _find_best_match(
    results: List[Dict],
    pattern: re.Pattern,
    keyword: str,
    aliases: Optional[set] = None,
    require_keyword: bool = False,
) -> Optional[Dict]:
    """Find the best matching result for a field using keyword + regex.

    Returns the matched result dict or None if no match found.

    If *require_keyword* is True and no line contains the keyword, return
    None immediately instead of falling back to all lines.  This prevents
    phantom extraction from unrelated text.
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

    # Bug 1b fix: when require_keyword=True and no keyword found, do NOT
    # fall back to all results — return None to avoid fabricating values.
    if not keyword_results:
        if require_keyword:
            return None
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

    Returns dict like {"amount": float, "currency": "INR", "confidence": float,
    "raw_text": str} or None.

    Bug 1b fix: require_keyword=True — if no line contains an MRP-related
    keyword (mrp, max, retail, price), return None.  Never fall back to
    scanning unrelated lines for any number.
    """
    matched = _find_best_match(results, _MRP_PATTERN, "mrp", aliases=_MRP_ALIASES, require_keyword=True)
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
        "raw_text": matched["text"],
    }


def extract_net_quantity(results: List[Dict]) -> Optional[Dict[str, Any]]:
    """Extract net quantity from OCR results.

    Returns dict like {"value": float, "unit": "g", "confidence": float,
    "raw_text": str} or None.
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
        "raw_text": matched["text"],
    }


def extract_manufacturer(results: List[Dict]) -> Optional[Dict[str, Any]]:
    """Extract manufacturer name from OCR results.

    Returns dict like {"name": str, "confidence": float, "raw_text": str}
    or None.

    Bug 3 fix: when the keyword-matched line is a header/reference line
    (e.g. "FOR MANUFACTURER'S NAME, ADDRESS AND LIC NO"), search a small
    window of adjacent lines for a plausible manufacturer name/address.
    The regex pattern won't match lines like MANUFACTURER'S (apostrophe),
    so we must do the header check BEFORE the regex gate.
    """
    keyword_results = [r for r in results if any(
        w in r["text"].lower() for w in {"manufacturer", "mfd", "mfg", "created"}
    )]

    if not keyword_results:
        return None

    # Pass 1: try standard regex on keyword-matched lines
    best = None
    best_score = -1
    for r in keyword_results:
        match = MANUFACTURER_PATTERN.search(r["text"])
        if not match:
            continue
        match_len = len(match.group(0))
        score = match_len * 10 + r["confidence"]
        if score > best_score:
            best_score = score
            best = r

    if best is not None:
        cleaned = re.sub(
            r"^[Mm]anufacturer[:\s]+|^[Mm]fd[:\s]+by[:\s]*|^[Mm]fg[:\s]+by[:\s]*|^[Cc]reated[:\s]+by[:\s]*|^[Mm]fd[:\s]+|^[Mm]fg[:\s]+|^[Cc]reated[:\s]+",
            "",
            best["text"],
            flags=re.IGNORECASE,
        ).strip()
        if cleaned:
            return {"name": cleaned, "confidence": best["confidence"], "raw_text": best["text"]}
        return None

    # Pass 2: no regex match — check if any keyword line is a header/reference
    for idx, r in enumerate(keyword_results):
        text = r["text"]
        if not _HEADER_SIGNALS.search(text):
            continue

        # Find original index in the full results list
        matched_idx = None
        for i, full_r in enumerate(results):
            if full_r["text"] == r["text"] and full_r["confidence"] == r["confidence"]:
                matched_idx = i
                break

        if matched_idx is None:
            continue

        # Search 1-3 lines before the header (Indian labels: address above the footnote)
        for offset in range(1, 4):
            check_idx = matched_idx - offset
            if check_idx < 0:
                break
            cand_text = results[check_idx]["text"].strip()
            if re.search(
                r"\b(?:PVT|LTD|LLP|INC|CO|BEVERAGES|ENTERPRISES|INDUSTRIES|MANUFACTURER)\b",
                cand_text,
                re.IGNORECASE,
            ):
                cleaned = re.sub(r"^[^A-Za-z]+", "", cand_text).strip()
                if cleaned:
                    return {
                        "name": cleaned,
                        "confidence": results[check_idx]["confidence"],
                        "raw_text": cand_text,
                    }

    return None
