"""Heuristic candidate-region detection for officer-reviewed placement analysis.

The output of this module is deliberately *not* a legal placement decision.
It identifies visually plausible regions using image geometry and text-like
pixel density, then marks every result for officer review.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np


_METHOD = "contour_and_text_density_heuristic"


def _clamp_box(box: tuple[int, int, int, int], width: int, height: int) -> list[int]:
    x, y, w, h = box
    x = max(0, min(x, width - 1))
    y = max(0, min(y, height - 1))
    w = max(1, min(w, width - x))
    h = max(1, min(h, height - y))
    return [int(x), int(y), int(w), int(h)]


def _iou(left: list[int], right: list[int]) -> float:
    lx, ly, lw, lh = left
    rx, ry, rw, rh = right
    x_overlap = max(0, min(lx + lw, rx + rw) - max(lx, rx))
    y_overlap = max(0, min(ly + lh, ry + rh) - max(ly, ry))
    intersection = x_overlap * y_overlap
    union = lw * lh + rw * rh - intersection
    return intersection / union if union else 0.0


class PlacementAnalyzer:
    """Find reviewable visual regions that may contain grouped declarations.

    This analyzer ranks image regions using only tractable visual signals:
    contour/surface area, text-like density, and relative position.  It does
    not identify a legally valid principal display panel.
    """

    def __init__(self, max_candidates: int = 3) -> None:
        self.max_candidates = max_candidates

    def detect(self, image: np.ndarray) -> list[dict[str, Any]]:
        """Return ranked, explicitly heuristic candidate regions for an image."""
        if image is None or not isinstance(image, np.ndarray) or image.size == 0:
            return []

        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        elif image.ndim == 2:
            gray = image
        else:
            return []

        height, width = gray.shape[:2]
        image_area = width * height
        if image_area == 0 or float(np.std(gray)) < 1.0:
            return []

        # Adaptive threshold highlights text-like dark detail across uneven
        # packaging illumination; contours supply the geometry signal.
        text_mask = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            31,
            11,
        )
        edges = cv2.Canny(gray, 50, 150)
        kernel_size = max(5, min(width, height) // 60)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
        grouped_edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(grouped_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        raw_boxes: list[tuple[list[int], str]] = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area_ratio = (w * h) / image_area
            if area_ratio >= 0.08:
                raw_boxes.append((_clamp_box((x, y, w, h), width, height), "visual_boundary"))

        # The envelope of text-like connected components gives a second,
        # independent signal for declaration grouping.
        component_count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(text_mask)
        text_boxes: list[tuple[int, int, int, int]] = []
        max_component_area = image_area * 0.02
        for index in range(1, component_count):
            x, y, w, h, area = stats[index]
            if 8 <= area <= max_component_area and w >= 2 and h >= 2:
                text_boxes.append((int(x), int(y), int(w), int(h)))
        if text_boxes:
            min_x = min(box[0] for box in text_boxes)
            min_y = min(box[1] for box in text_boxes)
            max_x = max(box[0] + box[2] for box in text_boxes)
            max_y = max(box[1] + box[3] for box in text_boxes)
            pad_x, pad_y = max(8, width // 50), max(8, height // 50)
            raw_boxes.append(
                (
                    _clamp_box(
                        (min_x - pad_x, min_y - pad_y, max_x - min_x + 2 * pad_x, max_y - min_y + 2 * pad_y),
                        width,
                        height,
                    ),
                    "text_grouping",
                )
            )

        # Keep an image-surface fallback for photos where package boundaries
        # are indistinct.  Its lower score makes its uncertainty visible.
        raw_boxes.append(([0, 0, width, height], "image_surface_fallback"))

        candidates: list[dict[str, Any]] = []
        for box, source in raw_boxes:
            if any(_iou(box, item["bbox"]) > 0.85 for item in candidates):
                continue
            x, y, w, h = box
            area_ratio = (w * h) / image_area
            text_density = float(np.count_nonzero(text_mask[y : y + h, x : x + w])) / max(w * h, 1)
            center_x = (x + w / 2) / width
            center_y = (y + h / 2) / height
            centrality = max(0.0, 1.0 - ((center_x - 0.5) ** 2 + (center_y - 0.5) ** 2) * 2)
            area_score = max(0.0, 1.0 - abs(area_ratio - 0.45) / 0.55)
            score = 0.45 * area_score + 0.4 * min(text_density / 0.35, 1.0) + 0.15 * centrality
            if source == "image_surface_fallback":
                score *= 0.55
            candidates.append(
                {
                    "bbox": box,
                    "score": round(float(score), 4),
                    "signals": {
                        "source": source,
                        "relative_area": round(float(area_ratio), 4),
                        "text_density": round(float(text_density), 4),
                        "centrality": round(float(centrality), 4),
                    },
                    "heuristic": True,
                    "authoritative": False,
                    "officer_review_required": True,
                    "method": _METHOD,
                }
            )

        candidates.sort(key=lambda item: item["score"], reverse=True)
        for rank, candidate in enumerate(candidates[: self.max_candidates], start=1):
            candidate["rank"] = rank
        return candidates[: self.max_candidates]


def build_region_hint(image_label: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the persisted declaration hint without asserting legal placement."""
    base: dict[str, Any] = {
        "kind": "placement_candidate_region",
        "image_label": image_label,
        "heuristic": True,
        "authoritative": False,
        "officer_review_required": True,
        "disclaimer": "Heuristic visual region only; it is not a legal placement determination and requires officer review.",
    }
    if not candidates:
        return {**base, "status": "no_candidate_detected", "region": None}
    return {**base, "status": "candidate_available", "region": candidates[0]}
