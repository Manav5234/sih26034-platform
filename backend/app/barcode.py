"""Barcode / QR code decoder using pyzbar.

Decodes all barcodes and QR codes found in an image and returns normalised
results with the same bbox shape used elsewhere ({x, y, width, height}).

Confidence is always 1.0 for successfully decoded barcodes — pyzbar either
decodes a symbol or it doesn't; there is no partial-confidence concept here.
This is unlike OCR where confidence reflects per-character certainty.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List

import cv2
from pyzbar import pyzbar  # type: ignore

logger = logging.getLogger(__name__)

# URL detection: simple heuristic, not RFC-compliant, avoids auto-fetching.
_URL_RE = re.compile(
    r"^https?://[^\s]+$",
    re.IGNORECASE,
)


def _classify_payload(data: str) -> str:
    """Classify a decoded QR payload without fetching it.

    Returns one of: "url", "structured_data", "plain_text".
    """
    if _URL_RE.match(data):
        return "url"
    # Heuristic: if it contains key-value separators or JSON-like structure,
    # treat as structured data.
    if re.search(r"[=:&?{}]", data):
        return "structured_data"
    return "plain_text"


def _polygon_to_bbox(points) -> dict[str, float]:
    """Convert pyzbar polygon points to {x, y, width, height}."""
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    return {
        "x": float(x_min),
        "y": float(y_min),
        "width": float(x_max - x_min),
        "height": float(y_max - y_min),
    }


class BarcodeDecoder:
    """Decode barcodes and QR codes from an image file."""

    def decode(self, image_path: str) -> list[dict]:
        """Run pyzbar on *image_path* and return normalised results.

        Each result dict contains:
            - format: str (e.g. "EAN13", "QRCODE")
            - data: str (decoded payload)
            - bbox: dict with x, y, width, height
            - confidence: float (always 1.0 — see module docstring)
            - payload_type: str (for QR: "url" | "structured_data" | "plain_text",
                             for barcodes: "barcode_data")
        """
        img = cv2.imread(image_path)
        if img is None:
            return []

        decoded = pyzbar.decode(img)
        results: list[dict] = []

        for obj in decoded:
            data = obj.data.decode("utf-8", errors="replace")
            fmt = obj.type  # e.g. "EAN13", "QRCODE", "CODE128"

            payload_type = "barcode_data"
            if fmt == "QRCODE":
                payload_type = _classify_payload(data)

            results.append({
                "format": fmt,
                "data": data,
                "bbox": _polygon_to_bbox(obj.polygon),
                "confidence": 1.0,  # pyzbar: decode succeeds or fails, no partial confidence
                "payload_type": payload_type,
            })

        return results
