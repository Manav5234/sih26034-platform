"""Physical scale estimation with explicit, auditable barcode provenance.

Pixels are not physical units.  This module only returns a pixels-per-mm
factor when a decoded EAN-13 or UPC-A symbol has a usable bounding box.  The
calculation uses the GS1 nominal (100 %) X-dimension of 0.330 mm and the 95
modules in the encoded bar pattern.  All other inputs produce NOT_VERIFIED.

The nominal-symbol assumption is preserved in every result so an officer can
see exactly why a millimetre estimate was, or was not, made.
"""
from __future__ import annotations

from typing import Any

import numpy as np


NOT_VERIFIED = "NOT_VERIFIED"
ESTABLISHED = "ESTABLISHED"

# GS1 General Specifications, EAN-13 / UPC-A nominal dimensions:
# 95 encoded modules at X-dimension 0.330 mm = 31.35 mm bar pattern width.
_LINEAR_FORMATS = {"EAN13", "EAN-13", "UPCA", "UPC-A"}
_MODULES_WIDE = 95
_NOMINAL_X_DIMENSION_MM = 0.330
_NOMINAL_SYMBOL_WIDTH_MM = _MODULES_WIDE * _NOMINAL_X_DIMENSION_MM


def not_verified(reason: str) -> dict[str, Any]:
    """Return the single safe failure shape; it intentionally has no scale."""
    return {
        "status": NOT_VERIFIED,
        "pixels_per_mm": None,
        "reason": reason,
        "method": "barcode_module_geometry",
        "millimetre_values_available": False,
    }


def estimate_barcode_scale(
    image: np.ndarray | None,
    barcode_bbox: dict[str, Any] | None,
    barcode_format: str | None,
) -> dict[str, Any]:
    """Estimate pixels/mm from a decoded, nominal-size EAN-13 or UPC-A symbol.

    ``barcode_bbox`` must be the decoded symbol's axis-aligned bounding box
    from :mod:`app.barcode`.  The wider dimension is accepted as the bar
    direction only for clearly linear symbols.  This deliberately rejects
    unknown, square, tiny, or malformed candidates instead of guessing.
    """
    if image is None or not isinstance(image, np.ndarray) or image.size == 0:
        return not_verified("image is unavailable for barcode scale estimation")

    fmt = (barcode_format or "").upper().replace("_", "").replace(" ", "")
    if fmt not in _LINEAR_FORMATS:
        return not_verified(
            f"barcode format {barcode_format!r} has no configured physical module geometry"
        )
    if not isinstance(barcode_bbox, dict):
        return not_verified("decoded barcode has no bounding box")

    try:
        width_px = float(barcode_bbox["width"])
        height_px = float(barcode_bbox["height"])
    except (KeyError, TypeError, ValueError):
        return not_verified("decoded barcode bounding box is malformed")

    if width_px <= 0 or height_px <= 0:
        return not_verified("decoded barcode bounding box has non-positive dimensions")

    long_axis_px = max(width_px, height_px)
    short_axis_px = min(width_px, height_px)
    if long_axis_px < 95 or long_axis_px / short_axis_px < 1.5:
        return not_verified("decoded barcode bounding box is not a usable linear symbol")

    pixels_per_mm = long_axis_px / _NOMINAL_SYMBOL_WIDTH_MM
    return {
        "status": ESTABLISHED,
        "pixels_per_mm": round(pixels_per_mm, 6),
        "reason": "decoded linear barcode matched configured GS1 nominal module geometry",
        "method": "barcode_module_geometry",
        "millimetre_values_available": True,
        "reference": {
            "barcode_format": fmt,
            "bbox_long_axis_px": round(long_axis_px, 3),
            "encoded_modules": _MODULES_WIDE,
            "nominal_x_dimension_mm": _NOMINAL_X_DIMENSION_MM,
            "nominal_symbol_width_mm": _NOMINAL_SYMBOL_WIDTH_MM,
            "standard": "GS1 General Specifications, EAN-13/UPC-A nominal 100% magnification",
        },
        "derivation": (
            f"pixels_per_mm = {long_axis_px:.3f} px / "
            f"({_MODULES_WIDE} modules × {_NOMINAL_X_DIMENSION_MM:.3f} mm)"
        ),
        "limitations": (
            "Uses GS1 nominal 100% symbol geometry; do not use if the printed "
            "symbol's magnification is unknown or visibly distorted. Officer review is required."
        ),
        "officer_review_required": True,
    }


def convert_font_height_to_mm(
    font_height_px: float | int | None,
    scale: dict[str, Any] | None,
) -> dict[str, Any]:
    """Convert a measured pixel glyph height only when the scale is established."""
    if not isinstance(scale, dict) or scale.get("status") != ESTABLISHED:
        return not_verified("physical scale could not be established")
    try:
        height_px = float(font_height_px)
        pixels_per_mm = float(scale["pixels_per_mm"])
    except (KeyError, TypeError, ValueError):
        return not_verified("font pixel height or scale factor is unavailable")
    if height_px <= 0 or pixels_per_mm <= 0:
        return not_verified("font pixel height or scale factor is invalid")

    height_mm = height_px / pixels_per_mm
    return {
        "status": ESTABLISHED,
        "font_height_px": round(height_px, 3),
        "font_height_mm": round(height_mm, 4),
        "pixels_per_mm": pixels_per_mm,
        "derivation": f"font_height_mm = {height_px:.3f} px / {pixels_per_mm:.6f} px/mm",
        "scale_reference": scale.get("reference"),
        "officer_review_required": True,
    }
