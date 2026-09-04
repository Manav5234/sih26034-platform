# SIH26034 — API Contract (Phase 1)

All endpoints return JSON unless noted. List endpoints support `limit` (1–100, default 20) and `offset` (default 0) query params.

---

## `GET /health`

**Response 200**
```json
{ "status": "ok", "service": "sih26034-backend" }
```

---

## `POST /scan`

Upload images and start a new scan.

**Request** — `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `images` | file[] | yes | One or more product images |

**Response 201**
```json
{
  "scan_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "PENDING"
}
```

---

## `GET /scan/{id}`

**Response 200**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "product_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "COMPLETED",
  "images": [
    {
      "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "url": "/images/example-front.jpg",
      "uploaded_at": "2026-09-03T12:00:00Z"
    }
  ],
  "image_quality": {
    "blur": "low",
    "glare": "none",
    "perspective": "slight_tilt",
    "resolution": "300dpi",
    "recommended_action": "proceed"
  },
  "compliance_results": [
    {
      "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
      "scan_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "field_name": "mrp",
      "extracted_value": { "amount": 499.0, "currency": "INR" },
      "evidence": [
        {
          "id": "d4e5f6a7-b8c9-0123-defa-234567890123",
          "source_type": "OCR",
          "raw_text": "MRP Rs. 499.00",
          "confidence": 0.92,
          "image_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
          "bbox": { "x": 120.0, "y": 45.0, "width": 200.0, "height": 30.0 },
          "preprocessing_variant": "crop_2_denoised",
          "extracted_at": "2026-09-03T12:00:00Z"
        }
      ],
      "rule_id": "LMR-2024-001",
      "verdict": "SATISFIED",
      "reason": "MRP value matches the declared amount on the package label.",
      "confidence": 0.92,
      "officer_correction": null
    }
  ],
  "overall_status": "SATISFIED",
  "warnings": [],
  "created_at": "2026-09-03T12:00:00Z"
}
```

---

## `POST /scan/{id}/images`

**Request** — `multipart/form-data`

| Field | Type | Required |
|-------|------|----------|
| `images` | file[] | yes |

**Response 201**
```json
{ "image_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901" }
```

---

## `POST /scan/{id}/reanalyze`

**Response 202**
```json
{
  "scan_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "PROCESSING"
}
```

---

## `GET /scan/{id}/evidence`

**Response 200**
```json
[
  {
    "declaration_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
    "field_name": "mrp",
    "evidence": [
      {
        "id": "d4e5f6a7-b8c9-0123-defa-234567890123",
        "source_type": "OCR",
        "raw_text": "MRP Rs. 499.00",
        "confidence": 0.92,
        "image_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
        "bbox": { "x": 120.0, "y": 45.0, "width": 200.0, "height": 30.0 },
        "preprocessing_variant": "crop_2_denoised",
        "extracted_at": "2026-09-03T12:00:00Z"
      }
    ]
  }
]
```

---

## `GET /scan/{id}/compliance`

**Response 200**
```json
{
  "declarations": [
    {
      "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
      "scan_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "field_name": "mrp",
      "extracted_value": { "amount": 499.0, "currency": "INR" },
      "evidence": [],
      "rule_id": "LMR-2024-001",
      "verdict": "SATISFIED",
      "reason": "MRP value matches the declared amount on the package label.",
      "confidence": 0.92,
      "officer_correction": null
    }
  ],
  "overall_status": "SATISFIED"
}
```

---

## `POST /inspection`

**Request** — `application/json`
```json
{
  "scan_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "officer_id": "e5f6a7b8-c9d0-1234-efab-345678901234",
  "actions": [
    {
      "declaration_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
      "action": "confirm",
      "old_value": { "amount": 499.0, "currency": "INR" },
      "new_value": null,
      "reason": "Verified against physical label."
    }
  ],
  "notes": "Routine inspection — all clear."
}
```

**Response 201**
```json
{
  "id": "f6a7b8c9-d0e1-2345-fabc-456789012345",
  "scan_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "officer_id": "e5f6a7b8-c9d0-1234-efab-345678901234",
  "actions": [
    {
      "declaration_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
      "action": "confirm",
      "old_value": { "amount": 499.0, "currency": "INR" },
      "new_value": null,
      "reason": "Verified against physical label."
    }
  ],
  "notes": "Routine inspection — all clear.",
  "created_at": "2026-09-03T12:00:00Z"
}
```

---

## `GET /inspections`

**Query params:** `officer_id?`, `scan_id?`, `date_from?`, `date_to?`, `limit=20`, `offset=0`

**Response 200**
```json
[
  {
    "id": "f6a7b8c9-d0e1-2345-fabc-456789012345",
    "scan_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "officer_id": "e5f6a7b8-c9d0-1234-efab-345678901234",
    "actions": [
      {
        "declaration_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
        "action": "confirm",
        "old_value": { "amount": 499.0, "currency": "INR" },
        "new_value": null,
        "reason": "Verified against physical label."
      }
    ],
    "notes": "Routine inspection — all clear.",
    "created_at": "2026-09-03T12:00:00Z"
  }
]
```

---

## `GET /products`

**Query params:** `name?`, `brand?`, `barcode?`, `category?`, `status?`, `limit=20`, `offset=0`

**Response 200**
```json
[
  {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "identity": "SKU-12345",
    "brand": "FreshHarvest",
    "category": "Packaged Food",
    "manufacturer": "FreshHarvest Pvt Ltd",
    "packer": "FreshHarvest Pvt Ltd",
    "importer": null,
    "country_of_origin": "India",
    "quantity": { "value": 500.0, "unit": "g" },
    "mrp": { "amount": 499.0, "currency": "INR" },
    "dates": { "manufacture": "2025-01-15", "best_before": "2026-01-15", "use_by": null },
    "consumer_care": "Store in a cool, dry place.",
    "unit_sale_price": { "amount": 449.0, "currency": "INR" },
    "barcode": { "code": "8901234567890", "format": "EAN13" },
    "declarations": [],
    "evidence": [],
    "created_at": "2026-09-03T12:00:00Z",
    "updated_at": "2026-09-03T12:00:00Z"
  }
]
```

---

## `GET /products/{id}`

**Response 200** — same object as above (single product, with declarations and evidence populated).

---

## `GET /dashboard`

**Response 200**
```json
{
  "total_scans": 1247,
  "violations": 38,
  "not_verified_rate": 0.052,
  "recent_inspections": [
    {
      "id": "f6a7b8c9-d0e1-2345-fabc-456789012345",
      "scan_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "officer_id": "e5f6a7b8-c9d0-1234-efab-345678901234",
      "actions": [],
      "notes": "Routine inspection — all clear.",
      "created_at": "2026-09-03T12:00:00Z"
    }
  ]
}
```

---

## `GET /rules`

**Query params:** `effective_date?` (date)

**Response 200**
```json
{
  "id": "12345678-abcd-ef01-2345-6789abcdef01",
  "source": "Legal Metrology Act, 2009",
  "rule_version": "2024.1",
  "effective_from": "2024-01-01",
  "effective_to": null,
  "jurisdiction": "India",
  "rules": [
    {
      "rule_id": "LMR-2024-001",
      "source_document": "Legal Metrology Act, 2009",
      "clause": "Rule 5",
      "applicability": "All pre-packaged goods",
      "required_declaration": "mrp",
      "validation_conditions": { "type": "number", "min": 0 },
      "measurement_requirements": null,
      "exceptions": ["Exempt for export goods"],
      "effective_date": "2024-01-01",
      "evidence_requirements": ["OCR", "BARCODE"]
    }
  ]
}
```

---

## `POST /reports/{id}/pdf`

**Response 200** — `application/pdf` (binary stream)

## `POST /reports/{id}/docx`

**Response 200** — `application/vnd.openxmlformats-officedocument.wordprocessingml.document` (binary stream)

---

## `POST /auth/login`

**Request** — `application/json`
```json
{ "email": "priya.sharma@example.gov.in", "password": "secret123" }
```

**Response 200**
```json
{
  "token": "eyJhbGciOiJIUzI1NiJ9.fake.token",
  "officer": {
    "id": "e5f6a7b8-c9d0-1234-efab-345678901234",
    "role": "INSPECTOR"
  }
}
```
