"""Quick smoke test: POST /scan with synthetic product images."""
import json
import urllib.request
import io
import cv2
import numpy as np

BASE = "http://localhost:8000"

# 1) Login
data = json.dumps({"email": "admin@sih26034.local", "password": "admin123"}).encode()
req = urllib.request.Request(f"{BASE}/auth/login", data=data, headers={"Content-Type": "application/json"})
resp = urllib.request.urlopen(req)
token = json.loads(resp.read())["token"]
print("LOGIN OK")

# 2) Create a synthetic product label image
img = np.ones((400, 800, 3), dtype=np.uint8) * 255
cv2.putText(img, "TEST PRODUCT", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0, 0, 0), 4)
cv2.putText(img, "MRP Rs 199.00", (50, 180), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 3)
cv2.putText(img, "Net Qty: 500 g", (50, 250), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 2)
cv2.putText(img, "Mfg: 2025-01-15", (50, 310), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
_, front_buf = cv2.imencode(".png", img)
_, back_buf = cv2.imencode(".png", img)

# 3) Build multipart/form-data
boundary = "----TestBoundary"
parts = []
for name in ("front", "back"):
    img_bytes = front_buf.tobytes() if name == "front" else back_buf.tobytes()
    parts.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{name}"; filename="{name}.png"\r\n'
        f"Content-Type: image/png\r\n\r\n".encode() + img_bytes + b"\r\n"
    )
body = b"".join(parts) + f"--{boundary}--\r\n".encode()

req = urllib.request.Request(
    f"{BASE}/scan",
    data=body,
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    },
)
try:
    resp = urllib.request.urlopen(req)
    result = json.loads(resp.read())
    print(f"SCAN OK — status={resp.status}, scan_id={result.get('scan_id', 'N/A')}")
except urllib.error.HTTPError as e:
    print(f"SCAN FAILED — status={e.code}")
    print(e.read().decode()[:2000])
