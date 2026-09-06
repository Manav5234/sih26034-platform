"""Control test: re-run FreshHarvest deodorant pair to confirm no regression."""
import sys, os, time
sys.path.insert(0, "/app")
import pytesseract
from PIL import Image

# First check: does the FreshHarvest scan still work?
# Use the existing scan data
from app.database import engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
Session = sessionmaker(bind=engine)
db = Session()

# Find the scan with FreshHarvest images
rows = db.execute(text("""
    SELECT s.id, s.status, s.overall_status, s.created_at
    FROM scans s
    WHERE s.id IN (
        SELECT scan_id FROM images WHERE label = 'front'
    )
    ORDER BY s.created_at DESC
    LIMIT 5
""")).fetchall()

print("=== Recent scans ===")
for r in rows:
    sid = str(r[0])
    imgs = db.execute(text("SELECT label FROM images WHERE scan_id = :sid"), {"sid": sid}).fetchall()
    labels = [i[0] for i in imgs]
    decls = db.execute(text("SELECT field_name, verdict, confidence FROM declarations WHERE scan_id = :sid"), {"sid": sid}).fetchall()
    non_trivial = [(d[0], d[1], d[2]) for d in decls if d[2] > 0]
    print(f"  {sid[:8]}... created={r[3]} labels={labels} status={r[1]} overall={r[2]} fields_with_data={len(non_trivial)}/{len(decls)}")

# Find the scan that used artifact2 images (FreshHarvest deodorant)
target = db.execute(text("""
    SELECT s.id FROM scans s
    JOIN images i ON i.scan_id = s.id
    WHERE s.created_at > '2026-09-05T15:20:00'
    ORDER BY s.created_at DESC
    LIMIT 1
""")).fetchone()

if target:
    sid = str(target[0])
    print(f"\n=== Latest scan (control): {sid[:8]} ===")
    imgs = db.execute(text("SELECT id, label, url FROM images WHERE scan_id = :sid"), {"sid": sid}).fetchall()
    for i in imgs:
        fpath = f"/data/uploads/{sid}/{os.path.basename(i[2])}"
        exists = os.path.exists(fpath)
        sz = os.path.getsize(fpath) if exists else 0
        print(f"  {i[1]}: {i[2]} exists={exists} size={sz}")

    decls = db.execute(text("SELECT field_name, verdict, extracted_value, confidence FROM declarations WHERE scan_id = :sid ORDER BY field_name"), {"sid": sid}).fetchall()
    for d in decls:
        print(f"  {d[0]}: {d[1]} conf={d[3]} val={str(d[2])[:80]}")

db.close()
