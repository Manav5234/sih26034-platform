"""Trace extraction on the actual OCR output for the Dr. Liver back image."""
import sys, os
sys.path.insert(0, "/app")
import pytesseract
from PIL import Image

from app.extraction import (
    extract_mrp, extract_net_quantity, extract_manufacturer,
    extract_manufacture_date, extract_expiry_date,
    extract_nutrition_facts, extract_cautions,
)

scan_id = "895edb8d-22ff-4335-8856-67dce98e2479"
img_dir = f"/data/uploads/{scan_id}"
files = sorted(os.listdir(img_dir))

for label, fname in zip(["front", "back"], files):
    fpath = os.path.join(img_dir, fname)
    print(f"=== {label.upper()} IMAGE: {fname} ({os.path.getsize(fpath)} bytes) ===")

    img = Image.open(fpath)
    print(f"  Size: {img.size}, Mode: {img.mode}")

    # Run OCR same way the pipeline does
    raw_text = pytesseract.image_to_string(img)
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    # Build results list like run_ocr does
    results = []
    for i, text in enumerate(data["text"]):
        if text.strip():
            conf = int(data["conf"][i]) / 100.0  # normalize to 0-1
            results.append({
                "text": text.strip(),
                "confidence": conf,
                "bbox": {
                    "x": data["left"][i],
                    "y": data["top"][i],
                    "width": data["width"][i],
                    "height": data["height"][i],
                }
            })

    print(f"  OCR words: {len(results)}")
    for r in results[:10]:
        print(f"    conf={r['confidence']:.2f} text='{r['text']}'")
    if len(results) > 10:
        print(f"    ... and {len(results)-10} more")

    # Run each extraction function
    print(f"\n  --- Extraction results ---")
    mrp = extract_mrp(results)
    print(f"  MRP: {mrp}")

    nq = extract_net_quantity(results)
    print(f"  Net quantity: {nq}")

    mf = extract_manufacturer(results)
    print(f"  Manufacturer: {mf}")

    mfd = extract_manufacture_date(results)
    print(f"  Manufacture date: {mfd}")

    exp = extract_expiry_date(results)
    print(f"  Expiry date: {exp}")

    nutr = extract_nutrition_facts(results)
    print(f"  Nutrition facts: {nutr}")

    caut = extract_cautions(results)
    print(f"  Cautions: {caut}")

    # Also check what a raw text dump looks like
    print(f"\n  --- Raw OCR text ---")
    for line in raw_text.strip().split("\n"):
        if line.strip():
            print(f"    |{line}|")
    print()
