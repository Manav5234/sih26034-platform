import os
from pathlib import Path

os.environ.setdefault("JWT_SECRET", "test-evaluation-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/sih26034_evaluation_test.db")

from scripts import evaluate


def _metric(target: str, *lines: str):
    return evaluate._ocr_metric([{"text": line} for line in lines], {"ocr_text": target})


def test_ocr_digit_gate_uses_aligned_window() -> None:
    assert _metric("01/2025", "MFD 01/2025 EXP 01/2026")["correct"] is True
    assert _metric("MRP ₹200/-", "MRP ₹200/- Net Wt 500 g")["correct"] is True
    assert _metric("Net Qty 500 g", "Net Qty: 500 g MRP Rs 45")["correct"] is True


def test_ocr_digit_gate_rejects_substitutions() -> None:
    assert _metric("₹200", "MRP ₹280/-")["correct"] is False
    assert _metric("₹200", "MRP ₹100/-")["correct"] is False
    assert _metric("01/2025", "MFD 01/2026")["correct"] is False


def test_digit_only_similarity_is_based_on_alignment_not_vacuous_text_score() -> None:
    good = _metric("01/2025", "01/2025")
    bad = _metric("01/2025", "01/2026")
    assert good["text_similarity"] is None
    assert good["similarity"] == 1.0
    assert bad["similarity"] < 1.0


def test_pending_cases_are_skipped_and_minimum_counts_verified_only(tmp_path: Path) -> None:
    image = tmp_path / "verified.jpg"
    image.write_bytes(b"not a real image; validation only")
    pending = {
        "id": "001",
        "hand_verified": False,
        "images": [{"filename": "pending.jpg", "label": "front"}],
        "ground_truth": {
            "mrp": {"visible": False},
            "net_quantity": {"visible": False},
            "manufacture_date": {"visible": False},
            "expiry_date": {"visible": False},
        },
        "compliance": {
            "mrp": "NOT_VERIFIED",
            "net_quantity": "NOT_VERIFIED",
            "manufacture_date": "NOT_VERIFIED",
            "expiry_date": "NOT_VERIFIED",
        },
        "overall_compliance": "NOT_VERIFIED",
    }
    verified = {
        "id": "002",
        "hand_verified": True,
        "verified_by": "reviewer-1",
        "verified_on": "2026-09-20",
        "images": [{"filename": image.name, "label": "front"}],
        "ground_truth": {
            "mrp": {"visible": False},
            "net_quantity": {"visible": False},
            "manufacture_date": {"visible": False},
            "expiry_date": {"visible": False},
        },
        "compliance": {
            "mrp": "NOT_VERIFIED",
            "net_quantity": "NOT_VERIFIED",
            "manufacture_date": "NOT_VERIFIED",
            "expiry_date": "NOT_VERIFIED",
        },
        "overall_compliance": "NOT_VERIFIED",
    }
    data = {"cases": [pending, verified]}
    verified_cases, pending_cases = evaluate._validate_dataset(data, tmp_path, 1)
    assert [case["id"] for case in verified_cases] == ["002"]
    assert [case["id"] for case in pending_cases] == ["001"]


def test_expected_fail_is_xfail_and_fixed_case_is_xpass() -> None:
    case = {"expected_fail": {"mrp": "known defect"}}
    fields = {
        field: {
            "ocr_correct": True,
            "field_match": True,
            "state_match": True,
        }
        for field in evaluate.FIELDS
    }
    xfail, xpass = evaluate._annotate_expected_failures(case, fields)
    assert (xfail, xpass) == (0, 1)
    assert fields["mrp"]["expected_fail_status"] == "XPASS"

    fields["mrp"]["field_match"] = False
    xfail, xpass = evaluate._annotate_expected_failures(case, fields)
    assert (xfail, xpass) == (1, 0)
    assert fields["mrp"]["expected_fail_status"] == "XFAIL"
    assert fields["mrp"]["metric_excluded"] is True


def test_xfail_fields_are_excluded_from_accuracy_aggregates() -> None:
    def result(field_match: bool, xfail: bool):
        fields = {
            field: {
                "visible": True,
                "field_match": True,
                "state_match": True,
                "predicted_state": "SATISFIED",
                "ocr_correct": True,
                "ocr_similarity": 1.0,
                "ocr_cer": 0.0,
                "expected_state": "SATISFIED",
            }
            for field in evaluate.FIELDS
        }
        fields["mrp"]["field_match"] = field_match
        fields["mrp"]["expected_fail_status"] = "XFAIL" if xfail else None
        return {
            "case_id": "1" if xfail else "2",
            "error": None,
            "conditions": [],
            "images": [],
            "expected_overall": "SATISFIED",
            "predicted_scoped_overall": "SATISFIED",
            "overall_match": True,
            "fields": fields,
            "xfail_count": int(xfail),
            "xpass_count": 0,
            "metric_excluded": xfail,
        }

    summary = evaluate._summarise([result(False, True), result(True, False)], "disabled")
    assert summary["cases_metric_eligible"] == 1
    assert summary["field_extraction_accuracy_percent"]["mrp"] == 100.0
    assert summary["xfail_field_counts"]["mrp"] == 1
