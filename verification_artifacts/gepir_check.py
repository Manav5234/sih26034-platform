"""GS1 Gepir reachability diagnosis."""
import sys, os, time, json, re, urllib.request
sys.path.insert(0, "/app")

url = "https://gepir.gs1.org/index.php/search-by-gtin?q=0049000042566"
try:
    req = urllib.request.Request(url, headers={
        "User-Agent": "SIH26034-LegalMetrology/1.0",
        "Accept": "text/html",
    })
    start = time.time()
    resp = urllib.request.urlopen(req, timeout=15)
    html = resp.read().decode("utf-8", errors="replace")
    elapsed = time.time() - start
    print(f"HTTP status: {resp.status}")
    print(f"Response length: {len(html)} bytes ({elapsed:.2f}s)")
    
    # Show a snippet to understand the page structure
    # Find title or h1
    title_m = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
    if title_m:
        print(f"Page title: {title_m.group(1)}")
    
    # Check for any company-related content
    for keyword in ["Coca", "company", "Company", "manufacturer", "Manufacturer", "GEPIR", "GTIN"]:
        idx = html.lower().find(keyword.lower())
        if idx >= 0:
            context = html[max(0, idx - 80):idx + 120]
            # Clean HTML tags for readability
            context_clean = re.sub(r"<[^>]+>", " ", context)
            context_clean = re.sub(r"\s+", " ", context_clean).strip()
            print(f"  Found '{keyword}' at {idx}: ...{context_clean[:120]}...")
    
    # Check for patterns
    company_patterns = [
        r"<td[^>]*class=\"[^\"]*company[^\"]*\"[^>]*>([^<]+)</td>",
        r'"companyName"\s*:\s*"([^"]+)"',
        r'class="[^\"]*result[^\"]*"',
    ]
    for p in company_patterns:
        m = re.search(p, html, re.IGNORECASE)
        print(f"  Pattern match: {'yes' if m else 'no'}")
        if m:
            print(f"    Matched: {m.group(0)[:100]}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
