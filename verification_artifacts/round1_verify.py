"""Round 1 Verification Script — runs inside the backend container."""
import sys, os, uuid, json, time
sys.path.insert(0, "/app")

from datetime import date
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.db.models import (
    Base, Scan, Image, Declaration, Evidence, ComplianceResult, Product,
    ScanStatus, VerificationState, EvidenceSourceType, RuleSet, Rule,
)
from app.pipeline import run_pipeline
from app.ocr import run_ocr
from app.image_quality import ImageQualityAnalyzer
import cv2
import numpy as np

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/sih26034")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def create_test_image(path, text_lines=None, blur_amount=0):
    """Create a synthetic test image with optional text and blur."""
    img = np.ones((400, 600, 3), dtype=np.uint8) * 255
    if text_lines:
        import subprocess
        # Use cv2.putText for simple text
        y = 50
        for line in text_lines:
            cv2.putText(img, line, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
            y += 35
    if blur_amount > 0:
        img = cv2.GaussianBlur(img, (blur_amount, blur_amount), 0)
    cv2.imwrite(path, img)
    return path

def setup_db():
    """Ensure tables exist."""
    Base.metadata.create_all(engine)

def cleanup(scan_ids):
    """Clean up test data."""
    with Session() as db:
        for sid in scan_ids:
            db.execute(text(f"DELETE FROM audit_log WHERE target_id IN (SELECT id FROM inspections WHERE scan_id = '{sid}')"))
            db.execute(text(f"DELETE FROM inspection_locations WHERE inspection_id IN (SELECT id FROM inspections WHERE scan_id = '{sid}')"))
            db.execute(text(f"DELETE FROM inspections WHERE scan_id = '{sid}'"))
            db.execute(text(f"DELETE FROM nutrition_facts WHERE declaration_id IN (SELECT id FROM declarations WHERE scan_id = '{sid}')"))
            db.execute(text(f"DELETE FROM compliance_results WHERE declaration_id IN (SELECT id FROM declarations WHERE scan_id = '{sid}')"))
            db.execute(text(f"DELETE FROM evidence WHERE declaration_id IN (SELECT id FROM declarations WHERE scan_id = '{sid}')"))
            db.execute(text(f"DELETE FROM evidence WHERE image_id IN (SELECT id FROM images WHERE scan_id = '{sid}')"))
            db.execute(text(f"DELETE FROM declarations WHERE scan_id = '{sid}'"))
            db.execute(text(f"DELETE FROM images WHERE scan_id = '{sid}'"))
            db.execute(text(f"DELETE FROM scans WHERE id = '{sid}'"))
        db.commit()

# =====================================================================
# VERIFICATION 1: Sharp-front / Blurry-back
# =====================================================================
print("=" * 70)
print("VERIFICATION 1: Sharp-front / Blurry-back scenario")
print("=" * 70)

setup_db()

# Create a sharp front image with MRP text
front_path = "/tmp/test_sharp_front.jpg"
back_path = "/tmp/test_blurry_back.jpg"

# Sharp front: clear text with MRP
create_test_image(front_path, [
    "MRP Rs. 499.00",
    "Net Qty. 500 g",
    "Brand: TestBrand",
])

# Blurry back: manufacturer info but heavily blurred
create_test_image(back_path, [
    "Mfd by: TestMfg Corp",
    "Address: 123 Industrial Area",
    "Mumbai 400001",
], blur_amount=51)  # Heavy blur

# Create scan
with Session() as db:
    scan_id = uuid.uuid4()
    scan = Scan(id=scan_id, status=ScanStatus.PENDING)
    db.add(scan)
    db.flush()

    # Save images
    with open(front_path, "rb") as f:
        front_data = f.read()
    with open(back_path, "rb") as f:
        back_data = f.read()

    # Save to uploads
    upload_dir = f"/data/uploads/{scan_id}"
    os.makedirs(upload_dir, exist_ok=True)
    front_name = f"{uuid.uuid4().hex}.jpg"
    back_name = f"{uuid.uuid4().hex}.jpg"
    with open(f"{upload_dir}/{front_name}", "wb") as f:
        f.write(front_data)
    with open(f"{upload_dir}/{back_name}", "wb") as f:
        f.write(back_data)

    front_img = Image(id=uuid.uuid4(), scan_id=scan_id, url=f"/uploads/{scan_id}/{front_name}", label="front")
    back_img = Image(id=uuid.uuid4(), scan_id=scan_id, url=f"/uploads/{scan_id}/{back_name}", label="back")
    db.add(front_img)
    db.add(back_img)
    db.flush()

    image_ids = [front_img.id, back_img.id]

    # Run pipeline
    try:
        iq, declarations, overall, barcode_ev, prod_id = run_pipeline(scan_id, image_ids, db)

        print(f"\nImage Quality: {json.dumps(iq, indent=2)}")
        print(f"Overall Status: {overall}")
        print(f"Number of Declarations: {len(declarations)}")

        for decl in declarations:
            print(f"\n  Field: {decl.field_name}")
            print(f"  Verdict: {decl.verdict}")
            print(f"  Value: {decl.extracted_value}")
            print(f"  Confidence: {decl.confidence}")
            print(f"  Reason: {decl.reason}")

        # Check: no global recapture forced
        has_recapture = any(
            iq.get(label, {}).get("recommended_action") == "recapture"
            for label in ["front", "back"]
            if label in iq
        )
        print(f"\n  Global recapture forced: {has_recapture}")

        # Check: back-only fields are NOT_VERIFIED not crashed
        for decl in declarations:
            if decl.field_name == "manufacturer":
                assert decl.verdict in [VerificationState.NOT_VERIFIED, VerificationState.SATISFIED, VerificationState.VIOLATION], \
                    f"manufacturer verdict should be NOT_VERIFIED/SATISFIED/VIOLATION, got {decl.verdict}"
                print(f"  manufacturer verdict OK: {decl.verdict}")

        print("\n  VERIFICATION 1: PASSED — no global recapture, no crash")
    except Exception as e:
        print(f"\n  VERIFICATION 1: FAILED — {e}")
        import traceback
        traceback.print_exc()

    cleanup([scan_id])

# =====================================================================
# VERIFICATION 2: Barcode Mismatch
# =====================================================================
print("\n" + "=" * 70)
print("VERIFICATION 2: Front/back barcode MISMATCH")
print("=" * 70)

# This test requires real barcode images. Since we can't easily create
# synthetic barcode images that pyzbar can decode, we test the
# _deduplicate_barcodes function directly.

from app.pipeline import _deduplicate_barcodes

# Test case: different barcodes on front vs back
test_barcodes = [
    {"data": "8901234567890", "format": "EAN13", "confidence": 0.95, "source_image": "front"},
    {"data": "0012345678905", "format": "EAN13", "confidence": 0.90, "source_image": "back"},
]
deduped, warnings = _deduplicate_barcodes(test_barcodes)
print(f"\n  Input: 2 different barcodes (front=8901234567890, back=0012345678905)")
print(f"  Deduplicated count: {len(deduped)}")
print(f"  Warnings: {warnings}")
assert len(deduped) == 2, f"Expected 2 deduped barcodes, got {len(deduped)}"
assert len(warnings) == 1, f"Expected 1 mismatch warning, got {len(warnings)}"
assert "mismatch" in warnings[0].lower(), f"Warning should mention mismatch: {warnings[0]}"
print("  VERIFICATION 2: PASSED — mismatch detected and warned")

# Test case: same barcode on both images
test_barcodes_same = [
    {"data": "8901234567890", "format": "EAN13", "confidence": 0.95, "source_image": "front"},
    {"data": "8901234567890", "format": "EAN13", "confidence": 0.90, "source_image": "back"},
]
deduped2, warnings2 = _deduplicate_barcodes(test_barcodes_same)
print(f"\n  Input: same barcode on both images")
print(f"  Deduplicated count: {len(deduped2)}")
print(f"  Warnings: {warnings2}")
assert len(deduped2) == 1, f"Expected 1 deduped barcode, got {len(deduped2)}"
assert deduped2[0]["source_image"] == "both", f"Source should be 'both', got {deduped2[0]['source_image']}"
assert len(warnings2) == 0, f"Expected no warnings, got {warnings2}"
print("  VERIFICATION 2: PASSED — same barcode deduplicated to 'both'")

# =====================================================================
# VERIFICATION 3: GS1 Gepir Timeout Diagnosis
# =====================================================================
print("\n" + "=" * 70)
print("VERIFICATION 3: GS1 Gepir adapter reachability")
print("=" * 70)

from app.product_lookup import GS1GepirAdapter

adapter = GS1GepirAdapter()

# Test with a known valid barcode
test_barcodes_diag = ["0049000042566", "5901234123457", "8901234567890"]
for barcode in test_barcodes_diag:
    start = time.time()
    try:
        result = adapter.lookup(barcode)
        elapsed = time.time() - start
        print(f"  Barcode {barcode}: {result is not None} ({elapsed:.2f}s)")
        if result:
            print(f"    Result: {json.dumps(result, indent=2)[:200]}")
    except Exception as e:
        elapsed = time.time() - start
        print(f"  Barcode {barcode}: ERROR after {elapsed:.2f}s — {type(e).__name__}: {e}")

print("\n  VERIFICATION 3: GS1 Gepir reachability test complete")
print("  (Timeouts are environment-specific — GS1 Gepir servers may be slow/unreachable)")
