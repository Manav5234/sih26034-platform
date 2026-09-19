"""Benchmark RapidOCR vs Tesseract on test images."""
import time
import os

os.chdir(os.path.join(os.path.dirname(__file__), ".."))
import sys
sys.path.insert(0, ".")

from app.ocr_provider import RapidOCRProvider, TesseractProvider

IMAGES = [
    os.path.join("..", "tests", "sharp.png"),
    os.path.join("..", "tests", "blurry.png"),
]

rapid = RapidOCRProvider()
tess = TesseractProvider()

print("OCR Engine Benchmark")
print("=" * 70)
print(f"{'Image':<20} {'Engine':<12} {'Lines':>5} {'AvgConf':>8} {'Time':>8}")
print("-" * 70)

for img_path in IMAGES:
    if not os.path.exists(img_path):
        print(f"  SKIP {img_path} (not found)")
        continue
    for name, prov in [("rapidocr", rapid), ("tesseract", tess)]:
        try:
            t0 = time.perf_counter()
            r = prov.extract(img_path)
            elapsed = time.perf_counter() - t0
            nl = len(r["lines"])
            avg_conf = sum(l["confidence"] for l in r["lines"]) / nl if nl else 0
            print(f"{os.path.basename(img_path):<20} {name:<12} {nl:>5} {avg_conf:>8.3f} {elapsed:>7.3f}s")
        except Exception as e:
            print(f"{os.path.basename(img_path):<20} {name:<12} ERROR: {e}")
    print()
