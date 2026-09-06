"""Multi-source product lookup by barcode.

Tries external adapters in order; stops at first hit.  Results are cached
in the ProductCache table so repeat scans don't re-hit external APIs.

Adapter chain:
  1. OpenFoodFacts  (food/grocery — free, no key)
  2. UPCitemdb      (general products — free tier, 100 req/day)
  3. GS1Gepir       (manufacturer identity only — best-effort, may skip)

OCR remains the primary source of truth.  This module provides SUPPLEMENTARY
cross-checking evidence (product name, brand, quantity, category).
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.request
from datetime import datetime, timezone
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Adapter base
# ---------------------------------------------------------------------------

class _BaseAdapter:
    """Base class for product lookup adapters."""

    name: str = "base"

    def lookup(self, barcode: str) -> dict | None:
        """Return normalized product dict or None if not found.

        Returned dict shape:
            {
                "name": str | None,
                "brand": str | None,
                "category": str | None,
                "manufacturer": str | None,
                "net_quantity": {"value": float, "unit": str} | None,
                "mrp": {"amount": float, "currency": str} | None,
            }
        """
        raise NotImplementedError

    def _get_json(self, url: str, timeout: int = 10) -> dict | None:
        """Fetch JSON from a URL with timeout and error handling."""
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "SIH26034-LegalMetrology/1.0",
                "Accept": "application/json",
                "Accept-Encoding": "identity",
            })
            resp = urllib.request.urlopen(req, timeout=timeout)
            return json.loads(resp.read())
        except Exception as e:
            logger.warning("%s: request failed for %s: %s", self.name, url, e)
            return None

    def _parse_quantity(self, text: str) -> dict | None:
        """Parse '500 g', '250 ml', '1 L' etc. into {"value": float, "unit": str}."""
        if not text:
            return None
        m = re.match(r"([\d.,]+)\s*(g|kg|ml|l|oz|lb|pcs?|pack|unit)s?\b", text.strip(), re.IGNORECASE)
        if m:
            value = float(m.group(1).replace(",", ""))
            unit = m.group(2).lower()
            if unit == "l":
                unit = "l"
            return {"value": value, "unit": unit}
        return None


# ---------------------------------------------------------------------------
# 1. OpenFoodFacts
# ---------------------------------------------------------------------------

class OpenFoodFactsAdapter(_BaseAdapter):
    """Lookup via Open Food Facts API (free, no key, food/grocery focus)."""

    name = "openfoodfacts"

    def lookup(self, barcode: str) -> dict | None:
        data = self._get_json(f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json")
        if not data or data.get("status") != 1:
            logger.info("%s: not found for barcode %s", self.name, barcode)
            return None

        product = data.get("product", {})
        result: dict = {}

        if product.get("product_name"):
            result["name"] = product["product_name"]
        if product.get("brands"):
            result["brand"] = product["brands"]
        if product.get("categories"):
            result["category"] = product["categories"]
        if product.get("manufacturers"):
            result["manufacturer"] = product["manufacturers"]

        # Quantity: Open FoodFacts stores this in "quantity" as a string
        qty = self._parse_quantity(product.get("quantity", ""))
        if qty:
            result["net_quantity"] = qty

        # MRP is not provided by Open FoodFacts (Indian pricing not in their schema)
        logger.info("%s: found for barcode %s — name=%s", self.name, barcode, result.get("name"))
        return result if result else None


# ---------------------------------------------------------------------------
# 2. UPCitemdb
# ---------------------------------------------------------------------------

class UPCitemdbAdapter(_BaseAdapter):
    """Lookup via UPCitemdb free tier (100 req/day, general products)."""

    name = "upcitemdb"

    def lookup(self, barcode: str) -> dict | None:
        api_key = os.environ.get("UPCITEMDB_API_KEY", "")
        if not api_key:
            logger.info("%s: no UPCITEMDB_API_KEY set, skipping", self.name)
            return None

        url = f"https://api.upcitemdb.com/prod/trial/lookup?upc={barcode}"
        try:
            req = urllib.request.Request(url, headers={
                "Accept": "application/json",
                "Authorization": f"key {api_key}",
                "User-Agent": "SIH26034-LegalMetrology/1.0",
            })
            resp = urllib.request.urlopen(req, timeout=10)
            data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 404 or e.code == 400:
                logger.info("%s: not found for barcode %s", self.name, barcode)
                return None
            # Rate limit (429) or server error — log and skip
            logger.warning("%s: HTTP %d for barcode %s", self.name, e.code, barcode)
            return None
        except Exception as e:
            logger.warning("%s: request failed for barcode %s: %s", self.name, barcode, e)
            return None

        items = data.get("items", [])
        if not items:
            logger.info("%s: not found for barcode %s", self.name, barcode)
            return None

        item = items[0]
        result: dict = {}

        if item.get("title"):
            result["name"] = item["title"]
        if item.get("brand"):
            result["brand"] = item["brand"]
        if item.get("category"):
            result["category"] = item["category"]
        if item.get("description"):
            result["manufacturer"] = item["description"]

        # UPCitemdb doesn't provide structured quantity or MRP
        logger.info("%s: found for barcode %s — title=%s", self.name, barcode, item.get("title"))
        return result if result else None


# ---------------------------------------------------------------------------
# 3. GS1Gepir (manufacturer identity only, best-effort)
# ---------------------------------------------------------------------------

class GS1GepirAdapter(_BaseAdapter):
    """Best-effort GS1 GEPIR lookup for manufacturer identity.

    GEPIR's public web interface doesn't expose a clean JSON API.
    This adapter attempts to scrape the company name from the search
    results page as a lower-reliability signal.  If scraping fails
    or the page structure changes, we silently return None.
    """

    name = "gs1gepir"

    def lookup(self, barcode: str) -> dict | None:
        # GS1 GEPIR lookup URL — returns HTML search results
        url = f"https://gepir.gs1.org/index.php/search-by-gtin?q={barcode}"
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "SIH26034-LegalMetrology/1.0",
                "Accept": "text/html",
            })
            resp = urllib.request.urlopen(req, timeout=10)
            html = resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            logger.info("%s: request failed for barcode %s: %s", self.name, barcode, e)
            return None

        # Try to extract company name from GEPIR HTML response
        # GEPIR typically shows the company name in a table or structured element
        # This is best-effort — if page structure changes, we silently skip
        company_match = re.search(
            r'<td[^>]*class="[^"]*company[^"]*"[^>]*>([^<]+)</td>',
            html, re.IGNORECASE
        )
        if not company_match:
            # Try alternate pattern
            company_match = re.search(
                r'"companyName"\s*:\s*"([^"]+)"',
                html, re.IGNORECASE
            )
        if not company_match:
            logger.info("%s: no company found for barcode %s (page structure may have changed)", self.name, barcode)
            return None

        company_name = company_match.group(1).strip()
        if not company_name:
            return None

        logger.info("%s: found company '%s' for barcode %s", self.name, company_name, barcode)
        return {"manufacturer": company_name}


# ---------------------------------------------------------------------------
# Adapter chain + cache
# ---------------------------------------------------------------------------

_ADAPTERS = [OpenFoodFactsAdapter(), UPCitemdbAdapter(), GS1GepirAdapter()]


class ProductLookupAdapter:
    """Multi-source product lookup with caching.

    Drop-in replacement for the old mocked stub.  Calling code (barcode
    service, pipeline) does not need to change.
    """

    @staticmethod
    def lookup(barcode: str, db=None) -> dict | None:
        """Look up product data by barcode.

        Args:
            barcode: The barcode string (EAN13, UPC, etc.)
            db: Optional SQLAlchemy session for cache access.  If None,
                caching is skipped (useful for tests that don't have DB).

        Returns:
            Product data dict or None if not found across all adapters.
        """
        # ── Check cache first ──
        if db is not None:
            try:
                from app.db.models import ProductCache
                cached = db.query(ProductCache).filter(ProductCache.barcode == barcode).first()
                if cached is not None:
                    logger.info("product_cache: cache HIT for barcode %s (adapter=%s)", barcode, cached.adapter)
                    return cached.result  # None means "queried, not found"
            except Exception as e:
                logger.warning("product_cache: cache read failed for barcode %s: %s", barcode, e)

        # ── Try adapters in order ──
        result = None
        found_adapter = None
        for adapter in _ADAPTERS:
            try:
                result = adapter.lookup(barcode)
            except Exception as e:
                logger.warning("adapter %s crashed for barcode %s: %s", adapter.name, barcode, e)
                result = None

            if result is not None:
                found_adapter = adapter.name
                break

        if result is None:
            logger.info("product_lookup: not found across all adapters for barcode %s", barcode)

        # ── Write to cache ──
        if db is not None:
            try:
                from app.db.models import ProductCache
                cache_entry = ProductCache(
                    barcode=barcode,
                    result=result,  # None = not found
                    adapter=found_adapter,
                    fetched_at=datetime.now(timezone.utc),
                )
                db.merge(cache_entry)  # upsert on barcode PK
                db.flush()
            except Exception as e:
                logger.warning("product_cache: cache write failed for barcode %s: %s", barcode, e)

        return result
