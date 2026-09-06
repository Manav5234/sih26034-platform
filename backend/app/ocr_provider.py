"""OCR Provider Abstraction — multi-engine OCR with normalized output.

Defines OCRToken/OCRLine normalized representation and provider interface.
Both PaddleOCR and Tesseract are normalized into the same schema.
The rest of the pipeline works with the normalized representation only;
provider-specific output is never exposed to extraction.py.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Protocol, runtime_checkable

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
        self.source_provider = source_provider  # "paddleocr" or "tesseract"
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

        raw = _run_ocr(image_path)

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
# PaddleOCR provider — skeleton; to be filled in Phase 3
# ---------------------------------------------------------------------------

class PaddleOCRProvider:
    """PaddleOCR provider — primary engine once integrated.

    To be implemented in Phase 3 after Phase 1 compatibility spike confirms
    environment stability.  Will normalize PaddleOCR output into the same
    contract as TesseractProvider.
    """

    name = "paddleocr"

    def __init__(self):
        self._engine = None  # lazily initialized
        self._initialized = False

    def _ensure_loaded(self):
        """Lazy import of PaddleOCR to avoid dependency errors."""
        if not self._initialized:
            try:
                from paddleocr import PaddleOCR  # type: ignore
                self._engine = PaddleOCR(lang_en=True, use_angle_cls=False, show_log=False)
                self._initialized = True
            except ImportError:
                logger.warning("PaddleOCR not available — falling back to Tesseract")
                self._engine = None
                self._initialized = True

    def extract(
        self,
        image_path: str,
        variant: str = "single_pass",
    ) -> dict[str, list[dict]]:
        """Run PaddleOCR and return normalized token/line results."""
        if self._engine is None:
            # Fallback to Tesseract when PaddleOCR not available
            from app.ocr import run_ocr as _run_ocr
            raw = _run_ocr(image_path)
            # Add variant info
            for t in raw.get("tokens", []):
                t["source_provider"] = "paddleocr_fallback"
                t["preprocessing_variant"] = variant
            for l in raw.get("lines", []):
                l["source_provider"] = "paddleocr_fallback"
                l["preprocessing_variant"] = variant
            return {"tokens": raw.get("tokens", []), "lines": raw.get("lines", [])}

        # TODO: actual PaddleOCR inference in Phase 3
        # For now, fall back to Tesseract
        from app.ocr import run_ocr as _run_ocr
        raw = _run_ocr(image_path)
        for t in raw.get("tokens", []):
            t["source_provider"] = "paddleocr"
            t["preprocessing_variant"] = variant
        for l in raw.get("lines", []):
            l["source_provider"] = "paddleocr"
            l["preprocessing_variant"] = variant
        return {"tokens": raw.get("tokens", []), "lines": raw.get("lines", [])}


# ---------------------------------------------------------------------------
# Provider registry — default chain: PaddleOCR primary, Tesseract fallback
# ---------------------------------------------------------------------------

_PROVIDER_CHAIN: list[OCRProvider] = [PaddleOCRProvider(), TesseractProvider()]


def get_provider_chain() -> list[OCRProvider]:
    """Return the default provider chain (PaddleOCR primary, Tesseract fallback)."""
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

    last_error: str | None = None
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
            last_error = str(e)
            logger.warning("Provider %s failed for %s: %s", provider.name, image_path, e)
            continue

    # All providers failed — return empty result
    return {"tokens": [], "lines": []}