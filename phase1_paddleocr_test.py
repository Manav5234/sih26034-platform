"""Phase 1 — PaddleOCR Compatibility Spike.

Isolated test to evaluate PaddleOCR in the target environment without
modifying production dependencies.  Designed to run inside the Docker
container (Linux) where PaddleOCR can be installed via apt/wheels.

Run: python phase1_paddleocr_test.py

Does NOT modify any production code or dependencies.
"""

from __future__ import annotations

import time
import json
import os
from typing import List, Dict, Any, Tuple

# -----------------------------------------------------------
# Helpers: normalize OCR output into the common contract
# -----------------------------------------------------------

OCRResult = Dict[str, Any]

def normalize_tesseract_tokens(raw: Dict[str, List]) -> List[OCRResult]:
    """Convert pytesseract Output.DICT into normalized token dicts.

    Contract: {text, bbox [x,y,w,h], confidence [0,1]}
    """
    tokens = []
    n = len(raw.get("level", []))
    for i in range(n):
        text = raw.get("text", [""] * n)[i].strip()
        if not text:
            continue
        try:
            conf = float(raw["conf"][i])
            if conf < 0:
                conf = 0.0
            conf = round(conf / 100.0, 3)
        except (ValueError, TypeError):
            conf = 0.0
        x = int(raw["left"][i])
        y = int(raw["top"][i])
        w = int(raw["width"][i])
        h = int(raw["height"][i])
        tokens.append({
            "text": text,
            "bbox": [float(x), float(y), float(w), float(h)],
            "confidence": conf,
        })
    return tokens


def normalize_tesseract_lines(tokens: List[OCRResult]) -> List[OCRResult]:
    """Group tokens into lines (same algorithm as ocr.py run_ocr)."""
    from collections import defaultdict
    line_groups: Dict[tuple, List[OCRResult]] = defaultdict(list)
    for t in tokens:
        key = (t.get("block_num", 0), t.get("par_num", 0), t.get("line_num", 0))
        line_groups[key].append(t)

    lines: List[OCRResult] = []
    for key in sorted(line_groups.keys()):
        group = sorted(line_groups[key], key=lambda t: t["bbox"][0])
        line_text = " ".join(t["text"] for t in group)
        xs = [t["bbox"][0] for t in group]
        ys = [t["bbox"][1] for t in group]
        rights = [t["bbox"][0] + t["bbox"][2] for t in group]
        bottoms = [t["bbox"][1] + t["bbox"][3] for t in group]
        line_bbox = [float(min(xs)), float(min(ys)),
                     float(max(rights) - min(xs)), float(max(bottoms) - min(ys))]
        confs = [t["confidence"] for t in group]
        line_conf = round(sum(confs) / len(confs), 3) if confs else 0.0
        lines.append({
            "text": line_text,
            "bbox": line_bbox,
            "confidence": line_conf,
        })
    return lines


def normalize_paddle_ocr(raw_result: Dict[str, Any]) -> Tuple[List[OCRResult], List[OCRResult]]:
    """Normalize PaddleOCR raw output into (tokens, lines) contract.

    PaddleOCR returns:
    - img: loaded image
    - res: list of [ [x1,y1,x2,y2,x3,y3,x4,y4], text, score ]

    We normalize to the same contract: tokens with {text, bbox, confidence},
    then grouped into lines.
    """
    results = raw_result.get("results", [])
    if not results:
        return [], []

    # PaddleOCR token-level results
    # Each entry: [bbox_points [8], text, score [0-100]]
    tokens: List[OCRResult] = []
    for item in results:
        bbox_points = item[0]  # 8 coordinates [x1,y1,x2,y2,x3,y3,x4,y4]
        text = item[1] if len(item) > 1 else ""
        score = item[2] if len(item) > 2 else 100.0

        # Convert 8-point polygon to [x, y, w, h]
        xs = [bbox_points[i] for i in range(0, 8, 2)]
        ys = [bbox_points[i] for i in range(1, 8, 2)]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        bbox = [float(min_x), float(min_y), float(max_x - min_x), float(max_y - min_y)]

        conf = round(min(max(score / 100.0, 0.0), 1.0), 3)  # Paddle score is 0-100

        tokens.append({
            "text": text,
            "bbox": bbox,
            "confidence": conf,
        })

    # Group tokens into lines using same algorithm as tesseract
    line_groups: Dict[tuple, List[OCRResult]] = {}
    for t in tokens:
        # Use center point for line grouping
        cx = (t["bbox"][0] + t["bbox"][0] + t["bbox"][2]) / 2  # center-x
        cy = (t["bbox"][1] + t["bbox"][3]) / 2  # center-y
        # Simple grouping by proximity - same block/par/line approximated
        # We'll use a simple approach: group by rounded y-position and x-position
        key = (round(cy / 20) * 20, round(cx / 20) * 20)  # 20px grid
        if key not in line_groups:
            line_groups[key] = []
        line_groups[key].append(t)

    lines: List[OCRResult] = []
    for key in sorted(line_groups.keys()):
        group = sorted(line_groups[key], key=lambda t: t["bbox"][0])
        line_text = " ".join(t["text"] for t in group if t["text"])
        xs = [t["bbox"][0] for t in group]
        ys = [t["bbox"][1] for t in group]
        rights = [t["bbox"][0] + t["bbox"][2] for t in group]
        bottoms = [t["bbox"][1] + t["bbox"][3] for t in group]
        line_bbox = [float(min(xs)), float(min(ys)),
                     float(max(rights) - min(xs)), float(max(bottoms) - min(ys))]
        confs = [t["confidence"] for t in group]
        line_conf = round(sum(confs) / len(confs), 3) if confs else 0.0
        lines.append({
            "text": line_text,
            "bbox": line_bbox,
            "confidence": line_conf,
        })

    return tokens, lines


# -----------------------------------------------------------
# Test images (paths relative to script location or /data)
# -----------------------------------------------------------

TEST_IMAGES = {
    "freshharvest": "tests/freshharvest.jpg",
    "coca_cola": "tests/coca_cola.jpg",
    "dr_liver": "tests/dr_liver.jpg",
    "blurry": "tests/blurry_test.png",
    "sharp": "tests/sharp_test.png",
}

# In Docker, images would be at /data/uploads/ or /mnt/data/
# For now, we use paths relative to script cwd; Docker volume mounts
# will make real images available at runtime.

# -----------------------------------------------------------
# Phase 1 Main
# -----------------------------------------------------------

def run_ocr_tesseract(image_path: str) -> Dict[str, List[OCRResult]]:
    """Run Tesseract OCR and return normalized tokens + lines."""
    import cv2
    import pytesseract

    img = cv2.imread(image_path)
    if img is None:
        return {"tokens": [], "lines": []}

    raw = pytesseract.image_to_data(
        img, lang="eng", config="--psm 6", output_type=pytesseract.Output.DICT
    )

    tokens = normalize_tesseract_tokens(raw)
    lines = normalize_tesseract_lines(tokens)

    return {"tokens": tokens, "lines": lines}


def run_ocr_paddle(image_path: str) -> Dict[str, Any]:
    """Run PaddleOCR and return raw result + normalized output.

    Returns dict with keys: raw, tokens, lines.
    """
    try:
        from paddleocr import PaddleOCR
    except ImportError:
        return {"error": "paddleocr_not_installed"}

    # Use smallest model, CPU only, English language
    # psm 6 equivalent: keep default PSM (6 = uniform block of text)
    paddle = PaddleOCR(lang_en=True, use_angle_cls=False, show_log=False)

    # Read image with OpenCV for consistency
    import cv2
    img = cv2.imread(image_path)
    if img is None:
        return {"error": "image_not_loadable"}

    # PaddleOCR expects BGR or RGB; it will process internally
    start = time.time()
    raw_result = paddle.ocr(img, cls=False)  # disable angle classification for CPU speed
    elapsed = time.time() - start

    # Normalize
    tokens, lines = normalize_paddle_ocr(raw_result if raw_result else [])

    return {
        "raw": raw_result,
        "tokens": tokens,
        "lines": lines,
        "elapsed_seconds": elapsed,
    }


def compare_outputs(t_result: Dict[str, List[OCRResult]],
                    p_result: Dict[str, Any]) -> Dict[str, Any]:
    """Compare Tesseract vs PaddleOCR output.

    Returns comparison summary including:
    - token count differences
    - line count differences
    - text agreements/disagreements
    - confidence comparison
    """
    tt_tokens = t_result.get("tokens", [])
    tt_lines = t_result.get("lines", [])
    pt_tokens = p_result.get("tokens", [])
    pt_lines = p_result.get("lines", [])

    comparison = {
        "tesseract": {
            "token_count": len(tt_tokens),
            "line_count": len(tt_lines),
        },
        "paddleocr": {
            "token_count": len(pt_tokens),
            "line_count": len(pt_lines),
        },
        "token_agreements": 0,
        "token_disagreements": 0,
        "confidence_spread": [],
    }

    # Compare token text
    tt_texts = {t["text"].lower().strip(): t for t in tt_tokens}
    pt_texts = {t["text"].lower().strip(): t for t in pt_tokens}

    for t_text, t_obj in tt_texts.items():
        if t_text in pt_texts:
            comparison["token_agreements"] += 1
            c_diff = abs(t_obj["confidence"] - pt_texts[t_text]["confidence"])
            comparison["confidence_spread"].append({
                "text": t_text,
                "tesseract_conf": t_obj["confidence"],
                "paddle_conf": pt_texts[t_text]["confidence"],
                "diff": c_diff,
            })
        else:
            comparison["token_disagreements"] += 1

    # Lines comparison
    comparison["paddleocr"]["line_agreements"] = 0
    comparison["paddleocr"]["line_disagreements"] = 0
    for l in pt_lines:
        l_text = l["text"].lower().strip()
        # Find matching tesseract line
        found = False
        for t in tt_lines:
            if t["text"].lower().strip() == l_text:
                comparison["paddleocr"]["line_agreements"] += 1
                found = True
                break
        if not found:
            comparison["paddleocr"]["line_disagreements"] += 1

    return comparison


def main():
    """Run Phase 1 PaddleOCR compatibility spike."""
    print("=" * 60)
    print("PHASE 1: PaddleOCR Compatibility Spike")
    print("=" * 60)

    # 1. Check Python version
    import sys
    print(f"\n[1] Python version: {sys.version}")

    # 2. Test Tesseract against test images
    print(f"\n[2] Testing Tesseract OCR against test images...")
    tesseract_results = {}
    for name, path in TEST_IMAGES.items():
        full_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
        if not os.path.isfile(full_path):
            # Try /data/uploads/ for Docker-mounted paths
            alt_path = f"/data/uploads/{path}"
            if os.path.isfile(alt_path):
                full_path = alt_path
            else:
                print(f"  ! Skipping {name}: image not found at {full_path} or {alt_path}")
                continue
        try:
            t_result = run_ocr_tesseract(full_path)
            tesseract_results[name] = t_result
            print(f"  ✓ {name}: {t_result['token_count']} tokens, {t_result['line_count']} lines")
        except Exception as e:
            print(f"  ✗ {name}: Tesseract error - {e}")

    # 3. Test PaddleOCR (may not be installed yet)
    print(f"\n[3] Testing PaddleOCR...")
    paddle_available = True
    paddle_results = {}
    try:
        from paddleocr import PaddleOCR
        print("  ✓ PaddleOCR import successful")
    except ImportError:
        paddle_available = False
        print("  ! PaddleOCR not installed — will skip inference")

    if paddle_available:
        for name, path in TEST_IMAGES.items():
            full_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
            if not os.path.isfile(full_path):
                alt_path = f"/data/uploads/{path}"
                if os.path.isfile(alt_path):
                    full_path = alt_path
                else:
                    print(f"  - {name}: image not found, skipping PaddleOCR")
                    continue
            try:
                p_result = run_ocr_paddle(full_path)
                paddle_results[name] = p_result
                print(f"  ✓ {name}: PaddleOCR done in {p_result.get('elapsed_seconds', '?') :.2f}s, "
                      f"{p_result.get('tokens', [])} tokens, {p_result.get('lines', [])} lines")
            except Exception as e:
                print(f"  ✗ {name}: PaddleOCR error - {e}")
                paddle_results[name] = {"error": str(e)}

    # 4. Compare outputs where both succeeded
    print(f"\n[4] Comparing Tesseract vs PaddleOCR output...")
    comparisons = {}
    for name in tesseract_results:
        if name in paddle_results and paddle_available:
            comp = compare_outputs(tesseract_results[name], paddle_results[name])
            comparisons[name] = comp
            print(f"  {name}: agreements={comp['token_agreements']}, "
                  f"disagreements={comp['token_disagreements']}, "
                  f"confidence entries={len(comp['confidence_spread'])}")
            # Show a few sample comparisons
            for entry in comp["confidence_spread"][:5]:
                print(f"    TEXT: '{entry['text']}'  TESS={entry['tesseract_conf']:.3f}  PADDLE={entry['paddle_conf']:.3f}  diff={entry['diff']:.3f}")

    # 5. Summary
    print(f"\n{'=' * 60}")
    print("PHASE 1 SUMMARY")
    print(f"{'=' * 60}")
    print(f"Python version: {sys.version.split()[0]}")
    print(f"Tesseract: working across {len(tesseract_results)} images")
    print(f"PaddleOCR available: {paddle_available}")
    if paddle_available:
        working = sum(1 for r in paddle_results.values() if "error" not in r)
        print(f"PaddleOCR: working across {working}/{len(paddle_results)} images")
    print(f"\nNext step: If PaddleOCR environment is stable, proceed to Phase 2")
    print(f"to create the OCR provider abstraction boundary.")

    return 0


if __name__ == "__main__":
    exit(main())