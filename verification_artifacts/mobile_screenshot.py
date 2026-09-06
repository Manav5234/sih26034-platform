from playwright.sync_api import sync_playwright
import os, time, json, urllib.request

os.makedirs("/tmp/mobile_screenshots", exist_ok=True)

# Get JWT token directly from backend
login_data = json.dumps({"email": "admin@sih26034.local", "password": "admin123"}).encode()
req = urllib.request.Request("http://localhost:8000/auth/login", data=login_data, headers={"Content-Type": "application/json"})
resp = urllib.request.urlopen(req)
token = json.loads(resp.read())["token"]
print(f"Got token: {token[:30]}...")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu"])
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        device_scale_factor=2,
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"
    )
    page = context.new_page()

    # First visit frontend to set the cookie
    page.goto("http://frontend:3000/login", wait_until="networkidle")
    
    # Set the JWT cookie via the API route
    page.evaluate(f"""async () => {{
        await fetch("/api/auth/login", {{
            method: "POST",
            headers: {{"Content-Type": "application/json"}},
            body: JSON.stringify({{token: "{token}"}}),
        }});
    }}""")
    time.sleep(1)

    # Now navigate to dashboard (cookie is set, server-side should accept it)
    page.goto("http://frontend:3000/dashboard", wait_until="networkidle")
    time.sleep(2)
    print(f"After dashboard nav: {page.url}")

    # Screenshot 1: Dashboard
    page.screenshot(path="/tmp/mobile_screenshots/mobile_dashboard.png", full_page=True)
    print(f"Screenshot 1: dashboard ({page.url})")

    # Screenshot 2: Products
    page.goto("http://frontend:3000/products", wait_until="networkidle")
    time.sleep(1)
    page.screenshot(path="/tmp/mobile_screenshots/mobile_products.png", full_page=True)
    print(f"Screenshot 2: products ({page.url})")

    # Screenshot 3: Scans
    page.goto("http://frontend:3000/scans", wait_until="networkidle")
    time.sleep(1)
    page.screenshot(path="/tmp/mobile_screenshots/mobile_scans.png", full_page=True)
    print(f"Screenshot 3: scans ({page.url})")

    browser.close()
    print("Done.")
