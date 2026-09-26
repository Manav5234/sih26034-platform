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

## Memory-constrained hosts: OCR_ENGINE_MODE=tesseract_only

On Render's free tier (512MB RAM, single worker) RapidOCR's in-process ONNX
model load + inference blows the memory ceiling:

| Stage | Process RSS (from structured logs) |
|---|---|
| `startup_baseline` | ~124MB |
| `rapidocr_pre_infer` (single 1200x1600 image) | ~210MB+ → OOM-killed |

The kill is not graceful: the worker dies mid-request, the scan request hangs
forever, and the frontend sits on "Analyzing Declarations..." at a fixed
percentage because the backend restarted underneath it.

Tesseract avoids this ceiling because it runs as a **subprocess** via
`pytesseract` — its memory lives in the child process's RSS, not this
process's, so it never counts against the 512MB ceiling the app server sits
under.

Set `OCR_ENGINE_MODE=tesseract_only` (see `backend/.env.example`) to build the
chain as Tesseract-only. RapidOCRProvider is never even constructed, so
`rapidocr_onnxruntime` is never imported and the model never loads. `"auto"`
(the default) keeps today's behavior: RapidOCR primary, Tesseract fallback.

**This is a visible, documented accuracy trade-off, not a silent one.**
Per the accuracy table above, Tesseract is weaker on Hindi/regional text
(Poor vs Good), curved/warped text (Poor vs Good) and low-contrast text —
expect more extraction misses on those labels while this flag is on.

**Revert to `OCR_ENGINE_MODE=auto` as soon as the host has more memory**
(paid Render tier or bigger instance); the flag exists purely as a stopgap,
not a permanent engine choice.
