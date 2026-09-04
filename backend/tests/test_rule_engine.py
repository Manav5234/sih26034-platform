"""Tests for the versioned rule engine.

All 8 required test cases:
1. SATISFIED — declaration present, confident, passes all conditions
2. VIOLATION — declaration present but fails a condition (wrong unit)
3. VIOLATION — declaration required but missing entirely
4. NOT_VERIFIED — declaration present but confidence below threshold
5. NOT_APPLICABLE — rule doesn't apply to this product's category
6. CONFLICT — declaration has conflicting evidence (pass-through)
7. Version selection — correct rule_set picked for inspection_date
8. Version selection failure — no matching rule_set raises error
"""
import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base, RuleSet as RuleSetDB, Rule as RuleDB, Declaration as DeclDB, VerificationState
from app.rule_engine import RuleEngine, RuleSetError, select_ruleset


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _seed_ruleset(db, *, jurisdiction="India", effective_from=date(2024, 1, 1),
                  effective_to=None, version="2024.1", prefix="LMR"):
    rs = RuleSetDB(
        id=uuid.uuid4(),
        source="Legal Metrology (Packaged Commodities) Rules, 2011",
        rule_version=version,
        effective_from=effective_from,
        effective_to=effective_to,
        jurisdiction=jurisdiction,
    )
    db.add(rs)
    db.flush()

    rules = [
        RuleDB(
            rule_id=f"{prefix}-001", rule_set_id=rs.id,
            source_document="Legal Metrology Act, 2009", clause="Rule 5",
            applicability="All pre-packaged goods", required_declaration="mrp",
            validation_conditions={"must_be_present": True, "min_confidence": 0.6, "format": "numeric", "min_value": 0},
            measurement_requirements=None, exceptions=[], effective_date=effective_from,
            evidence_requirements=["OCR", "BARCODE"],
        ),
        RuleDB(
            rule_id=f"{prefix}-002", rule_set_id=rs.id,
            source_document="Legal Metrology Act, 2009", clause="Rule 6",
            applicability="All pre-packaged goods", required_declaration="net_quantity",
            validation_conditions={"must_be_present": True, "min_confidence": 0.6, "format": "quantity_with_unit", "allowed_units": ["g", "kg", "ml", "l"]},
            measurement_requirements=None, exceptions=[], effective_date=effective_from,
            evidence_requirements=["OCR"],
        ),
        RuleDB(
            rule_id=f"{prefix}-003", rule_set_id=rs.id,
            source_document="Legal Metrology Act, 2009", clause="Rule 7",
            applicability="Imported goods", required_declaration="manufacturer",
            validation_conditions={"must_be_present": True, "min_confidence": 0.6, "format": "text", "min_length": 1},
            measurement_requirements=None, exceptions=[], effective_date=effective_from,
            evidence_requirements=["OCR", "PRODUCT_DATABASE"],
        ),
    ]
    for r in rules:
        db.add(r)
    db.commit()
    return rs


@pytest.fixture
def ruleset(db):
    return _seed_ruleset(db)


def _all_decls(scan_id=None, confidence=0.85):
    """Create all 3 declarations needed for a complete evaluation."""
    scan_id = scan_id or uuid.uuid4()
    return [
        DeclDB(id=uuid.uuid4(), scan_id=scan_id, field_name="mrp",
               extracted_value={"amount": 499.0, "currency": "INR"}, rule_id="LMR-001",
               verdict=VerificationState.NOT_VERIFIED, reason="", confidence=confidence, officer_correction=None),
        DeclDB(id=uuid.uuid4(), scan_id=scan_id, field_name="net_quantity",
               extracted_value={"value": 500.0, "unit": "g"}, rule_id="LMR-002",
               verdict=VerificationState.NOT_VERIFIED, reason="", confidence=confidence, officer_correction=None),
        DeclDB(id=uuid.uuid4(), scan_id=scan_id, field_name="manufacturer",
               extracted_value="FreshHarvest Pvt Ltd", rule_id="LMR-003",
               verdict=VerificationState.NOT_VERIFIED, reason="", confidence=confidence, officer_correction=None),
    ]


def _make_decl(field_name, extracted_value, confidence=0.85, verdict="NOT_VERIFIED", rule_id=None):
    return DeclDB(
        id=uuid.uuid4(),
        scan_id=uuid.uuid4(),
        field_name=field_name,
        extracted_value=extracted_value,
        rule_id=rule_id,
        verdict=VerificationState(verdict),
        reason="",
        confidence=confidence,
        officer_correction=None,
    )


# ---------------------------------------------------------------------------
# Test 1: SATISFIED
# ---------------------------------------------------------------------------

def test_satisfied(db, ruleset):
    decls = _all_decls()
    engine = RuleEngine(db)
    overall, results = engine.evaluate(decls, date(2024, 6, 1))

    mrp = next(r for r in results if r["field_name"] == "mrp")
    assert mrp["verdict"] == VerificationState.SATISFIED
    assert overall == VerificationState.SATISFIED


# ---------------------------------------------------------------------------
# Test 2: VIOLATION — wrong unit
# ---------------------------------------------------------------------------

def test_violation_wrong_unit(db, ruleset):
    decls = _all_decls()
    decls[1].extracted_value = {"value": 500.0, "unit": "lbs"}
    engine = RuleEngine(db)
    overall, results = engine.evaluate(decls, date(2024, 6, 1))

    nq = next(r for r in results if r["field_name"] == "net_quantity")
    assert nq["verdict"] == VerificationState.VIOLATION
    assert "lbs" in nq["reason"]
    assert overall == VerificationState.VIOLATION


# ---------------------------------------------------------------------------
# Test 3: VIOLATION — missing declaration
# ---------------------------------------------------------------------------

def test_violation_missing_declaration(db, ruleset):
    decls = _all_decls()
    decls = [d for d in decls if d.field_name != "mrp"]  # remove mrp
    engine = RuleEngine(db)
    overall, results = engine.evaluate(decls, date(2024, 6, 1))

    mrp = next(r for r in results if r["field_name"] == "mrp")
    assert mrp["verdict"] == VerificationState.VIOLATION
    assert "not found" in mrp["reason"].lower()
    assert overall == VerificationState.VIOLATION


# ---------------------------------------------------------------------------
# Test 4: NOT_VERIFIED — low confidence
# ---------------------------------------------------------------------------

def test_not_verified_low_confidence(db, ruleset):
    decls = _all_decls(confidence=0.3)
    engine = RuleEngine(db)
    overall, results = engine.evaluate(decls, date(2024, 6, 1))

    mrp = next(r for r in results if r["field_name"] == "mrp")
    assert mrp["verdict"] == VerificationState.NOT_VERIFIED
    assert "confidence" in mrp["reason"].lower()
    assert overall == VerificationState.NOT_VERIFIED


# ---------------------------------------------------------------------------
# Test 5: NOT_APPLICABLE — wrong category
# ---------------------------------------------------------------------------

def test_not_applicable_category(db, ruleset):
    decls = _all_decls()
    engine = RuleEngine(db)
    overall, results = engine.evaluate(decls, date(2024, 6, 1), product_category="domestic")

    mfr = next(r for r in results if r["field_name"] == "manufacturer")
    assert mfr["verdict"] == VerificationState.NOT_APPLICABLE
    assert "not applicable" in mfr["reason"].lower()
    # overall should still be SATISFIED since NOT_APPLICABLE is excluded from severity
    assert overall == VerificationState.SATISFIED


# ---------------------------------------------------------------------------
# Test 6: CONFLICT pass-through
# ---------------------------------------------------------------------------

def test_conflict_pass_through(db, ruleset):
    decls = _all_decls()
    decls[0].verdict = VerificationState.CONFLICT
    engine = RuleEngine(db)
    overall, results = engine.evaluate(decls, date(2024, 6, 1))

    mrp = next(r for r in results if r["field_name"] == "mrp")
    assert mrp["verdict"] == VerificationState.CONFLICT
    assert "conflicting" in mrp["reason"].lower()
    assert overall == VerificationState.CONFLICT


# ---------------------------------------------------------------------------
# Test 7: Version selection — correct rule_set picked
# ---------------------------------------------------------------------------

def test_version_selection_correct(db):
    _seed_ruleset(db, effective_from=date(2023, 1, 1), effective_to=date(2023, 12, 31), version="2023.1", prefix="OLD")
    _seed_ruleset(db, effective_from=date(2024, 1, 1), effective_to=None, version="2024.1", prefix="NEW")

    selected = select_ruleset(db, "India", date(2024, 6, 1))
    assert selected.rule_version == "2024.1"

    selected_old = select_ruleset(db, "India", date(2023, 6, 1))
    assert selected_old.rule_version == "2023.1"


# ---------------------------------------------------------------------------
# Test 8: Version selection failure — zero or multiple matches
# ---------------------------------------------------------------------------

def test_version_selection_no_match(db):
    with pytest.raises(RuleSetError, match="No rule_set found"):
        select_ruleset(db, "India", date(2020, 1, 1))


def test_version_selection_multiple_overlapping(db):
    _seed_ruleset(db, effective_from=date(2024, 1, 1), effective_to=date(2024, 12, 31), version="A", prefix="A")
    _seed_ruleset(db, effective_from=date(2024, 6, 1), effective_to=None, version="B", prefix="B")

    with pytest.raises(RuleSetError, match="Multiple overlapping"):
        select_ruleset(db, "India", date(2024, 8, 1))
