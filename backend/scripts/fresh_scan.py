import urllib.request, json, sys, os, glob

API = "http://localhost:8000"

def api(path, method="GET", data=None, token=None, files=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data and not files:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode()
    else:
        body = None
    req = urllib.request.Request(f"{API}{path}", data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"HTTP {e.code}: {err}", file=sys.stderr)
        return None

# Login
r = api("/auth/login", "POST", {"email": "admin@sih26034.local", "password": "admin123"})
if not r:
    print("Login failed")
    sys.exit(1)
token = r["token"]
print(f"Login OK")

# Find images
img_dir = "D:/projects/sih/verification_artifacts"
front = None
back = None
# Try numbered pairs first
for prefix in ["artifact2", "artifact3a", "artifact3b"]:
    f1 = os.path.join(img_dir, f"{prefix}-1.png")
    f2 = os.path.join(img_dir, f"{prefix}-2.png")
    if os.path.exists(f1) and os.path.exists(f2):
        front = f1
        back = f2
        break

if not front or not back:
    # List available images
    all_imgs = glob.glob(os.path.join(img_dir, "*"))
    print(f"No front/back pair found. Available: {[os.path.basename(i) for i in all_imgs]}")
    sys.exit(1)

print(f"Front: {os.path.basename(front)}")
print(f"Back: {os.path.basename(back)}")

# Upload via multipart
boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"

def make_multipart_file(filepath, field_name):
    filename = os.path.basename(filepath)
    with open(filepath, "rb") as f:
        file_data = f.read()
    ext = os.path.splitext(filename)[1].lower()
    ctype = "image/png" if ext == ".png" else "image/jpeg"
    part = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
        f"Content-Type: {ctype}\r\n\r\n"
    ).encode() + file_data + b"\r\n"
    return part

body = make_multipart_file(front, "front") + make_multipart_file(back, "back")
body += f"--{boundary}--\r\n".encode()

req = urllib.request.Request(
    f"{API}/scan",
    data=body,
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    },
    method="POST",
)
try:
    resp = urllib.request.urlopen(req)
    scan = json.loads(resp.read())
except urllib.error.HTTPError as e:
    print(f"Scan failed: HTTP {e.code}: {e.read().decode()}")
    sys.exit(1)

print(f"Raw response: {json.dumps(scan)[:500]}")
scan_id = scan.get("id") or scan.get("scan_id")
if not scan_id:
    print(f"No id found in response. Keys: {list(scan.keys())}")
    sys.exit(1)
print(f"\nScan created: {scan_id}")
print(f"Status: {scan['status']}")

# Wait for completion
import time
for i in range(30):
    time.sleep(2)
    detail = api(f"/scan/{scan_id}", token=token)
    if detail and detail["status"] == "COMPLETED":
        break
    if detail:
        print(f"  Status: {detail['status']}...")

if not detail or detail["status"] != "COMPLETED":
    print(f"Scan did not complete. Final status: {detail['status'] if detail else 'unknown'}")
    sys.exit(1)

print(f"\n=== Scan Result ===")
print(f"Overall: {detail['overall_status']}")
print(f"Images: {len(detail['images'])}")
for img in detail["images"]:
    print(f"  {img.get('label', '?')}: {img['url']}")
print(f"\nDeclarations ({len(detail['compliance_results'])}):")
for d in detail["compliance_results"]:
    val = d.get("extracted_value")
    if isinstance(val, dict):
        val_str = json.dumps(val)
    elif isinstance(val, list):
        val_str = f"[{len(val)} items]"
    else:
        val_str = str(val)
    print(f"  {d['field_name']}: {d['verdict']} (conf={d['confidence']}) val={val_str[:100]}")
