"""Diagnose scan 895edb8d: pull scan data, image paths, declarations, and raw OCR."""
import sys, os, traceback
sys.path.insert(0, "/app")

from app.database import engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

Session = sessionmaker(bind=engine)
db = Session()

scan_id = "895edb8d-22ff-4335-8856-67dce98e2479"

# 1. Scan metadata
scan = db.execute(text("SELECT id, status, overall_status, image_quality, created_at FROM scans WHERE id = :sid"), {"sid": scan_id}).fetchone()
if not scan:
    print(f"SCAN {scan_id} NOT FOUND")
    sys.exit(1)

print(f"=== SCAN {str(scan[0])[:8]} ===")
print(f"Status: {scan[1]}")
print(f"Overall: {scan[2]}")
print(f"Image quality raw: {scan[3]}")
print(f"Created: {scan[4]}")

# 2. Images
imgs = db.execute(text("SELECT id, label, url FROM images WHERE scan_id = :sid"), {"sid": scan_id}).fetchall()
print(f"\nImages ({len(imgs)}):")
for i in imgs:
    print(f"  {i[1]}: {i[2]} (id={str(i[0])[:8]})")
    # Check file size on disk
    fpath = "/app" + i[2]
    if os.path.exists(fpath):
        sz = os.path.getsize(fpath)
        print(f"    File size: {sz} bytes")
        if sz == 0:
            print(f"    *** ZERO-BYTE FILE ***")
    else:
        print(f"    *** FILE MISSING ***")

# 3. Declarations
decls = db.execute(text("SELECT field_name, verdict, extracted_value, confidence, reason FROM declarations WHERE scan_id = :sid ORDER BY field_name"), {"sid": scan_id}).fetchall()
print(f"\nDeclarations ({len(decls)}):")
for d in decls:
    print(f"  {d[0]}: {d[1]} conf={d[3]} reason={d[4]} val={str(d[2])[:100]}")

# 4. Evidence
evid = db.execute(text("SELECT e.source_type, e.raw_text, e.confidence, e.image_id, e.preprocessing_variant FROM evidence e JOIN declarations d ON e.declaration_id = d.id WHERE d.scan_id = :sid"), {"sid": scan_id}).fetchall()
print(f"\nEvidence ({len(evid)}):")
for e in evid:
    print(f"  [{e[0]}] \"{e[1]}\" conf={e[2]} img={str(e[3])[:8] if e[3] else 'None'} variant={e[4]}")

db.close()
