"""Unit tests for ImageQualityAnalyzer.

Tests that blur detection correctly classifies a deliberately blurry image
as "high" and a sharp image as "low" (or "medium").
"""

import pytest
import cv2
import numpy as np

from backend.app.image_quality import ImageQualityAnalyzer


# ---------------------------------------------------------------------------
# Helpers: create a sharp test image with fine details, then a blurred copy.
# ---------------------------------------------------------------------------

def _make_sharp_image(height: int = 600, width: int = 800) -> np.ndarray:
    """Create a sharp BGR image with fine horizontal and vertical lines.

    The pattern includes:
    - A white checkerboard (high frequency)
    - Thin black vertical lines (high frequency)
    - Thin white horizontal lines (high frequency)
    This ensures high Laplacian variance (sharp).
    """
    bgr = np.zeros((height, width, 3), dtype=np.uint8)
    # Checkerboard 8-pixel cells
    for i in range(0, height, 8):
        for j in range(0, width, 8):
            if (i // 8 + j // 8) % 2 == 0:
                bgr[i:i+8, j:j+8] = 255
    # Thin vertical lines every 8 pixels
    for x in range(0, width, 8):
        bgr[:, x] = 0 if x % 16 == 0 else 255  # alternating 0 and 255 gives 1-pixel lines
    # Thin horizontal lines every 8 pixels
    for y in range(0, height, 8):
        bgr[y, :] = 0 if y % 16 == 0 else 255
    return bgr


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestImageQualityBlur:
    """Verify Laplacian-variance blur classification."""

    @pytest.fixture
    def analyzer(self):
        return ImageQualityAnalyzer()

    def test_blurry_image_returns_high_blur(self, analyzer):
        """A heavily blurred image should be classified as 'high' blur.

        We create a sharp base image and then apply a large Gaussian kernel
        (51,51) so the Laplacian variance drops well below the high-threshold (100).
        The test asserts that the *same* base image blurred vs. sharp gives
        different blur classifications.
        """
        sharp_bgr = _make_sharp_image()

        # Heavy blur so variance becomes very low
        blurry_bgr = cv2.GaussianBlur(sharp_bgr, (51, 51), 0)

        result = analyzer.analyze(blurry_bgr)
        assert result["blur"] == "high", (
            f"Expected blur='high' for heavily blurred image, got '{result['blur']}'"
        )

    def test_sharp_image_returns_low_blur(self, analyzer):
        """A clean crisp image should be classified as 'low' blur.

        We use a sharp test image with fine checkerboard + thin lines —
        Laplacian variance should be well above the medium-threshold (200).
        """
        sharp_bgr = _make_sharp_image()

        result = analyzer.analyze(sharp_bgr)
        assert result["blur"] == "low", (
            f"Expected blur='low' for sharp image, got '{result['blur']}' "
            f"(variance info: check analyzer thresholds)"
        )


# ---------------------------------------------------------------------------
# Brightness / contrast tests
# ---------------------------------------------------------------------------

class TestImageQualityBrightness:
    """Verify brightness/contrast detection."""

    def test_dark_image(self):
        analyzer = ImageQualityAnalyzer()
        # Very dark image
        dark_bgr = np.zeros((600, 800, 3), dtype=np.uint8)
        label, detail = analyzer.detect_brightness(cv2.cvtColor(dark_bgr, cv2.COLOR_BGR2GRAY))
        assert label == "dark"

    def test_bright_image(self):
        analyzer = ImageQualityAnalyzer()
        # Very bright image
        bright_bgr = np.ones((600, 800, 3), dtype=np.uint8) * 220
        label, detail = analyzer.detect_brightness(cv2.cvtColor(bright_bgr, cv2.COLOR_BGR2GRAY))
        assert label == "bright"

    def test_normal_image(self):
        analyzer = ImageQualityAnalyzer()
        # Medium brightness
        normal_bgr = np.ones((600, 800, 3), dtype=np.uint8) * 128
        label, detail = analyzer.detect_brightness(cv2.cvtColor(normal_bgr, cv2.COLOR_BGR2GRAY))
        assert label == "normal"


# ---------------------------------------------------------------------------
# Resolution adequacy tests
# ---------------------------------------------------------------------------

class TestImageQualityResolution:
    """Verify resolution adequacy check."""

    def test_low_resolution(self):
        analyzer = ImageQualityAnalyzer()
        # Small image — short edge < 800
        result = analyzer.check_resolution((400, 600))   # short edge = 400
        assert result == "low"

    def test_adequate_resolution(self):
        analyzer = ImageQualityAnalyzer()
        # 1200x800 → short edge = 800 → adequate (>=800)
        result = analyzer.check_resolution((800, 1200))  # short edge = 800 → adequate
        assert result == "adequate"

    def test_high_resolution(self):
        analyzer = ImageQualityAnalyzer()
        result = analyzer.check_resolution((1200, 1600))  # short edge = 1200 > 800
        assert result == "adequate"