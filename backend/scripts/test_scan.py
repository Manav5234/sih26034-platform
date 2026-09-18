"""Test scan endpoint error handling."""
import urllib.request
import urllib.error
import json

print("=== Test: POST /scan without files ===")
url = 'http://localhost:8000/scan'
req = urllib.request.Request(url, data=b'', method='POST')
try:
    r = urllib.request.urlopen(req)
    body = r.read().decode()
    print(f"Status: {r.status}")
    print(f"Response: {body[:200]}")
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"Error {e.code}: {body[:300]}")
    # Check if the error message is properly formatted (string, not object)
    try:
        data = json.loads(body)
        detail = data.get('detail', 'N/A')
        print(f"JSON detail: {detail[:100] if detail else 'None'}")
        # Check if it's a string or object
        print(f"Detail is string: {isinstance(detail, str)}")
        print(f"Detail is list: {isinstance(detail, list)}")
    except Exception as ex:
        print(f"Not valid JSON: {ex}")