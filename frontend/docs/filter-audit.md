# Filter Audit — Frontend vs Backend Query Parameter Coverage

## Methodology

Every query parameter listed below was verified by reading the actual function
signatures in `backend/app/main.py` (the `list_*` route handlers), NOT assumed
from documentation or prior knowledge.

---

## GET /scans

**Backend params** (`main.py:470-478`):
| Param | Type | Backend supports | Frontend wired |
|-------|------|-----------------|----------------|
| `status` | `str \| None` | Yes | Yes |
| `date_from` | `date \| None` | Yes | Yes |
| `date_to` | `date \| None` | Yes | Yes |
| `officer_id` | `UUID \| None` | Yes | **No** |
| `barcode` | `str \| None` | Yes | Yes |
| `page` | `int` (default 1) | Yes | Yes |
| `page_size` | `int` (default 20) | Yes | Yes |

**Gap**: `officer_id` is supported by the backend but not wired in the frontend
scans page. This is a minor gap — most officers only see their own scans, but
an admin might want to filter by officer.

---

## GET /products

**Backend params** (`main.py:789-795`):
| Param | Type | Backend supports | Frontend wired |
|-------|------|-----------------|----------------|
| `search` | `str \| None` | Yes (ILIKE on identity/brand/manufacturer) | Yes |
| `brand` | `str \| None` | Yes | Yes |
| `category` | `str \| None` | Yes | Yes |
| `page` | `int` (default 1) | Yes | Yes |
| `page_size` | `int` (default 20) | Yes | Yes |

**All backend-supported filters are already wired.** The response payload
includes `barcode_code`, `latest_scan_status`, and `created_at`, but these
are NOT filterable server-side — no matching query params exist in
`list_products()`.

**Missing backend params that would be useful**:
- `barcode` — filter on `ProdDB.barcode_code` (exact or ILIKE match)
- `compliance_status` — filter on the latest scan's `overall_status` via
  a subquery joining `ScanDB` → `ProdDB`
- `manufacturer` — filter on `ProdDB.manufacturer` (currently only accessible
  via the `search` param which also matches identity and brand)
- `date_from` / `date_to` — filter on `ProdDB.created_at` or latest scan date

---

## GET /flags

**Backend params** (`main.py:1107-1111`):
| Param | Type | Backend supports | Frontend wired |
|-------|------|-----------------|----------------|
| `status` | `str \| None` | Yes | Yes (as tab links) |
| `page` | `int` (default 1) | Yes | Yes |
| `page_size` | `int` (default 20) | Yes | Yes |

**All backend-supported filters are already wired.** The flags endpoint has
almost no filter params beyond `status`.

**Missing backend params that would be useful**:
- `date_from` / `date_to` — filter on `ConsumerFlagDB.created_at` (requires
  a join through `scan_id` → product to support product/brand/manufacturer/
  barcode/category filters)
- `scan_id` — filter flags for a specific scan
- `product_name` / `brand` / `manufacturer` / `barcode` / `category` — all
  require joining `ConsumerFlagDB.scan_id` → `ScanDB.product_id` → `ProdDB`
  and filtering on product fields

---

## GET /inspections

**Backend params**: `status`, `officer_id`, `scan_id`, `date_from`, `date_to`
**Frontend page**: Does NOT exist yet. No audit needed on the frontend side.

---

## GET /rules

**Backend params**: `effective_date: date | None`
**Frontend page**: Created as part of this task. The endpoint is currently a
stub (always returns 404). The frontend handles this gracefully with an empty
state message.

---

## Summary

| Endpoint | Backend params | Frontend wired | Gap |
|----------|---------------|----------------|-----|
| GET /scans | 5 (+ pagination) | 4 of 5 | `officer_id` |
| GET /products | 3 (+ pagination) | 3 of 3 | All wired |
| GET /flags | 1 (+ pagination) | 1 of 1 | All wired |
| GET /inspections | 5 (+ pagination) | N/A (no page) | N/A |
| GET /rules | 1 | 1 of 1 | Endpoint is stub |

**Key finding**: All backend-supported filters are already wired in the
frontend. The gaps are entirely on the backend side — the backend doesn't
yet expose the additional query params needed for the full required filter
set (product name, brand, manufacturer, barcode, category, compliance status,
date, inspection status across all endpoints).

**DO NOT fake client-side filtering** to fill these gaps. These pages use
real server-side pagination with a `total` count. Client-side filtering on
a 20-item page would show incomplete results with a misleading total.

### Backend work needed (for whoever picks this up)

**GET /products** — add query params:
- `barcode: str | None` — `ProdDB.barcode_code.ilike(f"%{barcode}%")`
- `manufacturer: str | None` — `ProdDB.manufacturer.ilike(f"%{manufacturer}%")`
- `compliance_status: str | None` — subquery joining latest scan
  `ScanDB.overall_status` for the product
- `date_from: date | None` / `date_to: date | None` — filter on
  `ProdDB.created_at`

**GET /scans** — add query params:
- `product_name: str | None` — join through `ScanDB.product_id` →
  `ProdDB.identity` ILIKE
- `brand: str | None` — join through `ScanDB.product_id` → `ProdDB.brand` ILIKE
- `category: str | None` — join through `ScanDB.product_id` →
  `ProdDB.category` ILIKE

**GET /flags** — add query params:
- `date_from: date | None` / `date_to: date | None` — filter on
  `ConsumerFlagDB.created_at`
- `scan_id: UUID | None` — filter on `ConsumerFlagDB.scan_id`
- Product-level filters (brand, manufacturer, barcode, category) require
  joining `ConsumerFlagDB.scan_id` → `ScanDB.product_id` → `ProdDB`
