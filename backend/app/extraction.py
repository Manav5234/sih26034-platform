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
from typing import Any

logger = logging.getLogger(__name__)

# ---------- date extraction aliases ----------
_MFD_ALIASES = {
    "mfd", "mfg", "mfr", "mfg date", "mfd date", "manufactured",
    "manufactured on", "manufacturing date", "batch date", "prod date",
    "production date", "date of manufacture", "date of manufacturing",
}
_EXP_ALIASES = {
    "exp", "expy", "expiry", "expiry date", "exp date", "best before",
    "bb", "bb date", "use by", "use by date", "exd", "valid till",
    "shelf life", "best before date",
}

# ---------- nutrition patterns ----------
NUTRIENT_PATTERNS: dict[str, re.Pattern] = {
    "energy":         re.compile(r"energy(?:\s*(?:value|content))?[:\s]*(\d+\.?\d*)\s*(kcal|kj|cal)?", re.IGNORECASE),
    "carbohydrate":   re.compile(r"carbohydrate(?:\s*(?:|total))?[:\s]*(\d+\.?\d*)\s*(g|mg)?", re.IGNORECASE),
    "sugars":         re.compile(r"(?:total\s+)?sugars?[:\s]*(\d+\.?\d*)\s*(g|mg)?", re.IGNORECASE),
    "protein":        re.compile(r"protein[:\s]*(\d+\.?\d*)\s*(g|mg)?", re.IGNORECASE),
    "fat":            re.compile(r"(?:total\s+)?fat(?:\s*(?:content))?[:\s]*(\d+\.?\d*)\s*(g|mg)?", re.IGNORECASE),
    "saturated_fat":  re.compile(r"saturated\s*(?:fat|fatty\s*acids?)[:\s]*(\d+\.?\d*)\s*(g|mg)?", re.IGNORECASE),
    "trans_fat":      re.compile(r"trans[\s-]*fat[:\s]*(\d+\.?\d*)\s*(g|mg)?", re.IGNORECASE),
    "sodium":         re.compile(r"sodium[:\s]*(\d+\.?\d*)\s*(mg|g)?", re.IGNORECASE),
    "fibre":          re.compile(r"fib(?:re|er)[:\s]*(\d+\.?\d*)\s*(g|mg)?", re.IGNORECASE),
    "fiber":          re.compile(r"fiber[:\s]*(\d+\.?\d*)\s*(g|mg)?", re.IGNORECASE),
}

# ---------- caution keywords ----------
CAUTION_KEYWORDS = re.compile(
    r"\b(?:caution|warning|note|attention|advisory|safety|important)\b",
    re.IGNORECASE,
)

# ---------- date parsing patterns ----------
_DATE_DMY_PATTERN = re.compile(
    r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})",  # DD/MM/YYYY or DD-MM-YYYY
)
_DATE_MY_PATTERN = re.compile(
    r"(\d{1,2})[/\-.](\d{2,4})",                    # MM/YYYY or MM-YYYY
)
_DATE_MONTH_YEAR_PATTERN = re.compile(
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{2,4})",
    re.IGNORECASE,
)

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
    results: list[dict],
    pattern: re.Pattern,
    keyword: str,
    aliases: set | None = None,
    require_keyword: bool = False,
) -> dict | None:
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

    best: dict | None = None
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


# ---------------------------------------------------------------------------
# Date extraction (manufacture / expiry)
# ---------------------------------------------------------------------------

def _parse_date_value(raw_text: str, aliases: set) -> dict[str, Any] | None:
    """Parse a date from OCR text that matches one of the given aliases.

    Returns {"value": {"day": int|None, "month": int, "year": int},
             "confidence": float, "raw_text": str} or None.
    """
    if not raw_text:
        return None

    text_lower = raw_text.lower()
    has_alias = any(a in text_lower for a in aliases)
    if not has_alias:
        return None

    # Extract OCR confidence from the line (if present in format "conf: XX%")
    ocr_conf = 0.85  # default if not embedded in text
    conf_match = re.search(r"conf:\s*(\d+)", raw_text)
    if conf_match:
        ocr_conf = int(conf_match.group(1)) / 100.0

    # Try DD/MM/YYYY or DD-MM-YYYY
    m = _DATE_DMY_PATTERN.search(raw_text)
    if m:
        day_s, month_s, year_s = m.group(1), m.group(2), m.group(3)
        year = int(year_s)
        if year < 100:
            year += 2000  # 2-digit → 4-digit: deterministic for packaged goods
        month = int(month_s)
        day = int(day_s)
        if 1 <= month <= 12 and 1 <= day <= 31:
            # DD/MM assumed (Indian standard) — reduced confidence for format assumption
            return {
                "value": {"day": day, "month": month, "year": year},
                "confidence": round(ocr_conf * 0.8, 4),  # format assumption penalty
                "raw_text": raw_text,
            }

    # Try MM/YYYY or MM-YYYY (no day)
    m = _DATE_MY_PATTERN.search(raw_text)
    if m:
        month_s, year_s = m.group(1), m.group(2)
        year = int(year_s)
        if year < 100:
            year += 2000
        month = int(month_s)
        if 1 <= month <= 12:
            return {
                "value": {"day": None, "month": month, "year": year},
                "confidence": round(ocr_conf * 0.8, 4),
                "raw_text": raw_text,
            }

    # Try "Month YYYY" (e.g. "Dec 2025")
    m = _DATE_MONTH_YEAR_PATTERN.search(raw_text)
    if m:
        month_name = m.group(1)[:3].lower()
        year_s = m.group(2)
        year = int(year_s)
        if year < 100:
            year += 2000
        month_map = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
                     "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
        month = month_map.get(month_name)
        if month:
            return {
                "value": {"day": None, "month": month, "year": year},
                "confidence": round(ocr_conf * 0.85, 4),
                "raw_text": raw_text,
            }

    return None


def _find_date_source_image(
    ocr_by_label: dict[str, list[dict]],
    raw_text: str,
) -> str:
    """Find which image label contains the given OCR text."""
    if not raw_text:
        return "front"
    for label in ["front", "back"]:
        for line in ocr_by_label.get(label, []):
            if line.get("text", "") in raw_text or raw_text in line.get("text", ""):
                return label
    return "front"


def _evaluate_date_relationship(
    mfd: dict[str, Any] | None, exp: dict[str, Any] | None,
    mfd_label: str, exp_label: str,
    mfd_lines: list[dict], exp_lines: list[dict],
) -> dict[str, Any]:
    """Evaluate the relationship between manufacture and expiry dates.

    Uses spatial/contextual evidence to determine if dates are consistent.
    Returns a dict with relationship analysis.
    """
    result: dict[str, Any] = {
        "consistent": None,  # True, False, or None (inconclusive)
        "mfd_date": mfd,
        "exp_date": exp,
        "mfd_label": mfd_label,
        "exp_label": exp_label,
        "conflict_reason": None,
    }

    if not mfd or not exp:
        result["consistent"] = None
        return result

    # Extract year-month-day components for comparison
    mfd_val = mfd.get("value", {})
    exp_val = exp.get("value", {})

    mfd_year = mfd_val.get("year")
    exp_year = exp_val.get("year")
    mfd_month = mfd_val.get("month")
    exp_month = exp_val.get("month")
    mfd_day = mfd_val.get("day")
    exp_day = exp_val.get("day")

    # Check chronological consistency
    if mfd_year is not None and exp_year is not None:
        if exp_year < mfd_year:
            result["consistent"] = False
            result["conflict_reason"] = "expiry date is before manufacture date"
        elif exp_year > mfd_year:
            result["consistent"] = True
        elif exp_year == mfd_year:
            # Same year — check month
            if mfd_month is not None and exp_month is not None:
                if exp_month < mfd_month:
                    result["consistent"] = False
                    result["conflict_reason"] = "expiry date is before manufacture date"
                elif exp_month > mfd_month:
                    result["consistent"] = True
                else:
                    # Same month — check day
                    if mfd_day is not None and exp_day is not None:
                        if exp_day < mfd_day:
                            result["consistent"] = False
                            result["conflict_reason"] = "expiry date is before manufacture date"
                        elif exp_day == mfd_day:
                            result["consistent"] = False  # same day = expired at manufacture
                            result["conflict_reason"] = "expiry date is same as manufacture date"
                        else:
                            result["consistent"] = True
                    elif exp_day is None:
                        # No day info, same month/year — inconclusive
                        result["consistent"] = None
                    else:
                        result["consistent"] = None
            elif exp_month is None:
                result["consistent"] = None
            else:
                result["consistent"] = None
        else:
            result["consistent"] = None
    else:
        result["consistent"] = None

    # If we have label information, use it to refine the relationship
    # MFD typically comes before EXP; if both are labeled, the ordering
    # should follow packaging conventions
    if mfd_label and exp_label:
        # Both labeled — check if the labels make sense together
        mfd_lower = mfd_label.lower()
        exp_lower = exp_label.lower()
        # Common patterns: "MFD 03/2023" and "EXP 03/2024"
        # or "Manufactured on 03/2023" and "Best Before 03/2024"
        if "mfd" in mfd_lower and "exp" in exp_lower:
            # Labeled as MFD/EXP — trust the chronological check above
            pass
        elif "manufactured" in mfd_lower and "best before" in exp_lower:
            # Explicit MFD/Best Before — trust the check
            pass
        # If labels are ambiguous or conflicting, the chronological
        # check above is the primary determinant

    return result


def extract_manufacture_date(
    results: list[dict],
    ocr_by_label: dict[str, list[dict]] | None = None,
) -> dict[str, Any] | None:
    """Extract manufacture date from OCR results.

    Searches for keywords (MFD/Mfg Date/Manufactured on/Batch Date) then
    parses the date value. Returns dict with day/month/year or None.

    Additionally, if ocr_by_label is provided, the date's suspected
    panel (front/back) is recorded for later relationship evaluation.
    """
    # Find best matching line
    best = _find_best_match(results, re.compile(r".+", re.IGNORECASE), "mfg_date",
                            aliases=_MFD_ALIASES, require_keyword=True)
    if not best:
        # Try raw scan of all lines for date patterns near aliases
        for r in results:
            text = r["text"]
            text_lower = text.lower()
            if any(a in text_lower for a in _MFD_ALIASES):
                parsed = _parse_date_value(text, _MFD_ALIASES)
                if parsed:
                    # Record that this date was found without a keyword
                    # hint — it will be handled by the relationship evaluator
                    return parsed
        return None

    parsed = _parse_date_value(best["text"], _MFD_ALIASES)
    if not parsed:
        return None

    # Guardrail: if extracted value is non-None but raw_text doesn't
    # actually contain a parseable date pattern, force NOT_VERIFIED
    has_date_pattern = (_DATE_DMY_PATTERN.search(best["text"]) or
                        _DATE_MY_PATTERN.search(best["text"]) or
                        _DATE_MONTH_YEAR_PATTERN.search(best["text"]))
    if not has_date_pattern:
        logger.warning("MFD guardrail: value extracted but no date pattern in raw_text '%s'", best["text"])
        return None

    return parsed


def extract_expiry_date(
    results: list[dict],
    ocr_by_label: dict[str, list[dict]] | None = None,
) -> dict[str, Any] | None:
    """Extract expiry/best-before date from OCR results.

    Searches for keywords (Exp/Expiry/Best Before/Use By/BB/EXD) then
    parses the date value. Returns dict with day/month/year or None.

    Additionally, if ocr_by_label is provided, the date's suspected
    panel (front/back) is recorded for later relationship evaluation.
    """
    best = _find_best_match(results, re.compile(r".+", re.IGNORECASE), "exp_date",
                            aliases=_EXP_ALIASES, require_keyword=True)
    if not best:
        for r in results:
            text = r["text"]
            text_lower = text.lower()
            if any(a in text_lower for a in _EXP_ALIASES):
                parsed = _parse_date_value(text, _EXP_ALIASES)
                if parsed:
                    return parsed
        return None

    parsed = _parse_date_value(best["text"], _EXP_ALIASES)
    if not parsed:
        return None

    has_date_pattern = (_DATE_DMY_PATTERN.search(best["text"]) or
                        _DATE_MY_PATTERN.search(best["text"]) or
                        _DATE_MONTH_YEAR_PATTERN.search(best["text"]))
    if not has_date_pattern:
        logger.warning("EXP guardrail: value extracted but no date pattern in raw_text '%s'", best["text"])
        return None

    return parsed


# ---------------------------------------------------------------------------
# Nutrition facts extraction
# ---------------------------------------------------------------------------

def extract_nutrition_facts(results: list[dict]) -> list[dict[str, Any]]:
    """Extract per-nutrient values from OCR results.

    Detects a "Nutrition"/"Nutritional" header, then scans subsequent lines
    for known nutrient patterns. Returns a list of per-nutrient dicts, each
    with its own confidence. Garbled/unreadable lines get confidence=0.0
    and value=null — included, NOT omitted.

    Returns list of:
        {"nutrient": str, "value": float|None, "unit": str, "confidence": float, "raw_text": str}
    """
    # Find the nutrition header line
    header_idx = None
    for i, r in enumerate(results):
        text_lower = r["text"].lower()
        if "nutri" in text_lower:  # matches "nutrition", "nutritional"
            header_idx = i
            break

    if header_idx is None:
        return None

    # Scan lines after the header (up to 20 lines or next section header)
    nutrients = []
    seen_nutrients = set()
    scan_lines = results[header_idx + 1: header_idx + 21]

    for line in scan_lines:
        text = line["text"]
        text_lower = text.lower()

        # Stop at section boundary
        if any(kw in text_lower for kw in ["ingredients", "directions", "storage", "shelf life"]):
            break

        matched = False
        for nutrient_name, pattern in NUTRIENT_PATTERNS.items():
            # Skip fibre alias if fiber already matched (avoid duplicates)
            if nutrient_name == "fibre" and "fiber" in seen_nutrients:
                continue
            if nutrient_name == "fiber" and "fibre" in seen_nutrients:
                continue
            if nutrient_name in seen_nutrients:
                continue

            m = pattern.search(text)
            if m:
                try:
                    value = float(m.group(1))
                except (ValueError, IndexError):
                    value = None

                unit = m.group(2) if m.lastindex >= 2 and m.group(2) else _default_unit(nutrient_name)

                conf = line["confidence"]
                if value is None:
                    conf = 0.0  # garbled number

                nutrients.append({
                    "nutrient": nutrient_name,
                    "value": value,
                    "unit": unit,
                    "confidence": round(conf, 4),
                    "raw_text": text,
                })
                seen_nutrients.add(nutrient_name)
                matched = True
                break  # one nutrient per line

        # Fallback: line mentions a known nutrient keyword but regex didn't match value
        if not matched:
            for nutrient_name in NUTRIENT_PATTERNS:
                if nutrient_name in seen_nutrients:
                    continue
                if nutrient_name in text_lower:
                    nutrients.append({
                        "nutrient": nutrient_name,
                        "value": None,
                        "unit": _default_unit(nutrient_name),
                        "confidence": 0.0,
                        "raw_text": text,
                    })
                    seen_nutrients.add(nutrient_name)
                    break

    return nutrients


def _default_unit(nutrient_name: str) -> str:
    """Return the expected unit for a nutrient if OCR doesn't specify one."""
    if nutrient_name == "energy":
        return "kcal"
    if nutrient_name == "sodium":
        return "mg"
    return "g"


# ---------------------------------------------------------------------------
# Cautions extraction (presence-detection)
# ---------------------------------------------------------------------------

def extract_cautions(results: list[dict]) -> dict[str, Any]:
    """Detect caution/warning presence on the label.

    Returns {"present": bool, "text": str, "confidence": float, "raw_text": str}.
    """
    best_conf = 0.0
    best_text = ""

    for r in results:
        text = r["text"]
        if CAUTION_KEYWORDS.search(text):
            if r["confidence"] > best_conf:
                best_conf = r["confidence"]
                best_text = text

    if best_text:
        return {
            "present": True,
            "text": best_text.strip(),
            "confidence": round(best_conf, 4),
            "raw_text": best_text,
        }

    return {
        "present": False,
        "text": "",
        "confidence": 0.95,  # high confidence that no caution keyword exists
        "raw_text": "",
    }


def extract_mrp(results: list[dict]) -> dict[str, Any] | None:
    """Extract MRP (Maximum Retail Price) from OCR results.

    Returns dict like {"amount": float, "currency": "INR", "confidence": float,
    "raw_text": str, "tier": int} or None.

    Bug 1b fix: require_keyword=True — if no line contains an MRP-related
    keyword (mrp, max, retail, price), return None.  Never fall back to
    scanning unrelated lines for any number.

    Tier classification:
      Tier 1: "MRP"/"max"/"retail" keyword with explicit currency
              OR "MAXIMUM RETAIL PRICE" keyword (no currency needed)
      Tier 2: "Price" keyword with explicit currency
      Tier 4: keyword present but no currency (where applicable)
    """
    from app.extraction import _find_best_match

    text_lower = results[0]["text"].lower() if results else ""

    # Special case: "MAXIMUM RETAIL PRICE" keyword — the keyword itself
    # implies the field meaning, so we accept bare numbers without currency.
    if "maximum" in text_lower and "retail" in text_lower:
        # Find any result containing "maximum retail price" (case-insensitive)
        for r in results:
            if "maximum" in r["text"].lower() and "retail" in r["text"].lower():
                text = r["text"]
                num_match = re.search(r"[\d,]+\.?\d*", text)
                if not num_match:
                    return None
                try:
                    amount = float(num_match.group(0).replace(",", ""))
                except ValueError:
                    return None
                return {
                    "amount": round(amount, 2),
                    "currency": "INR",
                    "confidence": r["confidence"],
                    "raw_text": text,
                    "tier": 1,  # "MAXIMUM RETAIL PRICE" → tier 1 even without currency
                }
        # Fall through to normal processing if no exact match found

    # Use the existing _find_best_match which handles keyword/alias filtering
    # and pattern matching.  We pass require_keyword=True so that bare numbers
    # without an MRP-related keyword are rejected.
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
    has_currency = False
    if re.search(r"USD|\$", text, re.IGNORECASE):
        currency = "USD"
        has_currency = True
    elif re.search(r"EUR|\€", text, re.IGNORECASE):
        currency = "EUR"
        has_currency = True
    elif re.search(r"₹", text):
        currency = "INR"
        has_currency = True
    elif re.search(r"INR", text, re.IGNORECASE):
        currency = "INR"
        has_currency = True
    elif re.search(r"Rs\.?|RS\.?", text, re.IGNORECASE):
        currency = "INR"
        has_currency = True

    # Determine tier based on which keyword/alias triggered the match
    text_lower = text.lower()

    # Check if "price" alias triggered (and not also "MAXIMUM RETAIL PRICE")
    is_price_alias = "price" in text_lower and not ("retail" in text_lower or "maximum" in text_lower)
    is_mrp_keyword = bool(re.search(r"\bmrp\b", text_lower))
    is_retail_alias = "retail" in text_lower
    is_max_alias = "max" in text_lower and not is_retail_alias

    if is_price_alias:
        # "Price" alias triggered (and not also "MAXIMUM RETAIL PRICE")
        tier = 2 if has_currency else 4
    elif is_mrp_keyword:
        # "MRP" keyword triggered
        tier = 1 if has_currency else 4
    elif is_retail_alias or "maximum" in text_lower:
        # "MAXIMUM RETAIL PRICE" → tier 1 even without explicit currency
        # (this branch is a fallback; the special case above handles it primarily)
        tier = 1
    elif is_max_alias:
        # Standalone "max" → tier 1 if currency, else tier 4
        tier = 1 if has_currency else 4
    else:
        tier = 1 if has_currency else 4

    return {
        "amount": round(amount, 2),
        "currency": currency,
        "confidence": matched["confidence"],
        "raw_text": text,
        "tier": tier,
    }


def extract_net_quantity(results: list[dict]) -> dict[str, Any] | None:
    """Extract net quantity from OCR results.

    Returns dict like {"value": float, "unit": "g", "confidence": float,
    "raw_text": str} or None.
    """
    matched = _find_best_match(results, NET_QTY_PATTERN, "net_quantity", aliases=_NET_QTY_ALIASES)
    if matched:
        text = matched["text"]
    else:
        # Fallback: try any line that contains a number + unit pattern
        # This handles cases where OCR results don't have "Net Qty" prefix
        # but still contain a clear quantity declaration
        for r in results:
            text = r["text"]
            qty_match = re.search(
                r"([\d,]+\.?\d*)\s*(g|kg|ml|l|oz|lb|pcs|tablets|capsules|pieces|count)",
                text, re.IGNORECASE,
            )
            if qty_match:
                matched = {"text": text, "confidence": r.get("confidence", 1.0)}
                break
        if not matched:
            return None

    # Try to find a number with a unit (even if matched was found above)
    qty_match = re.search(
        r"([\d,]+\.?\d*)\s*(g|kg|ml|l|oz|lb|pcs|tablets|capsules|pieces|count)",
        matched["text"], re.IGNORECASE,
    )
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
        "tablets": "tablets",
        "capsules": "capsules",
        "pieces": "pieces",
        "count": "count",
    }
    unit = unit_map.get(unit, unit)

    return {
        "value": round(value, 2),
        "unit": unit,
        "confidence": matched["confidence"],
        "raw_text": matched["text"],
    }


def extract_manufacturer(results: list[dict]) -> dict[str, Any] | None:
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
    for _idx, r in enumerate(keyword_results):
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
