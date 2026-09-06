"""Check uploads directory for the scan's files."""
import sys, os, glob
sys.path.insert(0, "/app")

scan_id = "895edb8d-22ff-4335-8856-67dce98e2479"
upload_dir = f"/app/uploads/{scan_id}"

print(f"Upload dir exists: {os.path.exists(upload_dir)}")
if os.path.exists(upload_dir):
    files = os.listdir(upload_dir)
    print(f"Files in dir: {len(files)}")
    for f in files:
        fp = os.path.join(upload_dir, f)
        print(f"  {f}: {os.path.getsize(fp)} bytes")
else:
    print("Dir does not exist. Checking parent...")
    parent = "/app/uploads"
    if os.path.exists(parent):
        entries = os.listdir(parent)
        print(f"Entries in /app/uploads: {len(entries)}")
        # Check if our scan_id dir exists under a different path
        for e in entries[:5]:
            print(f"  {e}")
    else:
        print("/app/uploads does not exist either!")

# Also check how the storage module saves files
from app import storage
print(f"\nStorage module: {storage.__file__}")
print(f"Storage class: {dir(storage)}")

# Check the storage.save function
import inspect
if hasattr(storage, 'save'):
    src = inspect.getsource(storage.save)
    print(f"storage.save source:\n{src[:500]}")
elif hasattr(storage, 'LocalStorage'):
    src = inspect.getsource(storage.LocalStorage.save)
    print(f"LocalStorage.save source:\n{src[:500]}")
