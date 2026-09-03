"""Unit tests for ImageQualityAnalyzer.

Tests that blur detection correctly classifies a deliberately blurry image
as "high" and a sharp image as "low" (or "medium").
"""

import pytest
import cv2
import numpy as np

from backend.app.image_quality import ImageQualityAnalyzer


# ---------------------------------------------------------------------------
# Blur classification tests
# ---------------------------------------------------------------------------

class TestImageQualityBlur:
    """Verify Laplacian-variance blur classification."""

    @pytest.fixture
    def analyzer(self):
        return ImageQualityAnalyzer()

    def test_blurry_image_returns_high_blur(self, analyzer):
        """A heavily blurred image should be classified as 'high' blur.

        We create a sharp base pattern and then apply a large Gaussian kernel
        so the Laplacian variance drops well below the high-threshold (100).
        """
        # Sharp base (800x600) — high variance; sparse pattern so variance is moderate
        sharp_bgr = np.zeros((600, 800, 3), dtype=np.uint8)
        sharp_bgr[::15, ::15] = 255
        sharp_bgr[7::15, 7::15] = 255

        # Apply heavy blur so variance becomes very low
        blurry_bgr = cv2.GaussianBlur(sharp_bgr, (31, 31), 0)

        result = analyzer.analyze(blurry_bgr)
        assert result["blur"] == "high", (
            f"Expected blur='high' for heavily blurred image, got '{result['blur']}'"
        )

    def test_sharp_image_returns_low_blur(self, analyzer):
        """A clean crisp image should be classified as 'low' blur.

        We use a simple checkerboard pattern with 15-pixel spacing on an
        800x600 canvas — Laplacian variance should be well above the
        medium-threshold (200).
        """
        sharp_bgr = np.zeros((600, 800, 3), dtype=np.uint8)
        sharp_bgr[::15, ::15] = 255
        sharp_bgr[7::15, 7::15] = 255

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