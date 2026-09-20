import numpy as np

from app.scale_estimation import (
    ESTABLISHED,
    NOT_VERIFIED,
    convert_font_height_to_mm,
    estimate_barcode_scale,
)
from app.db.models import VerificationState
from app.rule_engine import evaluate_font_size_condition


def _barcode_image() -> np.ndarray:
    """A synthetic high-contrast, 95-module-wide linear barcode image."""
    image = np.full((180, 500, 3), 255, dtype=np.uint8)
    for module in range(95):
        if module % 3 != 1:
            image[30:150, 60 + module * 4 : 60 + (module + 1) * 4] = 0
    return image


def test_ean13_barcode_establishes_auditable_nominal_scale():
    image = _barcode_image()
    result = estimate_barcode_scale(
        image,
        {"x": 60, "y": 30, "width": 380, "height": 120},
        "EAN13",
    )

    assert result["status"] == ESTABLISHED
    assert result["pixels_per_mm"] == round(380 / 31.35, 6)
    assert result["reference"]["encoded_modules"] == 95
    assert result["reference"]["nominal_x_dimension_mm"] == 0.330
    assert "pixels_per_mm" in result["derivation"]

    font = convert_font_height_to_mm(24, result)
    assert font["status"] == ESTABLISHED
    assert 1.9 < font["font_height_mm"] < 2.1
    assert "font_height_mm" in font["derivation"]


def test_missing_or_unusable_barcode_never_invents_a_scale():
    image = np.full((180, 500, 3), 255, dtype=np.uint8)
    result = estimate_barcode_scale(image, None, None)

    assert result["status"] == NOT_VERIFIED
    assert result["pixels_per_mm"] is None
    assert result["millimetre_values_available"] is False

    font = convert_font_height_to_mm(24, result)
    assert font["status"] == NOT_VERIFIED
    assert font["pixels_per_mm"] is None


def test_font_rule_is_not_verified_without_a_provenance_bearing_scale():
    verdict, reason = evaluate_font_size_condition(
        {"font_height_px": 24},
        {"status": NOT_VERIFIED, "pixels_per_mm": None},
        {"min_font_size_mm": 1.0},
    )

    assert verdict == VerificationState.NOT_VERIFIED
    assert "not verified" in reason.lower()
