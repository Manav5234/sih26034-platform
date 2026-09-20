# Packaged-label evaluation and regression suite

This directory is the living regression suite for SIH26034's packaged-product OCR and Legal Metrology compliance pipeline.

## Scope of the measurement

The evaluator calls the production `app.pipeline.run_pipeline()` directly. It does not start FastAPI and does not change OCR, extraction, fusion, or rule-engine behavior.

A case can contain one photo or the real front/back pair used by `/scan`:

```json
"images": [
  {"filename": "031_front.jpg", "label": "front"},
  {"filename": "031_back.jpg", "label": "back"}
]
```

All panel images belonging to the same case are inserted into one scan and passed to the production multi-image pipeline. This exercises panel-aware extraction and fusion instead of reducing a real two-photo scan to a single image.

The labeled measurement fields are:

- `mrp`
- `net_quantity`
- `manufacture_date`
- `expiry_date`

The overall compliance metric is **intentionally scoped to those four fields**. The production ruleset also contains `manufacturer`, `nutrition_facts`, and `cautions`; those are not silently folded into the overall score because this evaluation ground truth does not label all of them. The raw production `pipeline_overall` value is retained per case for diagnostics, but it is not compared with the four-field overall ground truth.

## Metrics

### OCR accuracy

For every declaration whose ground truth text is visible, the evaluator captures **all OCR lines returned by the production `_ocr_with_recrop()` stage before field extraction**. It then scores the best-aligned OCR window against the human-written `ocr_text` target.

This keeps OCR quality separate from extraction: an extractor can select the wrong field or fail to extract a value even when the OCR output contains the correct text.

The report includes:

- OCR accuracy: percentage of visible field targets whose numeric tokens match exactly and whose non-numeric text reaches the configured 0.85 RapidFuzz partial-match threshold.
- OCR similarity: mean similarity of the best aligned full-text window, derived as `1 - CER`.
- OCR CER: mean character error rate on the best aligned full-text window.

Numeric tokens are a hard requirement within the aligned declaration window. Extra numbers elsewhere on the same OCR line are allowed, so a line such as `MFD 01/2025 EXP 01/2026` can still match the `01/2025` target. A substitution such as `₹280` for `₹200` cannot pass merely because the surrounding words are similar. `₹`, `Rs`, and `INR` are normalized to the same currency token.

### Field extraction accuracy

For visible declarations, the extracted structured value must match the hand-written expected value. MRP is compared numerically; net quantity reuses the production `fusion._normalize_net_quantity()` conversion so `1 kg` and `1000 g` are equivalent within the production's 1% tolerance; dates are compared by day/month/year at the precision represented by the ground truth.

A missed extraction counts as incorrect. Hidden text is excluded from the value-accuracy denominator rather than being treated as an OCR failure.

### Compliance-state accuracy

Each field compares the production declaration verdict with the hand-written expected state. All five production states are supported:

```text
SATISFIED
VIOLATION
NOT_VERIFIED
CONFLICT
NOT_APPLICABLE
```

### `NOT_VERIFIED` rate

Three numbers are reported so correct abstentions do not look like failures:

- `NOT_VERIFIED` across all four field states.
- `NOT_VERIFIED` on visible fields (the useful error/abstention signal).
- `NOT_VERIFIED` on non-visible fields (usually the correct behavior).

### False `VIOLATION`

Both field-level and case-level rates are reported. The case-level rate uses the four-field overall state because that is closest to what an officer sees for a scan.

### Overall accuracy and baseline

Overall accuracy is exact agreement between expected and predicted four-field scoped overall state. The report also shows the majority-class baseline and a 5x5 overall confusion matrix.

## Provider reproducibility

The production pipeline calls external product providers when it decodes a barcode. The evaluator therefore has three modes:

```bash
docker compose run --rm --build -v "./docs:/docs" backend python scripts/evaluate.py --provider-mode disabled
docker compose run --rm --build -v "./docs:/docs" backend python scripts/evaluate.py --provider-mode fixture
docker compose run --rm --build -v "./docs:/docs" backend python scripts/evaluate.py --provider-mode live
```

`disabled` is the default and is the recommended OCR/extraction/rules regression mode. Because provider evidence is absent, MRP/net-quantity `CONFLICT` cases cannot occur in this mode; this is stated explicitly in the output.

`fixture` uses `provider_fixtures.json` so provider-backed conflict/agreement cases can be tested deterministically without a network dependency.

`live` is for diagnostics only. Third-party availability, rate limits, and catalog changes can alter results.

## Running the evaluator

The supported repeatable path is the Docker backend. The backend image supplies the application's Python/OCR dependencies (including the small `rapidfuzz` evaluation dependency) and the Compose service supplies PostgreSQL and the `/data/uploads` volume.

Start PostgreSQL and apply the current schema and seed data:

```bash
docker compose up -d postgres
docker compose run --rm --build backend alembic upgrade head
docker compose run --rm --build backend python scripts/seed.py
```

Wait for PostgreSQL to accept connections before running the migration command if it was just started.

Run the evaluator with the dataset mounted into the backend container. Pass Git provenance from the host because the slim backend image does not contain the repository's `.git` directory or the `git` executable:

```bash
GIT_SHA="$(git rev-parse HEAD)"
GIT_DIRTY="$([ -n "$(git status --porcelain --untracked-files=all)" ] && echo true || echo false)"
docker compose run --rm --build \
  -e GIT_SHA="$GIT_SHA" \
  -e GIT_DIRTY="$GIT_DIRTY" \
  -v "$PWD/docs:/docs" \
  backend python scripts/evaluate.py
```

On Windows PowerShell, the equivalent provenance setup is:

```powershell
$env:GIT_SHA = git rev-parse HEAD
$env:GIT_DIRTY = if (git status --porcelain --untracked-files=all) { "true" } else { "false" }
docker compose run --rm --build `
  -e GIT_SHA=$env:GIT_SHA `
  -e GIT_DIRTY=$env:GIT_DIRTY `
  -v "${PWD}/docs:/docs" `
  backend python scripts/evaluate.py
```

A host-only run is possible only when the same application environment is configured locally, including `DATABASE_URL`, `JWT_SECRET`, OCR system dependencies, and a writable `/data/uploads` directory. The script deliberately fails early otherwise because the production resolver is hard-coded to `/data/uploads`.

Results are written to `docs/evaluation/results/latest.json` on the host through the mounted `/docs` directory. The generated file is ignored by Git.

## Baselines and regression detection

After the suite contains at least 30 verified cases and you have reviewed a complete deterministic run, create a baseline:

```bash
GIT_SHA="$(git rev-parse HEAD)"
GIT_DIRTY="$([ -n "$(git status --porcelain --untracked-files=all)" ] && echo true || echo false)"
docker compose run --rm --build \
  -e GIT_SHA="$GIT_SHA" -e GIT_DIRTY="$GIT_DIRTY" \
  -v "$PWD/docs:/docs" \
  backend python scripts/evaluate.py \
  --provider-mode disabled \
  --update-baseline /docs/evaluation/baseline.json
```

Review the generated baseline and commit it. Full-suite baseline comparison is strict by default: a current verified case missing from the baseline, or a baseline case missing from the current run, is a failure. This prevents silently deleting a regression case from `ground_truth.json`.

For CI/regression runs:

```bash
docker compose run --rm --build \
  -e GIT_SHA="$(git rev-parse HEAD)" \
  -e GIT_DIRTY="$([ -n "$(git status --porcelain --untracked-files=all)" ] && echo true || echo false)" \
  -v "$PWD/docs:/docs" \
  backend python scripts/evaluate.py \
  --provider-mode disabled \
  --baseline /docs/evaluation/baseline.json
```

When a newly verified regression case is being added, temporarily use `--allow-incomplete-baseline` so the new case does not fail the baseline comparison while you review it. Do not use that flag for normal CI.

To inspect one verified case against the baseline, use:

```bash
docker compose run --rm --build -v "$PWD/docs:/docs" backend python scripts/evaluate.py \
  --case 031 \
  --provider-mode disabled \
  --baseline /docs/evaluation/baseline.json
```

A case with `expected_fail` is reported as **XFAIL** when its known failing field still fails and as **XPASS** when it unexpectedly passes. XFAIL fields are excluded from normal accuracy aggregates and baseline regression checks. XPASS is reported separately and causes a non-zero exit so the team must review the case and remove/update the `expected_fail` declaration deliberately.

The command also exits non-zero for execution errors, true baseline regressions, aggregate accuracy drops, increased false-violation or visible-field `NOT_VERIFIED` rates, and unbaselined/missing cases in strict full-suite mode.

The baseline stores run time, Git SHA, Git dirty state, provider mode, inspection date, aggregate summary, and per-case results. If Git provenance cannot be recovered, the evaluator records `git_sha: "unknown"` and `git_dirty: null`, never pretending an unknown tree is clean.

## Hand-verified case schema

Each case requires a human verifier and a reproducible source record:

```json
{
  "id": "031",
  "images": [
    {"filename": "031_front.jpeg", "label": "front"},
    {"filename": "031_back.jpeg", "label": "back"}
  ],
  "hand_verified": true,
  "verified_by": "initials-or-team-id",
  "verified_on": "2026-09-19",
  "conditions": ["pouch", "glare", "hindi_english_mixed"],
  "ground_truth": {
    "mrp": {
      "visible": true,
      "value": {"amount": 50.0, "currency": "INR"},
      "ocr_text": "MRP ₹50/-"
    },
    "net_quantity": {
      "visible": true,
      "value": {"value": 200.0, "unit": "g"},
      "quantity_scope": "total",
      "ocr_text": "Net Qty 200 g"
    },
    "manufacture_date": {
      "visible": true,
      "value": {"day": null, "month": 6, "year": 2026},
      "ocr_text": "Mfd 06/2026"
    },
    "expiry_date": {
      "visible": false,
      "value": null,
      "ocr_text": null
    }
  },
  "compliance": {
    "mrp": "SATISFIED",
    "net_quantity": "SATISFIED",
    "manufacture_date": "SATISFIED",
    "expiry_date": "NOT_VERIFIED"
  },
  "overall_compliance": "NOT_VERIFIED",
  "source_id": "031"
}
```

For visible text, the human verifier must record the actual structured value and a short target OCR line **from the photograph**, without copying the pipeline output. Numeric characters in that target are treated as substantive. For non-visible text, use `visible: false`; its expected state should normally be `NOT_VERIFIED` or `NOT_APPLICABLE`.

For multipacks, use `quantity_scope` to document the labelling interpretation. `total` means the evaluation target is the declared total contents of the sale unit; `per_unit` means the target is the declared per-unit quantity. The harness uses this value as provenance/documentation and does **not** perform a pack-count conversion. Do not silently convert `4 x 250 g` to `1000 g` (or the reverse) without recording the project policy used for that product.

For known current defects, use an `expected_fail` object keyed by field with a short reason. This documents a known failing regression without weakening the ground truth. Do not change expected values merely to make a failing pipeline pass.

The evaluator verifies that `overall_compliance` equals the severity-derived state of the four labeled declarations, so the overall target cannot drift independently from its fields.

## Adding a regression case

1. Keep the original real photograph(s) exactly as captured. Do not generate a synthetic label or clean up the difficult condition that caused the bug.
2. For a normal scan, add both front and back photographs when both were available. Give each its actual panel label.
3. Add one source entry to `sources.json`. Record author/licence information for redistributed third-party material; for team-shot photos record the photographer/owner and the permission basis agreed by the team.
4. Add a case to `ground_truth.json`, including `verified_by`, `verified_on`, conditions, visible values, OCR target text, compliance states, and the derived overall state. Add `expected_fail` when the case intentionally records a known current defect.
5. Hand-check the values against the original pixels. Do not set `hand_verified: true` until a named human verifier has completed that review.
6. Run the case directly:

```bash
docker compose run --rm --build -v "./docs:/docs" backend python scripts/evaluate.py --case 031
```

7. Once the case is reviewed and accepted, run the full deterministic suite. After fixing a bug, keep the regression case and update the baseline only after reviewing the new behavior.

## Dataset requirements

The acceptance target is at least **30 real, hand-verified cases**, with no upper bound so the suite can keep growing.

Across the living suite, deliberately cover as much of this diversity as practical:

- bottles/cylinders and curved labels
- boxes/cartons
- pouches/flexible plastics
- reflective/foil surfaces
- tiny and dense text
- large front-panel text
- English-only and Hindi/English mixed labels
- rotated/perspective photographs
- glare/reflections
- blur
- low light
- partial occlusion
- multiple MRP layouts
- quantities in g/kg/ml/L
- manufacture and expiry/best-before variants
- both fully visible and genuinely non-visible declarations
- real violations/conflicts where the source photograph supports the expected state

Publicly redistributable photos can be used when their licence permits it, but team-shot product photographs are preferred for the difficult-condition coverage because their capture conditions are controllable and representative of the product users actually submit.

## Current dataset status

The evaluation dataset currently contains **36 real product-label cases**, of which **34 are hand-verified** and **2 historical cases remain pending review**. The verified cases therefore exceed the minimum acceptance target of 30 hand-verified cases.

All verified cases have corresponding photographs in `images/` and source records in `sources.json`. Cases may contain a single photograph or a real front/back pair; a back-only or front-only case is valid when that is the photograph available for the product.

The current measurement set covers packaged food, beverages, household products, personal-care/cosmetic products, and other pre-packaged goods, with variation in packaging, label layout, text size, glare, perspective, and visible/non-visible declarations.

The baseline should be created only after a complete deterministic evaluator run has been reviewed.

## Dataset policy for multipacks and violations

For this evaluation suite, multipack net-quantity ground truth represents the **total quantity of the sale unit**. Record this interpretation with `"quantity_scope": "total"` in the ground truth. The harness uses this value as provenance/documentation and does **not** perform a pack-count conversion.

A real `VIOLATION` case should only be labeled when the photograph supports the offending declaration and the expected rule outcome is known. A missing or unreadable field should remain `NOT_VERIFIED`, not be upgraded to `VIOLATION` merely because the pipeline could not extract it.

## Licensed-source helper

`backend/scripts/fetch_evaluation_candidates.py` is only a bootstrap/example convenience for explicitly listed Wikimedia Commons sources. It downloads the **original** image, records author/licence metadata from Commons, persists progress after each source, and never marks a case as hand-verified. **Do not treat running this helper as satisfying the dataset requirement.** It is not a substitute for collecting representative Indian front/back photos, especially for controlled difficult conditions such as glare, blur, low light, curved surfaces and occlusion.
