"""Check actual upload path /data/uploads."""
import os, glob

scan_id = "895edb8d-22ff-4335-8856-67dce98e2479"
upload_dir = f"/data/uploads/{scan_id}"

print(f"=== /data/uploads/{scan_id} ===")
print(f"Dir exists: {os.path.exists(upload_dir)}")
if os.path.exists(upload_dir):
    files = os.listdir(upload_dir)
    print(f"Files: {len(files)}")
    for f in files:
        fp = os.path.join(upload_dir, f)
        sz = os.path.getsize(fp)
        print(f"  {f}: {sz} bytes")
else:
    # Check parent
    parent = "/data/uploads"
    if os.path.exists(parent):
        entries = os.listdir(parent)
        print(f"/data/uploads has {len(entries)} entries")
        for e in sorted(entries)[:20]:
            ep = os.path.join(parent, e)
            if os.path.isdir(ep):
                subfiles = os.listdir(ep)
                print(f"  {e}/ ({len(subfiles)} files)")
                for sf in subfiles[:3]:
                    sfp = os.path.join(ep, sf)
                    print(f"    {sf}: {os.path.getsize(sfp)} bytes")
            else:
                print(f"  {e}: {os.path.getsize(ep)} bytes")
    else:
        print("/data/uploads does not exist!")

# Check all scans in DB to see if ANY have files
from app.database import engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
Session = sessionmaker(bind=engine)
db = Session()
scans = db.execute(text("SELECT id, created_at FROM scans ORDER BY created_at DESC LIMIT 5")).fetchall()
print(f"\n=== Recent scans ===")
for s in scans:
    sid = str(s[0])
    img_dir = f"/data/uploads/{sid}"
    exists = os.path.exists(img_dir)
    nfiles = len(os.listdir(img_dir)) if exists else 0
    print(f"  {sid[:8]}... created={s[1]} files={nfiles}")
db.close()
