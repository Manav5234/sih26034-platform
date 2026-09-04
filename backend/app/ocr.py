"""OCR orchestrator — single-pass CPU OCR using pytesseract.

Initialises the model once at module level.  Returns normalised OCR results
with BOTH per-token and per-line-grouped output.

Uses pytesseract (wrapped Tesseract OCR).  PaddleOCR is not compiled/installed
for this environment and is omitted from requirements.txt to avoid SIGSEGV crashes.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import List, Dict

logger = logging.getLogger(__name__)

import pytesseract  # type: ignore

logger.info("pytesseract initialised at module level")


def _normalize_result(text: str, bbox: List[float], confidence: float) -> Dict:
    """Normalise a single OCR result to a consistent schema."""
    return {
        "text": text.strip() if text else "",
        "bbox": bbox,
        "confidence": round(max(confidence, 0.0), 3),
    }


def run_ocr(image_path: str) -> Dict[str, List[Dict]]:
    """Run OCR on an image file and return both per-token and per-line results.

    Returns a dict with two keys:
        - "tokens": List of per-word results (original fine-grained output)
        - "lines":  List of per-line grouped results (reconstructed lines)

    Each result has the keys:
        - text: str
        - bbox: List[float] [x, y, width, height]
        - confidence: float in [0, 1]

    The lists may be empty if no text is detected.
    """
    import cv2

    img = cv2.imread(image_path)
    if img is None:
        return {"tokens": [], "lines": []}

    data = pytesseract.image_to_data(
        img, lang="eng", config="--psm 6", output_type=pytesseract.Output.DICT
    )

    # --- per-token results (same as 7a) ---
    tokens: List[Dict] = []
    n = len(data["level"])
    for i in range(n):
        text = data["text"][i].strip()
        if not text:
            continue
        try:
            conf = float(data["conf"][i])
            if conf < 0:
                conf = 0.0
            conf = round(conf / 100.0, 3)
        except ValueError:
            conf = 0.0

        x = int(data["left"][i])
        y = int(data["top"][i])
        w = int(data["width"][i])
        h = int(data["height"][i])
        bbox = [float(x), float(y), float(w), float(h)]

        tokens.append({
            **_normalize_result(text, bbox, conf),
            "block_num": int(data["block_num"][i]),
            "par_num": int(data["par_num"][i]),
            "line_num": int(data["line_num"][i]),
            "left": x,
        })

    # --- group tokens into lines ---
    line_groups: Dict[tuple, List[Dict]] = defaultdict(list)
    for t in tokens:
        key = (t["block_num"], t["par_num"], t["line_num"])
        line_groups[key].append(t)

    lines: List[Dict] = []
    for key in sorted(line_groups.keys()):
        group = sorted(line_groups[key], key=lambda t: t["left"])

        line_text = " ".join(t["text"] for t in group)

        xs = [t["left"] for t in group]
        ys = [t["bbox"][1] for t in group]
        rights = [t["left"] + t["bbox"][2] for t in group]
        bottoms = [t["bbox"][1] + t["bbox"][3] for t in group]

        line_bbox = [
            float(min(xs)),
            float(min(ys)),
            float(max(rights) - min(xs)),
            float(max(bottoms) - min(ys)),
        ]

        confs = [t["confidence"] for t in group]
        line_conf = round(sum(confs) / len(confs), 3)

        lines.append(_normalize_result(line_text, line_bbox, line_conf))

    return {"tokens": tokens, "lines": lines}
