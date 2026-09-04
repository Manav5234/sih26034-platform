"""Evidence fusion: merge OCR + provider-lookup evidence per field.

Per-field merge algorithm:
  1. Single source with a value → passthrough, fused_confidence = source confidence
  2. Multiple agreeing sources → higher-confidence value, fused_confidence = max (capped at 1.0)
  3. Multiple disagreeing sources → CONFLICT, fused_value = null, both values preserved
  4. No sources with a value → missing, fused_value = null, fused_confidence = 0

Unit normalization for net_quantity and mrp ensures "500g" vs "0.5kg" don't
false-conflict.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Tolerance for numeric comparison (±1% covers price rounding differences)
_NUMERIC_TOLERANCE = 0.01

# Unit conversion factors (to base unit)
_NQ_UNITS_TO_GRAMS = {
    "g": 1.0,
    "kg": 1000.0,
    "mg": 0.001,
    "oz": 28.3495,
    "lb": 453.592,
}
_NQ_UNITS_TO_ML = {
    "ml": 1.0,
    "l": 1000.0,
    "cl": 10.0,
}


def _normalize_net_quantity(value: float, unit: str) -> float:
    """Convert net_quantity to grams (or ml for liquids) for comparison.

    Returns the value in the canonical unit.  We assume grams for solids
    and milliliters for liquids — a simplification that covers the vast
    majority of FMCG products.
    """
    unit_lower = unit.lower()
    if unit_lower in _NQ_UNITS_TO_GRAMS:
        return value * _NQ_UNITS_TO_GRAMS[unit_lower]
    if unit_lower in _NQ_UNITS_TO_ML:
        return value * _NQ_UNITS_TO_ML[unit_lower]
    # Unknown unit — return as-is, comparison will likely disagree
    return value


def _normalize_mrp(value: float, currency: str) -> float:
    """Normalize MRP to INR for comparison.

    This is a stub — real conversion would use live exchange rates.
    For now, assume all test data is INR.
    """
    # Stub: assume INR.  Later, multiply by exchange rate if currency != "INR".
    return value


def _values_match(a: Any, b: Any, field_name: str) -> bool:
    """Check if two extracted values for the same field are semantically equal."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False

    if field_name == "net_quantity":
        a_val = a.get("value", 0) if isinstance(a, dict) else 0
        a_unit = a.get("unit", "g") if isinstance(a, dict) else "g"
        b_val = b.get("value", 0) if isinstance(b, dict) else 0
        b_unit = b.get("unit", "g") if isinstance(b, dict) else "g"
        norm_a = _normalize_net_quantity(a_val, a_unit)
        norm_b = _normalize_net_quantity(b_val, b_unit)
        if norm_a == 0 and norm_b == 0:
            return True
        if norm_a == 0 or norm_b == 0:
            return False
        return abs(norm_a - norm_b) / max(norm_a, norm_b) <= _NUMERIC_TOLERANCE

    if field_name == "mrp":
        a_amount = a.get("amount", 0) if isinstance(a, dict) else 0
        a_curr = a.get("currency", "INR") if isinstance(a, dict) else "INR"
        b_amount = b.get("amount", 0) if isinstance(b, dict) else 0
        b_curr = b.get("currency", "INR") if isinstance(b, dict) else "INR"
        norm_a = _normalize_mrp(a_amount, a_curr)
        norm_b = _normalize_mrp(b_amount, b_curr)
        if norm_a == 0 and norm_b == 0:
            return True
        if norm_a == 0 or norm_b == 0:
            return False
        return abs(norm_a - norm_b) / max(norm_a, norm_b) <= _NUMERIC_TOLERANCE

    if field_name == "manufacturer":
        # String comparison — case-insensitive, strip whitespace
        return str(a).strip().lower() == str(b).strip().lower()

    # Fallback: exact equality
    return a == b


@dataclass
class FusionResult:
    """Result of fusing multiple evidence sources for a single field."""
    field_name: str
    fused_value: Any = None
    fused_confidence: float = 0.0
    status: str = "missing"  # "agreed" | "conflict" | "missing"
    sources: List[Dict] = field(default_factory=list)
    conflict_values: List[Any] = field(default_factory=list)


def fuse_field(
    field_name: str,
    ocr_value: Any,
    ocr_confidence: float,
    provider_value: Any = None,
    provider_confidence: float = 1.0,
) -> FusionResult:
    """Fuse OCR evidence + provider-lookup evidence for a single field.

    Returns a FusionResult with the fused value, confidence, status,
    and all source values for the evidence trail.
    """
    sources: List[Dict] = []
    conflict_values: List[Any] = []

    has_ocr = ocr_value is not None
    has_provider = provider_value is not None

    if has_ocr:
        sources.append({"source": "ocr", "value": ocr_value, "confidence": ocr_confidence})
    if has_provider:
        sources.append({"source": "provider_lookup", "value": provider_value, "confidence": provider_confidence})

    # Case 4: No sources
    if not has_ocr and not has_provider:
        return FusionResult(
            field_name=field_name,
            fused_value=None,
            fused_confidence=0.0,
            status="missing",
            sources=sources,
        )

    # Case 1: Single source
    if len(sources) == 1:
        src = sources[0]
        return FusionResult(
            field_name=field_name,
            fused_value=src["value"],
            fused_confidence=src["confidence"],
            status="agreed",
            sources=sources,
        )

    # Case 2/3: Multiple sources — compare
    if _values_match(ocr_value, provider_value, field_name):
        # Agreement: take higher-confidence value, combined confidence = max
        if ocr_confidence >= provider_confidence:
            fused_value = ocr_value
        else:
            fused_value = provider_value
        fused_confidence = min(max(ocr_confidence, provider_confidence), 1.0)
        return FusionResult(
            field_name=field_name,
            fused_value=fused_value,
            fused_confidence=fused_confidence,
            status="agreed",
            sources=sources,
        )
    else:
        # Disagreement: CONFLICT
        conflict_values = [ocr_value, provider_value]
        return FusionResult(
            field_name=field_name,
            fused_value=None,
            fused_confidence=0.0,
            status="conflict",
            sources=sources,
            conflict_values=conflict_values,
        )
