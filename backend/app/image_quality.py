"""Image quality analyzer using OpenCV.

This module provides an ImageQualityAnalyzer class that can be swapped out
without touching the pipeline or API callers.  Each detection method works
on a numpy array (grayscale or BGR) and returns a descriptive label.
"""

from __future__ import annotations

import math
from typing import Tuple

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Thresholds (tweak per environment; exposed as module-level constants so
# tests / callers can override them easily).
# ---------------------------------------------------------------------------

# Blur: Laplacian variance thresholds
BLUR_HIGH_THRESHOLD = 100.0
BLUR_MEDIUM_THRESHOLD = 200.0

# Brightness / contrast (mean intensity on 0–255 scale)
BRIGHT_THRESHOLD = 180.0   # mean above → "bright" / low glare risk
DARK_THRESHOLD = 80.0      # mean below → "dark" / possible underexposure

# Resolution: short-edge pixel count below which we flag "low"
MIN_SHORT_EDGE = 800

# Perspective / skew: contour area ratio threshold
PERSPECTIVE_RATIO_THRESHOLD = 0.4


class ImageQualityAnalyzer:
    """Analyze a single image and return quality metrics + recommended action.

    The public entry point is :meth:`analyze` which returns an
    :class:`ImageQuality` dict.  Each sub‑method can be unit‑tested in
    isolation and replaced independently.
    """

    # ------------------------------------------------------------------
    # Blur detection
    # ------------------------------------------------------------------
    def detect_blur(self, gray: np.ndarray) -> str:
        """Return 'high' | 'medium' | 'low' based on Laplacian variance."""

        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

        if laplacian_var < BLUR_HIGH_THRESHOLD:
            return "high"
        if laplacian_var < BLUR_MEDIUM_THRESHOLD:
            return "medium"
        return "low"

    # ------------------------------------------------------------------
    # Brightness / contrast
    # ------------------------------------------------------------------
    def detect_brightness(self, gray: np.ndarray) -> Tuple[str, str]:
        """Return (label, detail) where label is 'bright' | 'normal' | 'dark'
        and detail is a short human readable string."""
        mean_intensity = float(np.mean(gray))

        if mean_intensity < DARK_THRESHOLD:
            return "dark", f"mean={mean_intensity:.1f} (underexposed)"
        if mean_intensity > BRIGHT_THRESHOLD:
            return "bright", f"mean={mean_intensity:.1f} (overexposed)"
        return "normal", f"mean={mean_intensity:.1f}"

    # ------------------------------------------------------------------
    # Rough perspective / skew estimation
    # ------------------------------------------------------------------
    def detect_perspective(self, gray: np.ndarray) -> str:
        """Return 'none' | 'slight_tilt' | 'severe' using Canny + contours.

        Heuristic: find the largest quadrilateral‑ish contour, compute its
        bounding‑rectangle aspect‑ratio and how far the corners deviate from
        a perfect rectangle.  If no decent contour is found we default to 'none'.
        """
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return "none"

        # Look for the largest contour that approximates a quadrilateral
        largest = max(contours, key=cv2.contourArea)
        epsilon = 0.02 * cv2.arcLength(largest, True)
        approx = cv2.approxPolyDP(largest, epsilon, True)

        if len(approx) != 4:
            # Not a four‑sided shape → probably not a skewed package
            return "none"

        # Compute width/height of the quad and aspect ratio
        points = approx.reshape(4, 2)  # (4, 2) array of (x, y) corners
        (tl, tr, br, bl) = points
        width_a = math.sqrt((br[0] - bl[0]) ** 2 + (br[1] - bl[1]) ** 2)
        width_b = math.sqrt((tr[0] - tl[0]) ** 2 + (tr[1] - tl[1]) ** 2)
        max_width = max(width_a, width_b)

        height_a = math.sqrt((tr[0] - br[0]) ** 2 + (tr[1] - br[1]) ** 2)
        height_b = math.sqrt((tl[0] - bl[0]) ** 2 + (tl[1] - bl[1]) ** 2)
        max_height = max(height_a, height_b)

        aspect = max_width / max_height if max_height > 0 else 0.0

        # A "squarish" package has aspect near 1; very elongated = severe tilt
        if aspect > PERSPECTIVE_RATIO_THRESHOLD and aspect < (1.0 / PERSPECTIVE_RATIO_THRESHOLD):
            # Reasonable rectangle → check how "off" it is
            # Simple heuristic: if the contour area differs significantly from
            # the bounding‑rectangle area, treat it as tilted
            area = cv2.contourArea(largest)
            rect_area = width * height if (width := max_width) and (height := max_height) else 0
            solidity = area / rect_area if rect_area > 0 else 0.0

            if solidity < 0.6:
                return "severe"
            return "slight_tilt"

        # Very elongated aspect ratio
        if aspect > (1.0 / PERSPECTIVE_RATIO_THRESHOLD):
            return "severe"
        return "none"

    # ------------------------------------------------------------------
    # Resolution adequacy
    # ------------------------------------------------------------------
    def check_resolution(self, shape: Tuple[int, int]) -> str:
        """Return 'adequate' | 'low' based on the shorter image dimension.

        :param shape: (height, width) from a BGR/grayscale numpy array.
        """
        h, w = shape
        short_edge = min(h, w)
        if short_edge < MIN_SHORT_EDGE:
            return "low"
        return "adequate"

    # ------------------------------------------------------------------
    # Full‑image analysis
    # ------------------------------------------------------------------
    def analyze(self, bgr_image: np.ndarray) -> dict:
        """Run all quality checks and return a dict matching the
        :class:`~app.schemas.scan.ImageQuality` schema.

        :param bgr_image: OpenCV BGR frame (as loaded by cv2.imread or
            FastAPI UploadFile.read()).
        :return: {blur, glare, perspective, resolution, recommended_action}
        """
        gray = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2GRAY)

        blur = self.detect_blur(gray)
        brightness_label, _ = self.detect_brightness(gray)
        perspective = self.detect_perspective(gray)
        resolution = self.check_resolution(gray.shape)

        # Glare is a simplified heuristic: very bright images with high stddev
        _mean, stddev = float(np.mean(gray)), float(np.std(gray))
        glare = "high" if _mean > 200 and stddev > 40 else "none"

        # Determine recommended_action
        # "recapture" if blur is high OR resolution is low OR perspective is severe
        # "proceed_with_caution" if any single factor is borderline (medium)
        # otherwise "proceed"
        blur_high = blur == "high"
        res_low = resolution == "low"
        pers_severe = perspective == "severe"
        any_borderline = (
            blur == "medium"
            or perspective == "slight_tilt"
            or brightness_label in ("dark", "bright")
        )

        if blur_high or res_low or pers_severe:
            recommended_action = "recapture"
        elif any_borderline:
            recommended_action = "proceed_with_caution"
        else:
            recommended_action = "proceed"

        return {
            "blur": blur,
            "glare": glare,
            "perspective": perspective,
            "resolution": resolution,
            "recommended_action": recommended_action,
        }