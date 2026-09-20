#!/usr/bin/env python3
"""Evaluate packaged-label OCR and compliance against hand-written ground truth.

The evaluator calls the production ``app.pipeline.run_pipeline`` in-process. It
creates isolated database records for each case, uses the production local-storage
adapter, captures the complete OCR output returned by ``_ocr_with_recrop`` before
field extraction, and rolls the transaction back after the case finishes.

Default mode is deterministic: external product-provider lookups are disabled.
Use ``--provider-mode fixture`` for deterministic provider-backed cases or
``--provider-mode live`` only for diagnostics; live provider runs are unsuitable
for regression numbers.

The normal full-suite command requires at least 30 hand-verified cases. Pending cases are skipped and reported. Use ``--case CASE_ID`` for one verified case while debugging, or lower the requirement explicitly with ``--min-cases`` for a local partial suite.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import traceback
import uuid
from typing import Any, Iterator

from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent

# In the production Docker image, only backend/ is copied to /app. The
# evaluation dataset is supplied separately at /docs/evaluation. On a host
# checkout, it lives at <repo>/docs/evaluation.
REPO_EVAL_ROOT = REPO_ROOT / "docs/evaluation"
CONTAINER_EVAL_ROOT = Path("/docs/evaluation")
DEFAULT_EVAL_ROOT = REPO_EVAL_ROOT if REPO_EVAL_ROOT.exists() else CONTAINER_EVAL_ROOT

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy.orm import Session  # noqa: E402

import app.pipeline as pipeline_module  # noqa: E402
from app.database import engine  # noqa: E402
from app.db.models import Image as ImageDB  # noqa: E402
from app.db.models import Scan as ScanDB  # noqa: E402
from app.db.models import ScanStatus  # noqa: E402
from app.fusion import _NUMERIC_TOLERANCE, _normalize_net_quantity  # noqa: E402
from app.pipeline import run_pipeline  # noqa: E402
from app.product_lookup import ProductLookupAdapter  # noqa: E402
from app.storage import storage  # noqa: E402


FIELDS = ("mrp", "net_quantity", "manufacture_date", "expiry_date")
STATES = (
    "SATISFIED",
    "VIOLATION",
    "NOT_VERIFIED",
    "CONFLICT",
    "NOT_APPLICABLE",
)
PANEL_LABELS = {"front", "back"}
OCR_ACCURACY_THRESHOLD = 0.85
OCR_TEXT_ACCURACY_THRESHOLD = 85.0
OCR_SCORE_EPSILON = 0.01
REGRESSION_EPSILON = 0.001


EXPECTED_FAIL_CHECKS = ("ocr", "field", "state")

# Match the production rule-engine severity ordering without importing a private
# helper. Overall ground truth is deliberately scoped to the four declarations
# this evaluation suite labels, rather than unrelated seeded rules.
_SEVERITY = {
    "VIOLATION": 0,
    "CONFLICT": 1,
    "NOT_VERIFIED": 2,
    "SATISFIED": 3,
    "NOT_APPLICABLE": 4,
}


def _normalise_date(value: Any) -> tuple[int | None, int, int] | None:
    if value is None or not isinstance(value, dict):
        return None
    nested = value.get("value", value)
    if not isinstance(nested, dict):
        return None
    try:
        return nested.get("day"), int(nested["month"]), int(nested["year"])
    except (KeyError, TypeError, ValueError):
        return None


def _normalise_money(value: Any) -> tuple[float, str] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        return None
    try:
        return round(float(value["amount"]), 2), str(value.get("currency", "INR")).upper()
    except (KeyError, TypeError, ValueError):
        return None


def _quantity_matches(actual: Any, expected: Any) -> bool:
    if actual is None or expected is None:
        return actual is expected
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    try:
        actual_value = float(actual["value"])
        expected_value = float(expected["value"])
        actual_unit = str(actual["unit"])
        expected_unit = str(expected["unit"])
    except (KeyError, TypeError, ValueError):
        return False

    actual_norm = _normalize_net_quantity(actual_value, actual_unit)
    expected_norm = _normalize_net_quantity(expected_value, expected_unit)
    if actual_norm == expected_norm:
        return True
    if actual_norm == 0 or expected_norm == 0:
        return False
    return abs(actual_norm - expected_norm) / max(actual_norm, expected_norm) <= _NUMERIC_TOLERANCE


def _field_matches(field: str, actual: Any, expected: Any) -> bool:
    if field == "mrp":
        return _normalise_money(actual) == _normalise_money(expected)
    if field == "net_quantity":
        return _quantity_matches(actual, expected)
    if field in {"manufacture_date", "expiry_date"}:
        return _normalise_date(actual) == _normalise_date(expected)
    return actual == expected


def _normalise_ocr_text(value: str | None) -> str:
    """Normalise OCR/ground truth text for semantic comparison.

    Currency spellings are intentionally collapsed (₹ / Rs / INR → rs). OCR
    punctuation and repeated whitespace are not substantive for this metric.
    """
    if not value:
        return ""
    text = value.casefold().replace("₹", " rs ")
    text = re.sub(r"\b(?:inr|rs)\.?\b", " rs ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _digit_tokens(value: str) -> list[str]:
    return re.findall(r"\d+(?:[.,]\d+)?", value)


def _text_without_digits(value: str) -> str:
    return re.sub(r"\d+(?:[.,]\d+)?", " ", _normalise_ocr_text(value)).strip()


def _contains_contiguous_tokens(needle: list[str], haystack: list[str]) -> bool:
    """Return True when the expected digit sequence occurs contiguously.

    Extra numbers outside the aligned declaration (batch number, another
    date, net weight, etc.) are allowed. A number substitution inside the
    aligned declaration is not.
    """
    if not needle:
        return True
    width = len(needle)
    return any(haystack[i : i + width] == needle for i in range(len(haystack) - width + 1))


def _ocr_candidates(lines: list[dict[str, Any]]) -> list[str]:
    texts = [str(line.get("text", "")) for line in lines if line.get("text")]
    candidates = list(texts)
    # Declarations occasionally span two or three OCR lines. Keep this small
    # because RapidFuzz already performs character-level alignment inside each
    # candidate line/window.
    for width in (2, 3):
        for i in range(len(texts) - width + 1):
            candidates.append(" ".join(texts[i : i + width]))
    return candidates


def _best_ocr_alignment(target: str, candidates: list[str]) -> tuple[float, float, str | None, bool, float | None]:
    """Return (similarity, CER, best_window, digit_match, text_similarity).

    The digit test is performed on the *aligned window*, not the entire OCR
    line. This allows legitimate extra numbers (batch numbers, another date,
    net quantity) while still making substitutions such as 200→100 a hard
    OCR failure.
    """
    target_norm = _normalise_ocr_text(target)
    target_digits = _digit_tokens(target_norm)
    target_text = _text_without_digits(target_norm)
    if not target_norm:
        return 0.0, 1.0, None, False, None

    best_rank = (-1, -1.0, -1.0)
    best_similarity = 0.0
    best_cer = 1.0
    best_window: str | None = None
    best_digit_match = False
    best_text_similarity: float | None = None

    for candidate in candidates:
        candidate_norm = _normalise_ocr_text(candidate)
        if not candidate_norm:
            continue

        alignment = fuzz.partial_ratio_alignment(target_norm, candidate_norm)
        window = candidate_norm[alignment.dest_start : alignment.dest_end]
        window_digits = _digit_tokens(window)
        digits_match = _contains_contiguous_tokens(target_digits, window_digits)
        window_text = _text_without_digits(window)
        text_similarity = (
            float(fuzz.partial_ratio(target_text, window_text))
            if target_text
            else None
        )
        cer = float(Levenshtein.normalized_distance(target_norm, window))
        similarity = max(0.0, 1.0 - cer)
        text_quality = text_similarity if text_similarity is not None else 100.0
        rank = (1 if digits_match else 0, text_quality, float(alignment.score))

        if rank > best_rank:
            best_rank = rank
            best_similarity = similarity
            best_cer = cer
            best_window = window
            best_digit_match = digits_match
            best_text_similarity = text_similarity

    return best_similarity, best_cer, best_window, best_digit_match, best_text_similarity


def _ocr_metric(lines: list[dict[str, Any]], expected: dict[str, Any]) -> dict[str, Any]:
    target = expected.get("ocr_text")
    if not target:
        return {
            "applicable": False,
            "correct": None,
            "similarity": None,
            "cer": None,
            "best_window": None,
            "digit_match": None,
            "text_similarity": None,
        }
    candidates = _ocr_candidates(lines)
    similarity, cer, best_window, digit_match, text_similarity = _best_ocr_alignment(target, candidates)
    text_ok = text_similarity is None or text_similarity >= OCR_TEXT_ACCURACY_THRESHOLD
    return {
        "applicable": True,
        "correct": bool(digit_match and text_ok and similarity >= OCR_ACCURACY_THRESHOLD),
        "similarity": round(similarity, 4),
        "cer": round(cer, 4),
        "best_window": best_window,
        "digit_match": digit_match,
        "text_similarity": round(text_similarity, 2) if text_similarity is not None else None,
    }

def _normalise_image_specs(case: dict[str, Any]) -> list[dict[str, str]]:
    images = case.get("images")
    if images is None:
        filename = case.get("image")
        if not filename:
            raise ValueError(f"case {case.get('id', '<missing>')} has no image(s)")
        return [{"filename": filename, "label": "front"}]
    if not isinstance(images, list) or not images:
        raise ValueError(f"case {case.get('id', '<missing>')}: images must be a non-empty list")
    specs: list[dict[str, str]] = []
    for item in images:
        if not isinstance(item, dict):
            raise ValueError(f"case {case.get('id', '<missing>')}: image entry must be an object")
        filename = item.get("filename")
        label = item.get("label", "front")
        if not filename:
            raise ValueError(f"case {case.get('id', '<missing>')}: image entry has no filename")
        if label not in PANEL_LABELS:
            raise ValueError(f"case {case.get('id', '<missing>')}: invalid panel label {label!r}")
        specs.append({"filename": filename, "label": label})
    return specs


def _expected_overall(case: dict[str, Any]) -> str:
    statuses = [case["compliance"][field] for field in FIELDS]
    relevant = [status for status in statuses if status != "NOT_APPLICABLE"]
    if not relevant:
        return "NOT_APPLICABLE"
    return min(relevant, key=lambda state: _SEVERITY[state])


def _predicted_scoped_overall(fields: dict[str, dict[str, Any]]) -> str:
    statuses = [fields[field]["predicted_state"] for field in FIELDS]
    relevant = [status for status in statuses if status != "NOT_APPLICABLE"]
    if not relevant:
        return "NOT_APPLICABLE"
    return min(relevant, key=lambda state: _SEVERITY[state])


def _load_ground_truth(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data.get("cases")
    if not isinstance(cases, list):
        raise ValueError("ground_truth.json must contain a top-level 'cases' array")
    return data


def _validate_dataset(
    data: dict[str, Any], image_dir: Path, min_cases: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate all case metadata and return (verified, pending) cases.

    Pending cases remain in the repository as documentation/regression backlog,
    but they are skipped from execution and accuracy denominators until a named
    human verifier completes the pixel-level review.
    """
    cases = data["cases"]
    if min_cases < 0:
        raise ValueError("minimum case count cannot be negative")

    seen_ids: set[str] = set()
    seen_images: set[str] = set()
    verified_cases: list[dict[str, Any]] = []
    pending_cases: list[dict[str, Any]] = []

    for case in cases:
        case_id = case.get("id", "<missing>")
        if case_id in seen_ids:
            raise ValueError(f"duplicate case id: {case_id}")
        seen_ids.add(case_id)

        hand_verified = case.get("hand_verified")
        if not isinstance(hand_verified, bool):
            raise ValueError(f"case {case_id}: hand_verified must be a boolean")

        expected_fail = case.get("expected_fail", {})
        if expected_fail and not isinstance(expected_fail, dict):
            raise ValueError(f"case {case_id}: expected_fail must be an object")
        for expected_field in expected_fail:
            if expected_field not in FIELDS:
                raise ValueError(f"case {case_id}: expected_fail has unknown field {expected_field!r}")

        case_specs = _normalise_image_specs(case)
        if len({spec["label"] for spec in case_specs}) != len(case_specs):
            raise ValueError(f"case {case_id}: at most one image per panel label is supported")

        gt = case.get("ground_truth", {})
        compliance = case.get("compliance", {})
        if not isinstance(gt, dict) or not isinstance(compliance, dict):
            raise ValueError(f"case {case_id}: ground_truth and compliance must be objects")

        for field in FIELDS:
            item = gt.get(field, {})
            state = compliance.get(field)
            if not isinstance(item, dict):
                raise ValueError(f"case {case_id}: ground_truth.{field} must be an object")
            if state not in STATES:
                raise ValueError(f"case {case_id}: compliance.{field} has invalid state {state!r}")

            quantity_scope = item.get("quantity_scope")
            if quantity_scope is not None and quantity_scope not in {"total", "per_unit"}:
                raise ValueError(f"case {case_id}: ground_truth.{field}.quantity_scope must be total or per_unit")

            visible = item.get("visible") is True
            if visible:
                if "value" not in item or item.get("value") is None:
                    raise ValueError(f"case {case_id}: visible {field} requires a non-null value")
                if not str(item.get("ocr_text", "")).strip():
                    raise ValueError(f"case {case_id}: visible {field} requires hand-written ocr_text")
            elif state not in {"NOT_VERIFIED", "NOT_APPLICABLE"}:
                raise ValueError(
                    f"case {case_id}: non-visible {field} must be NOT_VERIFIED or NOT_APPLICABLE"
                )

        expected_overall = _expected_overall(case)
        if case.get("overall_compliance") != expected_overall:
            raise ValueError(
                f"case {case_id}: overall_compliance must equal the scoped worst state "
                f"{expected_overall!r}; got {case.get('overall_compliance')!r}"
            )

        if hand_verified:
            if not str(case.get("verified_by", "")).strip():
                raise ValueError(f"case {case_id}: verified_by is required for hand-verified cases")
            try:
                date.fromisoformat(case["verified_on"])
            except (KeyError, TypeError, ValueError):
                raise ValueError(f"case {case_id}: verified_on must be YYYY-MM-DD for hand-verified cases") from None

            for spec in case_specs:
                path = image_dir / spec["filename"]
                if not path.is_file():
                    raise ValueError(f"case {case_id}: image not found: {path}")
                if spec["filename"] in seen_images:
                    raise ValueError(f"image reused across cases: {spec['filename']}")
                seen_images.add(spec["filename"])
            verified_cases.append(case)
        else:
            pending_cases.append(case)

    if len(verified_cases) < min_cases:
        raise ValueError(
            f"evaluation set requires at least {min_cases} hand-verified cases; "
            f"found {len(verified_cases)} verified and {len(pending_cases)} pending"
        )

    return verified_cases, pending_cases

def _load_provider_fixtures(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    fixtures = data.get("barcodes", data)
    if not isinstance(fixtures, dict):
        raise ValueError("provider fixture file must contain a 'barcodes' object")
    return fixtures


@contextmanager
def _provider_mode(mode: str, fixture_path: Path | None) -> Iterator[None]:
    if mode == "live":
        yield
        return

    original = ProductLookupAdapter.__dict__["lookup"]
    fixtures = _load_provider_fixtures(fixture_path) if mode == "fixture" else {}

    def _lookup(barcode: str, db=None):
        return fixtures.get(barcode)

    ProductLookupAdapter.lookup = staticmethod(_lookup)
    try:
        yield
    finally:
        ProductLookupAdapter.lookup = original


@contextmanager
def _capture_pipeline_ocr() -> Iterator[dict[str, list[dict[str, Any]]]]:
    """Capture all lines returned by the production recrop/variant OCR stage."""
    original = pipeline_module._ocr_with_recrop
    captured: dict[str, list[dict[str, Any]]] = {}

    def _wrapped(image_path: str, image_quality: dict) -> list[dict]:
        lines = original(image_path, image_quality)
        captured[str(image_path)] = [dict(line) for line in lines]
        return lines

    pipeline_module._ocr_with_recrop = _wrapped
    try:
        yield captured
    finally:
        pipeline_module._ocr_with_recrop = original


def _expected_fail_status(case: dict[str, Any], fields: dict[str, dict[str, Any]], field: str) -> str | None:
    if field not in case.get("expected_fail", {}):
        return None
    item = fields[field]
    failures = []
    if item.get("ocr_correct") is False:
        failures.append("ocr")
    if item.get("field_match") is False:
        failures.append("field")
    if item.get("state_match") is False:
        failures.append("state")
    return "XFAIL" if failures else "XPASS"


def _annotate_expected_failures(case: dict[str, Any], fields: dict[str, dict[str, Any]]) -> tuple[int, int]:
    xfail = xpass = 0
    for field in FIELDS:
        status = _expected_fail_status(case, fields, field)
        fields[field]["expected_fail_status"] = status
        fields[field]["metric_excluded"] = status == "XFAIL"
        if status == "XFAIL":
            xfail += 1
        elif status == "XPASS":
            xpass += 1
    return xfail, xpass


def _run_case(case: dict[str, Any], image_dir: Path, inspection_date: date) -> dict[str, Any]:
    image_specs = _normalise_image_specs(case)
    scan_id = uuid.uuid4()
    stored_urls: list[str] = []
    captured_ocr: dict[str, list[dict[str, Any]]] = {}

    try:
        with Session(engine) as db:
            try:
                scan = ScanDB(id=scan_id, status=ScanStatus.PENDING)
                db.add(scan)
                db.flush()

                image_ids: list[uuid.UUID] = []
                for spec in image_specs:
                    source_path = image_dir / spec["filename"]
                    url = storage.save(str(scan_id), source_path.name, source_path.read_bytes())
                    stored_urls.append(url)
                    image_row = ImageDB(
                        id=uuid.uuid4(),
                        scan_id=scan_id,
                        url=url,
                        label=spec["label"],
                    )
                    db.add(image_row)
                    db.flush()
                    image_ids.append(image_row.id)

                with _capture_pipeline_ocr() as captured:
                    _, declarations, pipeline_overall, _, _ = run_pipeline(
                        scan_id,
                        image_ids,
                        db,
                        inspection_date=inspection_date,
                    )
                    captured_ocr = dict(captured)

                by_field = {d.field_name: d for d in declarations}
                image_paths_by_label: dict[str, str] = {}
                for url, spec in zip(stored_urls, image_specs):
                    path = storage.get_path(url)
                    if path:
                        image_paths_by_label[spec["label"]] = str(path)

                all_ocr_lines: list[dict[str, Any]] = []
                for path in image_paths_by_label.values():
                    all_ocr_lines.extend(captured_ocr.get(path, []))

                output: dict[str, Any] = {
                    "case_id": case["id"],
                    "conditions": case.get("conditions", []),
                    "images": image_specs,
                    "provider_mode": None,
                    "pipeline_overall": pipeline_overall.value,
                    "known_expected_failures": case.get("expected_fail", {}),
                    "expected_overall": case["overall_compliance"],
                    "fields": {},
                    "error": None,
                }

                for field in FIELDS:
                    decl = by_field.get(field)
                    expected = case["ground_truth"].get(field, {})
                    actual = decl.extracted_value if decl is not None else None
                    predicted_state = decl.verdict.value if decl is not None else "NOT_VERIFIED"
                    visible = expected.get("visible") is True
                    extraction_match = (
                        _field_matches(field, actual, expected.get("value")) if visible else None
                    )
                    ocr_metric = _ocr_metric(all_ocr_lines, expected) if visible else {
                        "applicable": False,
                        "correct": None,
                        "similarity": None,
                        "cer": None,
                        "best_window": None,
                    }
                    output["fields"][field] = {
                        "visible": visible,
                        "expected_value": expected.get("value") if visible else None,
                        "quantity_scope": expected.get("quantity_scope"),
                        "actual_value": actual,
                        "expected_state": case["compliance"][field],
                        "predicted_state": predicted_state,
                        "state_match": predicted_state == case["compliance"][field],
                        "field_match": extraction_match,
                        "ocr_correct": ocr_metric["correct"],
                        "ocr_similarity": ocr_metric["similarity"],
                        "ocr_cer": ocr_metric["cer"],
                        "ocr_text_similarity": ocr_metric.get("text_similarity"),
                        "ocr_best_window": ocr_metric["best_window"],
                        "ocr_digit_match": ocr_metric.get("digit_match"),
                    }

                xfail_count, xpass_count = _annotate_expected_failures(case, output["fields"])
                output["xfail_count"] = xfail_count
                output["xpass_count"] = xpass_count
                output["metric_excluded"] = xfail_count > 0
                output["predicted_scoped_overall"] = _predicted_scoped_overall(output["fields"])
                output["overall_match"] = output["predicted_scoped_overall"] == output["expected_overall"]
                return output
            finally:
                db.rollback()
    finally:
        # storage.save() creates the scan directory before writing the file. If
        # a write/pipeline error occurs before the URL is recorded, clean the
        # unique scan directory directly so partial cases cannot leak files.
        scan_dir = Path("/data/uploads") / str(scan_id)
        try:
            if scan_dir.exists():
                shutil.rmtree(scan_dir)
        except OSError:
            pass


def _error_result(case: dict[str, Any], exc: Exception) -> dict[str, Any]:
    return {
        "case_id": case["id"],
        "conditions": case.get("conditions", []),
        "images": _normalise_image_specs(case),
        "provider_mode": None,
        "pipeline_overall": None,
        "expected_overall": case["overall_compliance"],
        "predicted_scoped_overall": None,
        "overall_match": False,
        "fields": {
            field: {
                "visible": case["ground_truth"][field].get("visible") is True,
                "expected_value": case["ground_truth"][field].get("value") if case["ground_truth"][field].get("visible") else None,
                "actual_value": None,
                "expected_state": case["compliance"][field],
                "predicted_state": None,
                "state_match": False,
                "field_match": None,
                "ocr_correct": None,
                "ocr_similarity": None,
                "ocr_cer": None,
                "ocr_text_similarity": None,
                "ocr_best_window": None,
                "ocr_digit_match": None,
                "expected_fail_status": None,
                "metric_excluded": False,
            }
            for field in FIELDS
        },
        "known_expected_failures": case.get("expected_fail", {}),
        "xfail_count": 0,
        "xpass_count": 0,
        "metric_excluded": False,
        "error": {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(limit=12),
        },
    }


def _pct(n: int | float, d: int | float) -> float | None:
    return round(100.0 * n / d, 2) if d else None


def _summarise(results: list[dict[str, Any]], provider_mode: str) -> dict[str, Any]:
    """Aggregate completed, metric-eligible cases only."""
    completed_results = [result for result in results if not result.get("error")]
    metric_cases = [result for result in completed_results if not result.get("metric_excluded")]
    field_totals = Counter()
    field_correct = Counter()
    state_totals = Counter()
    state_correct = Counter()
    ocr_totals = Counter()
    ocr_correct = Counter()
    ocr_similarity_sum = Counter()
    ocr_cer_sum = Counter()
    visible_nv = Counter()
    hidden_nv = Counter()
    false_violation_field = Counter()
    false_violation_field_denominator = Counter()
    field_state_confusion: dict[str, Counter[tuple[str, str]]] = defaultdict(Counter)
    overall_confusion: Counter[tuple[str, str]] = Counter()
    condition_cases: dict[str, list[dict[str, Any]]] = defaultdict(list)

    overall_correct = 0
    overall_false_violation = 0
    overall_non_violation = 0
    overall_expected = Counter(result["expected_overall"] for result in metric_cases)
    xfail_fields = Counter()
    xpass_fields = Counter()
    xfail_cases = 0
    xpass_cases = 0

    for result in completed_results:
        xfail_cases += bool(result.get("xfail_count"))
        xpass_cases += bool(result.get("xpass_count"))
        for field, item in result["fields"].items():
            if item.get("expected_fail_status") == "XFAIL":
                xfail_fields[field] += 1
            elif item.get("expected_fail_status") == "XPASS":
                xpass_fields[field] += 1

    for result in metric_cases:
        expected_overall = result["expected_overall"]
        predicted_overall = result.get("predicted_scoped_overall")
        if predicted_overall is not None:
            overall_confusion[(expected_overall, predicted_overall)] += 1
            if expected_overall == predicted_overall:
                overall_correct += 1
            if expected_overall != "VIOLATION":
                overall_non_violation += 1
                if predicted_overall == "VIOLATION":
                    overall_false_violation += 1

        for condition in result.get("conditions", []):
            condition_cases[condition].append(result)

        for field, item in result["fields"].items():
            state = item.get("predicted_state")
            if state is not None:
                state_totals[field] += 1
                if item.get("state_match"):
                    state_correct[field] += 1
                field_state_confusion[field][(item["expected_state"], state)] += 1

            if item.get("expected_state") != "VIOLATION":
                false_violation_field_denominator[field] += 1
                if state == "VIOLATION":
                    false_violation_field[field] += 1

            if item.get("visible"):
                field_totals[field] += 1
                if item.get("field_match"):
                    field_correct[field] += 1
                if item.get("ocr_correct") is not None:
                    ocr_totals[field] += 1
                    if item["ocr_correct"]:
                        ocr_correct[field] += 1
                if item.get("ocr_similarity") is not None:
                    ocr_similarity_sum[field] += item["ocr_similarity"]
                if item.get("ocr_cer") is not None:
                    ocr_cer_sum[field] += item["ocr_cer"]
                if state == "NOT_VERIFIED":
                    visible_nv[field] += 1
            elif state == "NOT_VERIFIED":
                hidden_nv[field] += 1

    majority_state, majority_count = overall_expected.most_common(1)[0] if overall_expected else (None, 0)

    summary: dict[str, Any] = {
        "provider_mode": provider_mode,
        "provider_evidence_note": (
            "External provider evidence is disabled; MRP/net-quantity CONFLICT cases are not exercised in this run."
            if provider_mode == "disabled"
            else "Provider fixtures are deterministic and included in this run."
            if provider_mode == "fixture"
            else "LIVE provider calls were enabled; results are not suitable for reproducible historical comparison."
        ),
        "cases_requested": len(results),
        "cases_completed": len(completed_results),
        "cases_metric_eligible": len(metric_cases),
        "case_errors": len(results) - len(completed_results),
        "cases_excluded_xfail": xfail_cases,
        "cases_with_xpass": xpass_cases,
        "photos_evaluated": sum(len(result["images"]) for result in completed_results),
        "xfail_field_counts": dict(xfail_fields),
        "xpass_field_counts": dict(xpass_fields),
        "ocr_accuracy_percent": {field: _pct(ocr_correct[field], ocr_totals[field]) for field in FIELDS},
        "ocr_similarity_percent": {
            field: round(100.0 * ocr_similarity_sum[field] / ocr_totals[field], 2) if ocr_totals[field] else None
            for field in FIELDS
        },
        "ocr_cer_percent": {
            field: round(100.0 * ocr_cer_sum[field] / ocr_totals[field], 2) if ocr_totals[field] else None
            for field in FIELDS
        },
        "field_extraction_accuracy_percent": {
            field: _pct(field_correct[field], field_totals[field]) for field in FIELDS
        },
        "compliance_state_accuracy_percent": {
            field: _pct(state_correct[field], state_totals[field]) for field in FIELDS
        },
        "false_violation_rate_percent": _pct(
            sum(false_violation_field.values()), sum(false_violation_field_denominator.values())
        ),
        "false_violation_case_rate_percent": _pct(overall_false_violation, overall_non_violation),
        "violation_recall_percent": _pct(
            sum(1 for result in metric_cases if result["expected_overall"] == "VIOLATION" and result.get("predicted_scoped_overall") == "VIOLATION"),
            sum(1 for result in metric_cases if result["expected_overall"] == "VIOLATION"),
        ),
        "not_verified_rate_percent_all_field_states": _pct(
            sum(1 for result in metric_cases for item in result["fields"].values() if item.get("predicted_state") == "NOT_VERIFIED"),
            sum(1 for result in metric_cases for item in result["fields"].values() if item.get("predicted_state") is not None),
        ),
        "not_verified_rate_percent_visible_fields": _pct(sum(visible_nv.values()), sum(field_totals.values())),
        "not_verified_rate_percent_non_visible_fields": _pct(
            sum(hidden_nv.values()),
            sum(1 for result in metric_cases for item in result["fields"].values() if not item.get("visible") and item.get("predicted_state") is not None),
        ),
        "overall_compliance_accuracy_percent": _pct(overall_correct, len(metric_cases)),
        "majority_class_baseline": {
            "state": majority_state,
            "count": majority_count,
            "accuracy_percent": _pct(majority_count, len(metric_cases)),
        },
        "overall_confusion_matrix": {
            expected: {predicted: overall_confusion[(expected, predicted)] for predicted in STATES}
            for expected in STATES
        },
        "field_confusion_matrices": {
            field: {
                expected: {predicted: field_state_confusion[field][(expected, predicted)] for predicted in STATES}
                for expected in STATES
            }
            for field in FIELDS
        },
        "condition_breakdown": {},
    }

    for condition, condition_result_list in sorted(condition_cases.items()):
        summary["condition_breakdown"][condition] = _summarise_without_condition(condition_result_list)

    return summary

def _summarise_without_condition(results: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [result for result in results if not result.get("error")]
    metric = [result for result in completed if not result.get("metric_excluded")]
    visible = [
        item
        for result in metric
        for item in result["fields"].values()
        if item.get("visible")
    ]
    visible_ocr = [item for item in visible if item.get("ocr_correct") is not None]
    field_matches = [item for item in visible if item.get("field_match") is not None]
    non_violation_cases = [result for result in metric if result["expected_overall"] != "VIOLATION"]
    violation_cases = [result for result in metric if result["expected_overall"] == "VIOLATION"]
    false_case_violations = sum(
        result.get("predicted_scoped_overall") == "VIOLATION" for result in non_violation_cases
    )
    return {
        "cases": len(completed),
        "metric_eligible": len(metric),
        "ocr_accuracy_percent": _pct(sum(bool(item["ocr_correct"]) for item in visible_ocr), len(visible_ocr)),
        "field_extraction_accuracy_percent": _pct(sum(bool(item["field_match"]) for item in field_matches), len(field_matches)),
        "overall_compliance_accuracy_percent": _pct(
            sum(result.get("overall_match", False) for result in metric), len(metric)
        ),
        "false_violation_case_rate_percent": _pct(false_case_violations, len(non_violation_cases)),
        "violation_recall_percent": _pct(
            sum(result.get("predicted_scoped_overall") == "VIOLATION" for result in violation_cases),
            len(violation_cases),
        ),
        "not_verified_rate_percent_visible_fields": _pct(
            sum(item.get("predicted_state") == "NOT_VERIFIED" for item in visible), len(visible)
        ),
    }

def _git_info() -> tuple[str, bool | None]:
    env_sha = os.environ.get("GIT_SHA", "").strip()
    env_dirty = os.environ.get("GIT_DIRTY")
    if env_sha:
        if env_dirty is None:
            return env_sha, None
        if env_dirty.strip().lower() in {"1", "true", "yes"}:
            return env_sha, True
        if env_dirty.strip().lower() in {"0", "false", "no"}:
            return env_sha, False
        return env_sha, None

    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain", "--untracked-files=all"],
                cwd=REPO_ROOT,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        )
        return sha, dirty
    except (OSError, subprocess.CalledProcessError):
        return "unknown", None


def _git_sha() -> str:
    return _git_info()[0]

def _baseline_cases(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cases = data.get("cases", [])
    if isinstance(cases, list):
        return {case["case_id"]: case for case in cases if "case_id" in case}
    if isinstance(cases, dict):
        return cases
    return {}


def _load_baseline_for_run(path: Path, provider_mode: str) -> dict[str, Any]:
    try:
        baseline = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"baseline file not found: {path}") from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"baseline is not valid JSON: {exc}") from None

    if baseline.get("status") == "not_initialized":
        raise ValueError(
            f"baseline is not initialized: {path}. Run a reviewed full suite with --update-baseline after >=30 hand-verified cases."
        )
    if baseline.get("status") != "initialized":
        raise ValueError(f"baseline status must be 'initialized', got {baseline.get('status')!r}")
    if baseline.get("provider_mode") != provider_mode:
        raise ValueError(
            f"baseline provider mode {baseline.get('provider_mode')!r} does not match current mode {provider_mode!r}"
        )
    return baseline



def _compare_baseline(
    current: dict[str, Any],
    baseline: dict[str, Any],
    require_complete: bool,
    compare_aggregates: bool = True,
) -> list[str]:
    if baseline.get("status") == "not_initialized":
        raise ValueError("baseline is not initialized; run with --update-baseline after a verified full-suite run")
    if baseline.get("provider_mode") != current["summary"].get("provider_mode"):
        raise ValueError(
            f"baseline provider mode {baseline.get('provider_mode')!r} does not match current "
            f"mode {current['summary'].get('provider_mode')!r}"
        )

    regressions: list[str] = []
    baseline_by_id = _baseline_cases(baseline)
    current_by_id = {case["case_id"]: case for case in current["cases"]}

    new_cases = sorted(set(current_by_id) - set(baseline_by_id))
    missing_cases = sorted(set(baseline_by_id) - set(current_by_id))
    if require_complete and new_cases:
        regressions.append(f"unbaselined cases: {', '.join(new_cases)}")
    if require_complete and missing_cases:
        regressions.append(f"baseline cases missing from run: {', '.join(missing_cases)}")

    for case_id in sorted(set(current_by_id) & set(baseline_by_id)):
        old = baseline_by_id[case_id]
        new = current_by_id[case_id]
        for field in FIELDS:
            old_field = old["fields"][field]
            new_field = new["fields"][field]
            old_xfail = old_field.get("expected_fail_status") == "XFAIL"
            new_xfail = new_field.get("expected_fail_status") == "XFAIL"
            new_xpass = new_field.get("expected_fail_status") == "XPASS"
            if new_xpass and old_xfail:
                regressions.append(f"{case_id}/{field}: expected-fail case unexpectedly passed; remove expected_fail after review")
            elif old_xfail and not new_xfail and new_field.get("field_match") is False:
                regressions.append(f"{case_id}/{field}: known failure is no longer marked expected_fail")
            if old_field.get("field_match") is True and new_field.get("field_match") is False and not new_xfail:
                regressions.append(f"{case_id}/{field}: field extraction regressed")
            if old_field.get("state_match") is True and new_field.get("state_match") is False and not new_xfail:
                regressions.append(f"{case_id}/{field}: compliance state regressed")
            if old_field.get("ocr_correct") is True and new_field.get("ocr_correct") is False and not new_xfail:
                regressions.append(f"{case_id}/{field}: OCR accuracy regressed below threshold")
            old_similarity = old_field.get("ocr_similarity")
            new_similarity = new_field.get("ocr_similarity")
            if old_similarity is not None and new_similarity is not None and old_similarity - new_similarity > OCR_SCORE_EPSILON:
                regressions.append(f"{case_id}/{field}: OCR similarity fell by > {OCR_SCORE_EPSILON:.2f}")

        if old.get("overall_match") is True and new.get("overall_match") is False:
            regressions.append(f"{case_id}: overall compliance regressed")

    if compare_aggregates:
        old_summary = baseline.get("summary", {})
        new_summary = current["summary"]

        for field, old_value in old_summary.get("field_extraction_accuracy_percent", {}).items():
            new_value = new_summary.get("field_extraction_accuracy_percent", {}).get(field)
            if old_value is not None and new_value is not None and new_value + REGRESSION_EPSILON < old_value:
                regressions.append(f"aggregate/{field}: extraction accuracy dropped {old_value}% -> {new_value}%")

        for field, old_value in old_summary.get("ocr_accuracy_percent", {}).items():
            new_value = new_summary.get("ocr_accuracy_percent", {}).get(field)
            if old_value is not None and new_value is not None and new_value + REGRESSION_EPSILON < old_value:
                regressions.append(f"aggregate/{field}: OCR accuracy dropped {old_value}% -> {new_value}%")

        old_overall = old_summary.get("overall_compliance_accuracy_percent")
        new_overall = new_summary.get("overall_compliance_accuracy_percent")
        if old_overall is not None and new_overall is not None and new_overall + REGRESSION_EPSILON < old_overall:
            regressions.append(f"aggregate/overall: accuracy dropped {old_overall}% -> {new_overall}%")

        old_false = old_summary.get("false_violation_case_rate_percent")
        new_false = new_summary.get("false_violation_case_rate_percent")
        if old_false is not None and new_false is not None and new_false > old_false + REGRESSION_EPSILON:
            regressions.append(f"aggregate/false violation case rate increased {old_false}% -> {new_false}%")

        old_nv = old_summary.get("not_verified_rate_percent_visible_fields")
        new_nv = new_summary.get("not_verified_rate_percent_visible_fields")
        if old_nv is not None and new_nv is not None and new_nv > old_nv + REGRESSION_EPSILON:
            regressions.append(f"aggregate/visible-field NOT_VERIFIED rate increased {old_nv}% -> {new_nv}%")

    return regressions


def _write_baseline(path: Path, results: list[dict[str, Any]], summary: dict[str, Any], provider_mode: str) -> None:
    git_sha, git_dirty = _git_info()
    payload = {
        "version": 1,
        "status": "initialized",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_sha,
        "git_dirty": git_dirty,
        "provider_mode": provider_mode,
        "inspection_date": summary.get("inspection_date"),
        "summary": summary,
        "cases": results,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _print_summary(summary: dict[str, Any], baseline_regressions: list[str]) -> None:
    print("\nSIH26034 evaluation")
    print("=" * 86)
    print(f"Cases requested/completed:       {summary['cases_requested']}/{summary['cases_completed']}")
    print(f"Cases metric-eligible:            {summary['cases_metric_eligible']}")
    print(f"Pending cases skipped:            {summary['cases_pending_skipped']}")
    print(f"Photos evaluated:                {summary['photos_evaluated']}")
    print(f"Case execution errors:           {summary['case_errors']}")
    print(f"Provider mode:                   {summary['provider_mode']}")
    print(f"Provider note:                   {summary['provider_evidence_note']}")
    print(f"Git SHA:                         {summary['git_sha']}")
    dirty = summary["git_dirty"]
    dirty_text = "unknown" if dirty is None else str(dirty)
    print(f"Git tree dirty:                  {dirty_text}")

    print("\nKnown expected failures:")
    print(f"  XFAIL fields:                   {sum(summary['xfail_field_counts'].values())}")
    print(f"  XPASS fields:                   {sum(summary['xpass_field_counts'].values())}")

    print("\nOCR accuracy (visible fields only; digit-gated):")
    for field, value in summary["ocr_accuracy_percent"].items():
        similarity = summary["ocr_similarity_percent"].get(field)
        cer = summary["ocr_cer_percent"].get(field)
        if value is None:
            print(f"  {field:<28} n/a")
        else:
            print(f"  {field:<28} {value:.2f}%  similarity {similarity:.2f}%  CER {cer:.2f}%")

    print("\nField extraction accuracy (visible fields only):")
    for field, value in summary["field_extraction_accuracy_percent"].items():
        print(f"  {field:<28} {value:.2f}%" if value is not None else f"  {field:<28} n/a")

    print("\nCompliance-state accuracy:")
    for field, value in summary["compliance_state_accuracy_percent"].items():
        print(f"  {field:<28} {value:.2f}%" if value is not None else f"  {field:<28} n/a")

    print("\nError/abstention rates:")
    print(f"  False VIOLATION (field):       {summary['false_violation_rate_percent']:.2f}%" if summary['false_violation_rate_percent'] is not None else "  False VIOLATION (field):       n/a")
    print(f"  False VIOLATION (case):        {summary['false_violation_case_rate_percent']:.2f}%" if summary['false_violation_case_rate_percent'] is not None else "  False VIOLATION (case):        n/a")
    print(f"  VIOLATION recall (case):       {summary['violation_recall_percent']:.2f}%" if summary['violation_recall_percent'] is not None else "  VIOLATION recall (case):       n/a")
    print(f"  NOT_VERIFIED (all fields):     {summary['not_verified_rate_percent_all_field_states']:.2f}%" if summary['not_verified_rate_percent_all_field_states'] is not None else "  NOT_VERIFIED (all fields):     n/a")
    print(f"  NOT_VERIFIED (visible fields): {summary['not_verified_rate_percent_visible_fields']:.2f}%" if summary['not_verified_rate_percent_visible_fields'] is not None else "  NOT_VERIFIED (visible fields): n/a")
    print(f"  NOT_VERIFIED (non-visible):    {summary['not_verified_rate_percent_non_visible_fields']:.2f}%" if summary['not_verified_rate_percent_non_visible_fields'] is not None else "  NOT_VERIFIED (non-visible):    n/a")

    print("\nOverall compliance (scoped to MRP/net quantity/manufacture/expiry):")
    overall = summary["overall_compliance_accuracy_percent"]
    print(f"  Accuracy:                      {overall:.2f}%" if overall is not None else "  Accuracy:                      n/a")
    baseline = summary["majority_class_baseline"]
    print(f"  Majority baseline:             {baseline['state']} ({baseline['accuracy_percent']:.2f}%)" if baseline['state'] else "  Majority baseline:             n/a")

    print("\nOverall confusion matrix (expected rows / predicted columns):")
    header = "  " + "Expected\\Pred".ljust(18) + " ".join(state[:12].rjust(12) for state in STATES)
    print(header)
    for expected in STATES:
        row = summary["overall_confusion_matrix"][expected]
        print("  " + expected.ljust(18) + " ".join(str(row[state]).rjust(12) for state in STATES))

    if summary["condition_breakdown"]:
        print("\nPer-condition breakdown:")
        print("  " + "condition".ljust(24) + "cases".rjust(8) + " overall".rjust(12) + " false-VIOL".rjust(13) + " NV-visible".rjust(13))
        for condition, item in summary["condition_breakdown"].items():
            overall = item["overall_compliance_accuracy_percent"]
            false_v = item["false_violation_case_rate_percent"]
            nv = item["not_verified_rate_percent_visible_fields"]
            print(
                "  "
                + condition[:22].ljust(24)
                + str(item["completed"]).rjust(8)
                + (f"{overall:.2f}%" if overall is not None else "n/a").rjust(12)
                + (f"{false_v:.2f}%" if false_v is not None else "n/a").rjust(13)
                + (f"{nv:.2f}%" if nv is not None else "n/a").rjust(13)
            )

    if baseline_regressions:
        print("\nREGRESSIONS DETECTED:")
        for regression in baseline_regressions:
            print(f"  - {regression}")

    print("=" * 86)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_EVAL_ROOT / "ground_truth.json")
    parser.add_argument("--image-dir", type=Path, default=DEFAULT_EVAL_ROOT / "images")
    parser.add_argument("--output", type=Path, default=DEFAULT_EVAL_ROOT / "results/latest.json")
    parser.add_argument("--provider-mode", choices=("disabled", "fixture", "live"), default="disabled")
    parser.add_argument("--provider-fixtures", type=Path, default=DEFAULT_EVAL_ROOT / "provider_fixtures.json")
    parser.add_argument("--inspection-date", help="YYYY-MM-DD; defaults to ground_truth.json")
    parser.add_argument("--min-cases", type=int, default=30, help="minimum cases required for this run (default: 30)")
    parser.add_argument("--case", dest="case_id", help="run one case without the full-suite minimum gate")
    parser.add_argument("--baseline", type=Path, help="compare this run against a committed baseline JSON")
    parser.add_argument("--allow-incomplete-baseline", action="store_true", help="allow new/missing cases in a full-suite baseline comparison while adding cases")
    parser.add_argument("--update-baseline", type=Path, help="write current results as the new committed baseline")
    args = parser.parse_args()

    if args.min_cases < 0:
        parser.error("--min-cases must be >= 0")
    if args.update_baseline and args.case_id:
        parser.error("--update-baseline cannot be used with --case; baseline updates require a full suite")

    baseline: dict[str, Any] | None = None
    if args.baseline:
        baseline = _load_baseline_for_run(args.baseline, args.provider_mode)

    data = _load_ground_truth(args.ground_truth)
    all_cases = data["cases"]
    if args.case_id:
        selected = [case for case in all_cases if str(case.get("id")) == args.case_id]
        if not selected:
            raise ValueError(f"case not found: {args.case_id}")
        if not selected[0].get("hand_verified"):
            print(f"Case {args.case_id} is pending human verification; skipped.")
            return 0
        selected_data = dict(data)
        selected_data["cases"] = selected
        verified_cases, pending_cases = _validate_dataset(selected_data, args.image_dir, 0)
        cases = verified_cases
    else:
        verified_cases, pending_cases = _validate_dataset(data, args.image_dir, args.min_cases)
        cases = verified_cases

    inspection_date_raw = args.inspection_date or data.get("inspection_date")
    if not inspection_date_raw:
        raise ValueError("set ground_truth.json inspection_date or --inspection-date YYYY-MM-DD")
    inspection_date = date.fromisoformat(inspection_date_raw)

    # The production resolver is currently hard-coded to /data/uploads. Fail with
    # a useful message instead of producing a zero-image run in a local environment.
    if not Path("/data/uploads").is_dir():
        raise RuntimeError(
            "pipeline expects /data/uploads. Run the evaluator in the project's backend "
            "Docker container (recommended), or provide that mount in the evaluation environment."
        )
    if not os.access("/data/uploads", os.W_OK):
        raise RuntimeError("/data/uploads is not writable by the evaluation process")

    results: list[dict[str, Any]] = []
    with _provider_mode(args.provider_mode, args.provider_fixtures):
        for case in cases:
            try:
                result = _run_case(case, args.image_dir, inspection_date)
                result["provider_mode"] = args.provider_mode
            except Exception as exc:  # keep the suite moving; execution errors are reported and exit non-zero
                result = _error_result(case, exc)
                result["provider_mode"] = args.provider_mode
            results.append(result)

    completed_results = [result for result in results if not result.get("error")]
    summary = _summarise(results, args.provider_mode)
    summary["inspection_date"] = inspection_date.isoformat()
    summary["cases_pending_skipped"] = len(pending_cases)
    summary["git_sha"], summary["git_dirty"] = _git_info()

    baseline_regressions: list[str] = []

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {
                "evaluation_version": data.get("version", 5),
                "provider_mode": args.provider_mode,
                "inspection_date": inspection_date.isoformat(),
                "summary": summary,
                "cases": results,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    if baseline is not None:
        current_payload = {"cases": completed_results, "summary": summary}
        baseline_regressions = _compare_baseline(
            current_payload,
            baseline,
            (not args.allow_incomplete_baseline) and not bool(args.case_id),
            compare_aggregates=not bool(args.case_id) and not args.allow_incomplete_baseline,
        )

    _print_summary(summary, baseline_regressions)

    if args.update_baseline:
        if args.case_id:
            raise ValueError("refusing to update baseline from --case; baseline updates require a full suite")
        if len(verified_cases) < 30:
            raise ValueError("refusing to update baseline before at least 30 hand-verified cases are present")
        if results != completed_results:
            raise ValueError("refusing to update baseline when one or more cases failed")
        _write_baseline(args.update_baseline, completed_results, summary, args.provider_mode)
        print(f"Baseline written: {args.update_baseline}")

    if results and any(result.get("error") for result in results):
        return 2
    if any(result.get("xpass_count") for result in results):
        return 1
    if baseline_regressions:
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(f"Evaluation setup failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
