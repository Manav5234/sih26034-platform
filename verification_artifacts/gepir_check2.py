"""GS1 Gepir reachability with browser UA."""
import sys, os, time, json, re, urllib.request
sys.path.insert(0, "/app")

url = "https://gepir.gs1.org/index.php/search-by-gtin?q=0049000042566"
try:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    })
    start = time.time()
    resp = urllib.request.urlopen(req, timeout=15)
    html = resp.read().decode("utf-8", errors="replace")
    elapsed = time.time() - start
    print(f"HTTP status: {resp.status}")
    print(f"Response length: {len(html)} bytes ({elapsed:.2f}s)")
    
    title_m = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
    if title_m:
        print(f"Page title: {title_m.group(1)}")
    
    for keyword in ["Coca", "company", "Company", "manufacturer", "Manufacturer", "GEPIR", "GTIN"]:
        idx = html.lower().find(keyword.lower())
        if idx >= 0:
            context = html[max(0, idx - 80):idx + 120]
            context_clean = re.sub(r"<[^>]+>", " ", context)
            context_clean = re.sub(r"\s+", " ", context_clean).strip()
            print(f"  Found '{keyword}' at {idx}: ...{context_clean[:120]}...")

except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
