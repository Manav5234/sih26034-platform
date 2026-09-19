# OCR Engine Decision: RapidOCR vs Tesseract

## Why RapidOCR

RapidOCR wraps PaddleOCR's detection+recognition models via ONNX Runtime — same
accuracy as PaddleOCR without the `paddlepaddle` dependency (fragile, heavy,
platform-specific).  It installs cleanly via pip, no system binary needed.

Tesseract is kept as fallback.  It works, but:
- Requires a system binary (`tesseract-ocr` apt package / Chocolatey)
- Weaker on Indian-language labels and non-Latin scripts
- Lower accuracy on curved/perspective-distorted packaging text
- Slower on multi-lingual mixed-text labels

## Accuracy (known characteristics)

| Scenario | RapidOCR (PaddleOCR models) | Tesseract |
|---|---|---|
| English printed labels | Excellent (~95%+ line accuracy) | Good (~88-92%) |
| Hindi/regional text | Good | Poor |
| Curved/warped text | Good (angle detection) | Poor |
| Low-contrast text | Better (learned features) | Baseline |

## Speed

| Engine | Warm inference (per image) | Cold start |
|---|---|---|
| RapidOCR (ONNX CPU) | ~0.3-1.5s | ~2-3s (model load) |
| Tesseract | ~0.5-2s | ~0.1s |

RapidOCR cold start is higher due to ONNX model loading, but subsequent calls
are competitive.  On GPU, RapidOCR is significantly faster.

## Benchmark on test images

`tests/sharp.png` and `tests/blurry.png` are image-quality fixtures (blur/sharp
detection), not label photos.  Neither engine detects text on them — this is
expected.  A proper benchmark requires real product label images.

To benchmark with real labels, place label photos in `tests/` and run:
```bash
python scripts/benchmark_ocr.py
```

## Decision

**RapidOCR first, Tesseract fallback.** The honesty bug (PaddleOCRProvider
silently relabeling Tesseract output) is fixed: `RapidOCRProvider` returns
empty results when unavailable, and the chain falls through to Tesseract with
 truthful `source_provider: "tesseract"` tagging.
