"""OCR Ensemble — multi-provider, multi-variant OCR evidence fusion.

Produce a unified OCR evidence set from multiple OCR results (different
providers, different preprocessing variants).  Key design goals:

1. Never simply choose the result with the highest OCR confidence.
2. Compare candidates on: text agreement, bounding-box agreement,
   field pattern validity, contextual relevance, OCR confidence,
   source provider, preprocessing variant.
3. Preserve conflicting candidates — let the field-level fusion layer
   resolve them, not the OCR ensemble.
4. Every candidate carries full provenance: provider, variant, bbox,
   confidence, raw text.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Normalized OCR candidate — shared representation across all providers
# ---------------------------------------------------------------------------

@dataclass
class OCREvidence:
    """A single OCR candidate for a field, with full provenance.

    Attributes:
        text: The OCR-recognized text.
        bbox: Bounding box [x, y, width, height] in image coordinates.
        confidence: OCR engine's confidence in this result [0, 1].
        source_provider: Which OCR engine produced this ("tesseract", "paddleocr").
        image_id: Identifier of the image this came from.
        preprocessing_variant: What preprocessing was applied
            ("original", "upscaled_2x", "contrast_enhanced", "deskewed",
             "bottom_crop_2x").
        context_hints: Optional free-text hints about contextual clues
            (e.g. "near_MRP", "above_quantity", "label_MFD").
    """
    text: str
    bbox: list[float]
    confidence: float
    source_provider: str
    image_id: str | None = None
    preprocessing_variant: str = "single_pass"
    context_hints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Convert to dict compatible with existing extraction code.

        Note: Only core keys (text, bbox, confidence, source_provider,
        preprocessing_variant) are returned.  Extra fields like
        context_hints and image_id are part of the normalized representation
        but are not included in the basic dict output to preserve backward
        compatibility with extraction.py which only reads text, bbox, confidence.
        """
        return {
            "text": self.text,
            "bbox": self.bbox,
            "confidence": self.confidence,
            "source_provider": self.source_provider,
            "preprocessing_variant": self.preprocessing_variant,
        }


# ---------------------------------------------------------------------------
# Helper utilities — text/bbox comparison
# ---------------------------------------------------------------------------

def _normalize_text_for_comparison(text: str) -> str:
    """Normalize text for comparison: lowercase, strip, collapse whitespace."""
    return re.sub(r"\s+", " ", text.strip().lower())


def _bbox_iou(box_a: list[float], box_b: list[float]) -> float:
    """Intersection-over-union of two [x, y, w, h] boxes."""
    ax, ay, aw, ah = box_a
    bx, by, bw, bh = box_b
    x_inter = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    y_inter = max(0, min(ay + ah, by + bh) - max(ay, by))
    inter = x_inter * y_inter
    area_a = aw * ah
    area_b = bw * bh
    union = area_a + area_b - inter
    if union == 0:
        return 0.0
    return inter / union


def _texts_agree(a: OCREvidence, b: OCREvidence, threshold: float = 0.85) -> bool:
    """Check if two OCR candidates agree on text (normalized)."""
    return _normalize_text_for_comparison(a.text) == _normalize_text_for_comparison(b.text)


def _bboxes_agree(a: OCREvidence, b: OCREvidence, iou_threshold: float = 0.5) -> bool:
    """Check if two OCR bounding boxes overlap significantly."""
    return _bbox_iou(a.bbox, b.bbox) >= iou_threshold


def _confidence_similar(a: OCREvidence, b: OCREvidence, threshold: float = 0.1) -> bool:
    """Check if two confidences are within a relative threshold."""
    return abs(a.confidence - b.confidence) <= threshold


# Helper: duck-type access for both dicts and OCREvidence objects
def _get_text(line):
    """Extract text from a line dict or OCREvidence object."""
    if hasattr(line, "get"):
        return line.get("text", "").strip()
    return getattr(line, "text", "").strip()


def _get_bbox(line):
    """Extract bbox from a line dict or OCREvidence object."""
    if hasattr(line, "get"):
        return line.get("bbox", [0, 0, 0, 0])
    return getattr(line, "bbox", [0, 0, 0, 0])


def _get_confidence(line):
    """Extract confidence from a line dict or OCREvidence object."""
    if hasattr(line, "get"):
        return line.get("confidence", 0.0)
    return getattr(line, "confidence", 0.0)


def _get_preprocessing(line):
    """Extract preprocessing_variant from a line dict or OCREvidence object."""
    if hasattr(line, "get"):
        return line.get("preprocessing_variant", "single_pass")
    return getattr(line, "preprocessing_variant", "single_pass")


# ---------------------------------------------------------------------------
# Field-level candidate generation from OCR lines
# ---------------------------------------------------------------------------


def generate_field_candidates(
    ocr_lines: list[dict],
    field_name: str,
    source_provider: str,
    image_id: str | None = None,
) -> list[OCREvidence]:
    """Generate field-specific candidates from OCR lines.

    For each field type (mrp, net_quantity, manufacturer, etc.), scan
    the OCR lines and produce OCREvidence candidates with full provenance.

    Accepts both dicts (from run_ocr()) and OCREvidence objects
    (from the normalized representation) via duck-typing helpers.

    Args:
        ocr_lines: List of OCR result dicts with {text, bbox, confidence,
            source_provider, preprocessing_variant, ...}
        field_name: One of "mrp", "net_quantity", "manufacturer",
            "manufacture_date", "expiry_date", "nutrition_facts", "cautions"
        source_provider: Which provider these lines came from
        image_id: Identifier of the image

    Returns:
        List of OCREvidence candidates, each with full provenance.
        May be empty if no relevant lines found.
    """
    candidates: list[OCREvidence] = []

    for line in ocr_lines:
        text = _get_text(line).strip()
        bbox = _get_bbox(line)
        confidence = _get_confidence(line)
        preprocessing = _get_preprocessing(line)

        # Skip empty text
        if not text:
            continue

        # Field-specific candidate generation
        if field_name == "mrp":
            if re.search(r"[₹]|Rs\.?|RS\.?|INR", text, re.IGNORECASE):
                candidates.append(OCREvidence(
                    text=text,
                    bbox=bbox,
                    confidence=confidence,
                    source_provider=source_provider,
                    image_id=image_id,
                    preprocessing_variant=preprocessing,
                    context_hints=["near_currency"],
                ))

        elif field_name == "net_quantity":
            if re.search(r"[\d.]+\s*(g|kg|ml|l|oz|lb|pcs)", text, re.IGNORECASE):
                candidates.append(OCREvidence(
                    text=text,
                    bbox=bbox,
                    confidence=confidence,
                    source_provider=source_provider,
                    image_id=image_id,
                    preprocessing_variant=preprocessing,
                    context_hints=["has_unit"],
                ))

        elif field_name == "manufacturer":
            if re.search(r"[Mm]anufacturer|[Mm]fd|[Cc]reated", text, re.IGNORECASE):
                candidates.append(OCREvidence(
                    text=text,
                    bbox=bbox,
                    confidence=confidence,
                    source_provider=source_provider,
                    image_id=image_id,
                    preprocessing_variant=preprocessing,
                    context_hints=["has_keyword"],
                ))

        elif field_name == "manufacture_date":
            if re.search(r"\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}", text):
                candidates.append(OCREvidence(
                    text=text,
                    bbox=bbox,
                    confidence=confidence,
                    source_provider=source_provider,
                    image_id=image_id,
                    preprocessing_variant=preprocessing,
                    context_hints=["looks_like_date"],
                ))

        elif field_name == "expiry_date":
            if re.search(r"(?:EXP|Best.Before|Use.?By)", text, re.IGNORECASE):
                candidates.append(OCREvidence(
                    text=text,
                    bbox=bbox,
                    confidence=confidence,
                    source_provider=source_provider,
                    image_id=image_id,
                    preprocessing_variant=preprocessing,
                    context_hints=["has_expiry_keyword"],
                ))

        elif field_name == "cautions":
            if re.search(r"\b(?:caution|warning|note|attention)\b", text, re.IGNORECASE):
                candidates.append(OCREvidence(
                    text=text,
                    bbox=bbox,
                    confidence=confidence,
                    source_provider=source_provider,
                    image_id=image_id,
                    preprocessing_variant=preprocessing,
                    context_hints=["caution_keyword"],
                ))

        elif field_name == "nutrition_facts":
            if re.search(r"\b(nutrition|energy|protein|fat|carbohydrate)\b", text, re.IGNORECASE):
                candidates.append(OCREvidence(
                    text=text,
                    bbox=bbox,
                    confidence=confidence,
                    source_provider=source_provider,
                    image_id=image_id,
                    preprocessing_variant=preprocessing,
                    context_hints=["nutrient_keyword"],
                ))

    return candidates


# ---------------------------------------------------------------------------
# OCR Ensemble — produce unified evidence set from multiple results
# ---------------------------------------------------------------------------


def ensemble_ocr_evidence(
    all_candidates: dict[str, list[OCREvidence]],
) -> dict[str, dict[str, Any]]:
    """Produce a unified OCR evidence set from candidates across providers/variants.

    Args:
        all_candidates: Dict mapping field_name → list of OCREvidence candidates
            from different providers/variants.  Example:

            {
                "mrp": [
                    OCREvidence(text="₹ 1500", bbox=[...], confidence=0.93,
                                source_provider="paddleocr", preprocessing_variant="deskewed",
                                context_hints=["near_MRP"]),
                    OCREvidence(text="€1500", bbox=[...], confidence=0.81,
                                source_provider="tesseract", preprocessing_variant="original",
                                context_hints=["near_price"]),
                ],
                "net_quantity": [...],
                ...
            }

    Returns:
        Dict mapping field_name → ensemble result dict with keys:

        - "candidates": List[Dict] — all preserved candidates (as dicts
          via OCREvidence.to_dict()), never silently dropped.
        - "status": "agreed" | "conflict" | "missing"
        - "fused_value": str | None — if agreed, the consensus text
        - "fused_confidence": float — if agreed, the selected confidence
        - "conflict_info": str | None — if conflict, description of
          disagreement, including source providers and texts.
        - "verification_state": "VERIFIED" | "NOT_VERIFIED" | "CONFLICT"

        The key principle:  preserve ALL candidates.  Never silently drop
        a candidate just because its confidence is lower.  The fusion layer
        (fuse_field in fusion.py) will see both candidates and can decide
        based on contextual evidence.
    """
    results: dict[str, dict[str, Any]] = {}

    for field_name, candidates in all_candidates.items():
        if not candidates:
            results[field_name] = {
                "candidates": [],
                "status": "missing",
                "fused_value": None,
                "fused_confidence": 0.0,
                "conflict_info": None,
                "verification_state": "NOT_VERIFIED",
            }
            continue

        # Single candidate — pass through
        if len(candidates) == 1:
            results[field_name] = {
                "candidates": [c.to_dict() for c in candidates],
                "status": "agreed",
                "fused_value": candidates[0].text,
                "fused_confidence": candidates[0].confidence,
                "conflict_info": None,
                "verification_state": "VERIFIED" if candidates[0].confidence >= 0.6 else "NOT_VERIFIED",
            }
            continue

        # Multiple candidates — check agreements vs conflicts
        agreed_pairs = 0
        conflict_pairs = 0

        for i in range(len(candidates)):
            for j in range(i + 1, len(candidates)):
                c1, c2 = candidates[i], candidates[j]
                text_agree = _texts_agree(c1, c2)
                bbox_agree = _bboxes_agree(c1, c2)
                conf_similar = _confidence_similar(c1, c2)

                if text_agree and bbox_agree and conf_similar:
                    agreed_pairs += 1
                else:
                    conflict_pairs += 1

        # Decision: more agreements than conflicts → agreed;
        # more conflicts than agreements → preserve all as conflict
        if agreed_pairs > conflict_pairs:
            # Find best candidate: highest confidence with most agreements
            best_idx = 0
            best_score = -1
            for i, c in enumerate(candidates):
                agreements = sum(
                    1 for j, d in enumerate(candidates)
                    if j != i and _texts_agree(c, d) and _bboxes_agree(c, d)
                )
                score = c.confidence * (1 + agreements)
                if score > best_score:
                    best_score = score
                    best_idx = i

            results[field_name] = {
                "candidates": [c.to_dict() for c in candidates],
                "status": "agreed",
                "fused_value": candidates[best_idx].text,
                "fused_confidence": candidates[best_idx].confidence,
                "conflict_info": None,
                "verification_state": "VERIFIED" if candidates[best_idx].confidence >= 0.6 else "NOT_VERIFIED",
            }
        else:
            # Preserve ALL candidates as conflict
            conflict_descriptions = []
            for c in candidates:
                conflict_descriptions.append(f"{c.source_provider}:{c.text}")
            results[field_name] = {
                "candidates": [c.to_dict() for c in candidates],
                "status": "conflict",
                "fused_value": None,
                "fused_confidence": 0.0,
                "conflict_info": (
                    f"OCR conflict for '{field_name}': "
                    f"disagreeing candidates: "
                    f"{', '.join(conflict_descriptions)}"
                ),
                "verification_state": "CONFLICT",
            }

    return results