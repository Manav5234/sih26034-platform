"""OCR Error Normalization — context-dependent character substitution.

Handles common OCR confusions such as:
  ₹ → €, O ↔ 0, I ↔ 1, l ↔ 1, S ↔ 5, B ↔ 8

But NEVER globally replaces characters.
Normalization depends on context — the same character may be substituted
differently based on surrounding text, field context, and evidence tier.

The output preserves the original OCR text and generates candidate versions
for the field-level fusion layer to resolve.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Normalization substitution rules (ordered by likelihood)
# ---------------------------------------------------------------------------

# These substitutions are context-dependent, not global.
# Each rule has a "context hint" that determines when it should apply.

SUBSTITUTION_RULES = [
    # ₹ (Indian Rupee) can be misread as € (Euro), especially in
    # blurry or low-quality OCR.  But in an Indian packaging context,
    # ₹ should be preserved.
    {
        "from": "₹",
        "to": "€",
        "context_hints": ["european_context", "foreign_currency"],
        "reverse_hints": ["indian_context", "rupee_currency"],
    },
    # OCR often reads € as ₹ and vice versa.  The reverse rule is
    # implicitly handled by the substitution symmetry.
    # O ↔ 0 (zero) — OCR confusion between letter O and digit 0
    {
        "from": "O",
        "to": "0",
        "context_hints": ["digit_position", "numeric_field", "sequence_of_digits"],
        "reverse_hints": ["letter_position", "alphabetic_field"],
    },
    # 0 → O (zero to letter O) — same rule, reverse direction
    {
        "from": "0",
        "to": "O",
        "context_hints": ["letter_position", "alphabetic_field"],
        "reverse_hints": ["digit_position", "numeric_field"],
    },
    # I ↔ 1 (capital i / eye confusion with digit one)
    {
        "from": "I",
        "to": "1",
        "context_hints": ["digit_position", "numeric_field", "year_pattern"],
        "reverse_hints": ["letter_position", "alphabetic_field"],
    },
    # 1 → I (digit one to capital i)
    {
        "from": "1",
        "to": "I",
        "context_hints": ["letter_position", "alphabetic_field", "company_name"],
        "reverse_hints": ["digit_position", "numeric_field", "year_pattern"],
    },
    # S ↔ 5 (similar shape)
    {
        "from": "S",
        "to": "5",
        "context_hints": ["digit_position", "numeric_field", "percentage_pattern"],
        "reverse_hints": ["letter_position", "alphabetic_field"],
    },
    # 5 → S (digit five to letter S)
    {
        "from": "5",
        "to": "S",
        "context_hints": ["letter_position", "alphabetic_field"],
        "reverse_hints": ["digit_position", "numeric_field"],
    },
    # B ↔ 8 (similar shape)
    {
        "from": "B",
        "to": "8",
        "context_hints": ["digit_position", "numeric_field"],
        "reverse_hints": ["letter_position", "alphabetic_field"],
    },
    # 8 → B (digit eight to letter B)
    {
        "from": "8",
        "to": "B",
        "context_hints": ["letter_position", "alphabetic_field"],
        "reverse_hints": ["digit_position", "numeric_field"],
    },
]


# ---------------------------------------------------------------------------
# OCR normalisation candidate
# ---------------------------------------------------------------------------

@dataclass
class OCROErrorNormalization:
    """Result of normalizing a single OCR text string.

    Attributes:
        original_text: The original OCR text (never modified).
        normalized_variants: List of (text, confidence_penalty) tuples,
            where text is the variant after substitutions and
            confidence_penalty is how much to reduce confidence (0.0 = no
            penalty, 1.0 = fully penalized).
        context_hints: Free-text hints about the contextual clues used
            for the normalization decisions.
    """
    original_text: str
    normalized_variants: list[tuple[str, float]] = field(default_factory=list)
    context_hints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "original_text": self.original_text,
            "normalized_variants": self.normalized_variants,
            "context_hints": self.context_hints,
        }


# ---------------------------------------------------------------------------
# Context-dependent normalization engine
# -------------------------------------------------------------------------__


def normalize_ocr_text(
    text: str,
    field_context: str = "general",
    evidence_tier: int = 4,
) -> OCROErrorNormalization:
    """Normalize OCR text with context-dependent character substitutions.

    Key principles:
    1. Never globally replace characters — only substitute when context
       strongly suggests the substitution is correct.
    2. Generate multiple variants when ambiguity exists.
    3. Preserve the original OCR text — it's the primary evidence.
    4. Apply substitutions that are justified by the field context and
       evidence tier.

    Args:
        text: The original OCR text to normalize.
        field_context: The expected field type ("mrp", "net_quantity",
            "manufacturer", "date", etc.).
        evidence_tier: The MRP evidence tier from Phase 6 (1-4). Lower tiers
            have more conservative normalization (fewer substitutions).

    Returns:
        OCROErrorNormalization containing the original text, normalized
        variants with confidence penalties, and context hints.
    """
    original = text.strip()
    variants: list[tuple[str, float]] = [(original, 0.0)]  # (variant_text, confidence_penalty)
    hints: list[str] = []

    # Determine substitution conservatism based on evidence tier
    # Tier 1-2: conservative (fewer substitutions, higher confidence)
    # Tier 3-4: more aggressive (more substitutions, lower confidence)
    conservative = evidence_tier <= 2

    # Build a set of substitutions to consider based on context
    applicable_rules = []

    for rule in SUBSTITUTION_RULES:
        # Check if the rule's context hints are compatible with the
        # current field context and evidence tier
        rule_applies = False

        for hint in rule["context_hints"]:
            # Map hints to field context evaluation
            if hint == "digit_position" and _is_in_numeric_position(text, field_context):
                rule_applies = True
                break
            elif hint == "letter_position" and _is_in_text_position(text, field_context):
                rule_applies = True
                break
            elif hint == "numeric_field" and _is_likely_numeric_field(text, field_context):
                rule_applies = True
                break
            elif hint == "alphabetic_field" and _is_likely_alphabetic_field(text, field_context):
                rule_applies = True
                break
            elif hint == "digit_sequence" and _has_digit_sequence(text):
                rule_applies = True
                break
            elif hint == "european_context" and _has_european_context(text):
                rule_applies = True
                break
            elif hint == "indian_context" and _has_indian_context(text):
                rule_applies = True
                break
            elif hint == "foreign_currency" and _has_foreign_currency(text):
                rule_applies = True
                break
            elif hint == "rupee_currency" and _has_rupee_currency(text):
                rule_applies = True
                break

        # If the rule was already added via another hint, skip
        if any(r is rule for r in applicable_rules):
            continue

        if rule_applies:
            applicable_rules.append(rule)

    # Apply substitutions, being more conservative if evidence tier is low
    for rule in applicable_rules:
        subs_from = rule["from"]
        subs_to = rule["to"]

        # Determine if we should apply this substitution
        should_substitute = _should_substitute(
            rule, original, field_context, conservative
        )

        if should_substitute:
            # Generate the substituted text
            new_text = original.replace(subs_from, subs_to, 1)  # replace only first occurrence
            if new_text != original:
                # Determine confidence penalty based on evidence tier
                if conservative:
                    penalty = 0.3  # conservative: small penalty for tier 1-2
                else:
                    penalty = 0.5  # aggressive: larger penalty for tier 3-4

                # Only add if not already in the variants list
                if not any(v[0] == new_text for v in variants):
                    variants.append((new_text, penalty))
                    # Record the substitution hint
                    hint_key = f"{subs_from}→{subs_to}"
                    if hint_key not in hints:
                        hints.append(hint_key)

    # Sort variants by confidence penalty (lower penalty first)
    variants.sort(key=lambda v: v[1])

    # Remove duplicate text variants, keeping the one with lowest penalty
    seen = set()
    unique_variants = []
    for text, penalty in variants:
        if text not in seen:
            seen.add(text)
            unique_variants.append((text, penalty))

    return OCROErrorNormalization(
        original_text=original,
        normalized_variants=unique_variants,
        context_hints=hints,
    )


def _should_substitute(
    rule: dict[str, str],
    text: str,
    field_context: str,
    conservative: bool,
) -> bool:
    """Determine whether a substitution rule should apply to the given text."""
    subs_from = rule["from"]

    # Check if the substitution character exists in the text
    if subs_from not in text:
        return False

    # Conservative mode: only substitute in clearly numeric/digital contexts
    if conservative:
        return _is_in_numeric_position(text, field_context)

    # Aggressive mode: substitute more freely
    return _is_in_numeric_position(text, field_context) or _is_in_text_position(text, field_context)


def _is_in_numeric_position(text: str, field_context: str) -> bool:
    """Check if a character substitution would place text in a numeric context."""
    # Heuristic: if the text contains primarily digits, or the character
    # appears in a position where a digit is expected
    digits = sum(c.isdigit() for c in text)
    # If more than half the characters are digits, it's likely a numeric field
    if len(text) > 0 and digits / len(text) > 0.5:
        return True

    # Check for common numeric patterns: sequences of digits, percentages, etc.
    if re.search(r"\d+", text):
        return True

    # Field-context heuristics
    if field_context in ("mrp", "net_quantity", "date"):
        return True

    return False


def _is_in_text_position(text: str, field_context: str) -> bool:
    """Check if a character substitution would place text in an alphabetic context."""
    # If the text contains primarily letters, substitution to a letter makes sense
    letters = sum(c.isalpha() for c in text)
    if len(text) > 0 and letters / len(text) > 0.5:
        return True

    # Field-context heuristics
    if field_context in ("manufacturer", "brand", "cautions"):
        return True

    return False


def _is_likely_numeric_field(text: str, field_context: str) -> bool:
    """Check if the text is likely from a numeric field."""
    if field_context in ("mrp", "net_quantity", "date"):
        return True
    if re.search(r"\d+", text) and sum(c.isdigit() for c in text) > sum(c.isalpha() for c in text):
        return True
    return False


def _is_likely_alphabetic_field(text: str, field_context: str) -> bool:
    """Check if the text is likely from an alphabetic field."""
    if field_context in ("manufacturer", "brand", "cautions"):
        return True
    if sum(c.isalpha() for c in text) > sum(c.isdigit() for c in text) and len(text) > 2:
        return True
    return False


def _has_digit_sequence(text: str) -> bool:
    """Check if text contains a sequence of digits."""
    return bool(re.search(r"\d{2,}", text))


def _has_european_context(text: str) -> bool:
    """Check if text has European formatting cues (comma as decimal, etc.)."""
    return bool(re.search(r"[,]", text)) and not bool(re.search(r"[₹]", text))


def _has_indian_context(text: str) -> bool:
    """Check if text has Indian formatting cues (₹ symbol)."""
    return bool(re.search(r"[₹]", text))


def _has_foreign_currency(text: str) -> bool:
    """Check if text has foreign currency markers ($, €)."""
    return bool(re.search(r"[$€]", text))


def _has_rupee_currency(text: str) -> bool:
    """Check if text has rupee currency marker."""
    return bool(re.search(r"[₹]|Rs\.?|INR", text))


# ---------------------------------------------------------------------------
# Integration with extraction pipeline
# ---------------------------------------------------------------------------


def apply_ocr_normalization(
    extracted_value: dict[str, Any],
    field_name: str,
    evidence_tier: int = 4,
) -> dict[str, Any]:
    """Apply OCR error normalization to an extracted value.

    This function takes the result from an extraction function and generates
    normalized variants, preserving the original text for auditability.

    Args:
        extracted_value: The extracted value dict from an extraction function.
            Must contain "raw_text" key.
        field_name: The field name ("mrp", "net_quantity", "manufacturer", etc.).
        evidence_tier: The MRP evidence tier (1-4). Affects normalization
            conservativeness.

    Returns:
        The original extracted_value dict with an additional "normalized"
        key containing the normalization result.
    """
    raw_text = extracted_value.get("raw_text", "")

    if not raw_text:
        extracted_value["normalized"] = normalize_ocr_text(raw_text, field_name, evidence_tier)
        return extracted_value

    # Apply normalization based on field context
    field_context_map = {
        "mrp": "mrp",
        "net_quantity": "net_quantity",
        "manufacturer": "manufacturer",
        "manufacture_date": "date",
        "expiry_date": "date",
        "cautions": "cautions",
        "nutrition_facts": "general",
    }

    context = field_context_map.get(field_name, "general")

    normalization = normalize_ocr_text(raw_text, context, evidence_tier)

    result = dict(extracted_value)
    result["normalized"] = normalization.to_dict()

    return result