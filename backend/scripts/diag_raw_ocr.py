"""Raw OCR dump for both images of scan 895edb8d."""
import sys, os
sys.path.insert(0, "/app")
import pytesseract
from PIL import Image

scan_id = "895edb8d-22ff-4335-8856-67dce98e2479"
upload_root = "/data/uploads"

for label in ["front", "back"]:
    img_dir = os.path.join(upload_root, scan_id)
    files = os.listdir(img_dir)
    # Find the file matching label order (front first uploaded, back second)
    # The DB stores them in order: front first, back second
    # Check the actual filenames
    print(f"=== {label.upper()} IMAGE ===")
    for fname in sorted(files):
        fpath = os.path.join(img_dir, fname)
        sz = os.path.getsize(fpath)
        print(f"  File: {fname} ({sz} bytes)")

    # Use the correct file
    target = None
    for fname in sorted(files):
        fpath = os.path.join(img_dir, fname)
        if label == "front" and fname == sorted(files)[0]:
            target = fpath
        elif label == "back" and fname == sorted(files)[1]:
            target = fpath
    if not target:
        target = os.path.join(img_dir, sorted(files)[0 if label == "front" else 1])

    print(f"  Processing: {target}")
    try:
        img = Image.open(target)
        print(f"  Image size: {img.size}, mode: {img.mode}")

        # Raw text
        raw_text = pytesseract.image_to_string(img)
        print(f"  Raw text ({len(raw_text)} chars):")
        for line in raw_text.strip().split("\n"):
            if line.strip():
                print(f"    |{line}|")

        # image_to_data for word-level confidence
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        words = []
        for i, text in enumerate(data["text"]):
            if text.strip():
                conf = int(data["conf"][i])
                words.append((text, conf, data["left"][i], data["top"][i], data["width"][i], data["height"][i]))
        print(f"\n  Words with confidence ({len(words)}):")
        for w, c, x, y, bw, bh in words:
            print(f"    conf={c:3d} text='{w}' bbox=({x},{y},{bw},{bh})")

        if not words:
            print(f"    *** NO TEXT DETECTED AT ALL ***")

    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
    print()
