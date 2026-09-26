"""OCR Provider Abstraction — multi-engine OCR with normalized output.

Defines OCRToken/OCRLine normalized representation and provider interface.
Both RapidOCR and Tesseract are normalized into the same schema.
The rest of the pipeline works with the normalized representation only;
provider-specific output is never exposed to extraction.py.
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from app.config import settings
from app.observability import log_inference_rss, log_rss

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Normalized representation (shared across all providers)
# ---------------------------------------------------------------------------

class OCRToken:
    """Normalized OCR token — shared representation across all providers."""

    __slots__ = ("text", "bbox", "confidence", "source_provider",
                 "image_id", "preprocessing_variant")

    def __init__(
        self,
        text: str,
        bbox: list[float],
        confidence: float,
        source_provider: str,
        image_id: str | None = None,
        preprocessing_variant: str = "single_pass",
    ):
        self.text = text
        self.bbox = bbox  # [x, y, width, height]
        self.confidence = round(max(confidence, 0.0), 3)
        self.source_provider = source_provider  # "rapidocr" or "tesseract"
        self.image_id = image_id
        self.preprocessing_variant = preprocessing_variant  # "original", "upscaled", "contrast", etc.

    def to_dict(self) -> dict[str, object]:
        """Convert to dict compatible with existing extraction code."""
        return {
            "text": self.text,
            "bbox": self.bbox,
            "confidence": self.confidence,
            # The following are added by the provider layer;
            # extraction.py silently ignores extra keys.
            "source_provider": self.source_provider,
            "image_id": self.image_id,
            "preprocessing_variant": self.preprocessing_variant,
        }


class OCRLine:
    """Normalized OCR line — grouped tokens into a logical line."""

    __slots__ = ("text", "bbox", "confidence", "source_provider",
                 "image_id", "preprocessing_variant")

    def __init__(
        self,
        text: str,
        bbox: list[float],
        confidence: float,
        source_provider: str,
        image_id: str | None = None,
        preprocessing_variant: str = "single_pass",
    ):
        self.text = text
        self.bbox = bbox  # [x, y, width, height]
        self.confidence = round(max(confidence, 0.0), 3)
        self.source_provider = source_provider
        self.image_id = image_id
        self.preprocessing_variant = preprocessing_variant

    def to_dict(self) -> dict[str, object]:
        """Convert to dict compatible with existing extraction code."""
        return {
            "text": self.text,
            "bbox": self.bbox,
            "confidence": self.confidence,
            "source_provider": self.source_provider,
            "image_id": self.image_id,
            "preprocessing_variant": self.preprocessing_variant,
        }


# ---------------------------------------------------------------------------
# Provider protocol / interface
# ---------------------------------------------------------------------------

@runtime_checkable
class OCRProvider(Protocol):
    """Protocol for OCR engine providers.

    Implementations must provide `extract` returning normalized
    token/line results with source_provider and preprocessing_variant set.
    """

    def extract(
        self,
        image_path: str,
        variant: str = "single_pass",
    ) -> dict[str, list[dict]]:
        """Run OCR on *image_path* and return {"tokens": [...], "lines": [...]}.

        The returned dicts contain the normalized contract keys:
        - text: str
        - bbox: List[float] [x, y, width, height]
        - confidence: float in [0, 1]

        Additional keys (source_provider, image_id, preprocessing_variant)
        are set by the provider and silently ignored by extraction.py.
        """
        ...


# ---------------------------------------------------------------------------
# Tesseract provider — wraps existing pytesseract behavior
# ---------------------------------------------------------------------------

class TesseractProvider:
    """Tesseract OCR provider — preserves existing behavior.

    This is the controlled fallback provider.  It wraps the existing
    `run_ocr()` logic and normalizes output into the shared representation.
    """

    name = "tesseract"

    def __init__(self):
        self._initialized = False

    def _ensure_loaded(self):
        """Tesseract is loaded at module level in ocr.py; no-op here."""
        pass

    def extract(
        self,
        image_path: str,
        variant: str = "single_pass",
    ) -> dict[str, list[dict]]:
        """Run Tesseract OCR and return normalized token/line results."""
        from app.ocr import run_ocr as _run_ocr

        # ponytail: diagnostic RSS/dims lines only — inference call unchanged.
        log_inference_rss(logger, "tesseract_pre_infer", image_path, variant)
        try:
            raw = _run_ocr(image_path)
        finally:
            log_inference_rss(logger, "tesseract_post_infer", image_path, variant)

        # Normalize tokens into OCRToken objects, then back to dicts
        # with source_provider and preprocessing_variant set.
        normalized_tokens: list[dict] = []
        for t in raw.get("tokens", []):
            d = t.copy()  # preserve existing keys
            d["source_provider"] = "tesseract"
            d["preprocessing_variant"] = variant
            normalized_tokens.append(d)

        normalized_lines: list[dict] = []
        for l in raw.get("lines", []):
            d = l.copy()
            d["source_provider"] = "tesseract"
            d["preprocessing_variant"] = variant
            normalized_lines.append(d)

        return {"tokens": normalized_tokens, "lines": normalized_lines}


# ---------------------------------------------------------------------------
# RapidOCR provider — PaddleOCR models via ONNX Runtime
# ---------------------------------------------------------------------------

class RapidOCRProvider:
    """RapidOCR provider — primary engine.

    Uses PaddleOCR's own models re-exported to ONNX via rapidocr-onnxruntime.
    PaddleOCR-level accuracy without the heavy paddlepaddle dependency.
    Each detected text box is treated as one line (RapidOCR does line-level
    detection natively).
    """

    name = "rapidocr"

    def __init__(self):
        self._engine = None
        self._initialized = False

    def _ensure_loaded(self):
        """Lazy-import RapidOCR to avoid startup cost if never used."""
        if not self._initialized:
            # ponytail: diagnostic RSS lines only — load logic unchanged.
            log_rss(logger, "memory_rss", stage="rapidocr_pre_load")
            try:
                from rapidocr_onnxruntime import RapidOCR
                self._engine = RapidOCR()
                self._initialized = True
            except ImportError:
                logger.warning("rapidocr-onnxruntime not available")
                self._engine = None
                self._initialized = True
            log_rss(logger, "memory_rss", stage="rapidocr_post_load")

    def extract(
        self,
        image_path: str,
        variant: str = "single_pass",
    ) -> dict[str, list[dict]]:
        """Run RapidOCR and return normalized token/line results."""
        self._ensure_loaded()
        if self._engine is None:
            return {"tokens": [], "lines": []}

        # ponytail: diagnostic RSS/dims lines only — inference call unchanged.
        log_inference_rss(logger, "rapidocr_pre_infer", image_path, variant)
        try:
            result, _elapse = self._engine(image_path)
        except Exception as e:
            logger.warning("RapidOCR failed for %s: %s", image_path, e)
            return {"tokens": [], "lines": []}
        finally:
            log_inference_rss(logger, "rapidocr_post_infer", image_path, variant)

        if not result:
            return {"tokens": [], "lines": []}

        tokens: list[dict] = []
        lines: list[dict] = []
        for item in result:
            polygon, text, confidence = item
            text = text.strip() if text else ""
            if not text:
                continue

            # Convert polygon [[x1,y1],[x2,y2],[x3,y3],[x4,y4]] → [x, y, w, h]
            if not isinstance(polygon, (list, tuple)) or len(polygon) < 2:
                continue
            xs = [p[0] for p in polygon]
            ys = [p[1] for p in polygon]
            x = float(min(xs))
            y = float(min(ys))
            w = float(max(xs) - x)
            h = float(max(ys) - y)
            bbox = [x, y, w, h]

            try:
                conf = round(min(max(float(confidence), 0.0), 1.0), 3)
            except (ValueError, TypeError):
                conf = 0.0
            entry = {
                "text": text,
                "bbox": bbox,
                "confidence": conf,
                "source_provider": "rapidocr",
                "preprocessing_variant": variant,
            }
            tokens.append(entry)
            lines.append(entry)

        return {"tokens": tokens, "lines": lines}


# ---------------------------------------------------------------------------
# Provider registry — chain built from settings.ocr_engine_mode
# ---------------------------------------------------------------------------

def _build_provider_chain(mode: str) -> list[OCRProvider]:
    """Build the provider chain for *mode*.

    "tesseract_only" never constructs RapidOCRProvider, so
    rapidocr_onnxruntime is never imported and its ONNX model never
    loads (memory stopgap for constrained hosts).
    """
    if mode == "tesseract_only":
        logger.info(
            "ocr_engine_mode=tesseract_only: RapidOCR disabled and not constructed"
        )
        return [TesseractProvider()]
    if mode != "auto":
        logger.warning(
            "Unknown ocr_engine_mode %r — falling back to 'auto' "
            "(RapidOCR primary, Tesseract fallback)",
            mode,
        )
    return [RapidOCRProvider(), TesseractProvider()]


_PROVIDER_CHAIN: list[OCRProvider] = _build_provider_chain(settings.ocr_engine_mode)


def get_provider_chain() -> list[OCRProvider]:
    """Return the configured provider chain (see settings.ocr_engine_mode)."""
    return _PROVIDER_CHAIN


def run_ocr_with_provider(
    image_path: str,
    variant: str = "single_pass",
    provider_chain: list[OCRProvider] | None = None,
) -> dict[str, list[dict]]:
    """Run OCR through the provider chain, returning the first successful result.

    Tries each provider in order.  The first provider to not return empty
    results is used.  All results are normalized into the shared contract.
    """
    if provider_chain is None:
        provider_chain = _PROVIDER_CHAIN

    for provider in provider_chain:
        try:
            result = provider.extract(image_path, variant=variant)
            # Check if we got any meaningful results
            tokens = result.get("tokens", [])
            lines = result.get("lines", [])
            if tokens or lines:
                # Ensure all tokens/lines have source_provider and preprocessing_variant
                for t in tokens:
                    if "source_provider" not in t:
                        t["source_provider"] = provider.name
                    if "preprocessing_variant" not in t:
                        t["preprocessing_variant"] = variant
                for l in lines:
                    if "source_provider" not in l:
                        l["source_provider"] = provider.name
                    if "preprocessing_variant" not in l:
                        l["preprocessing_variant"] = variant
                return result
            # Empty results — try next provider
        except Exception as e:
            logger.warning("Provider %s failed for %s: %s", provider.name, image_path, e)
            continue

    # All providers failed — return empty result
    return {"tokens": [], "lines": []}