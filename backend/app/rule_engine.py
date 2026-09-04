"""Versioned rule engine — deterministic evaluation of declarations against rules.

No LLM calls, no randomness, no wall-clock reads inside evaluation.
inspection_date is an explicit input parameter.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import (
    Declaration as DeclDB,
    Rule as RuleDB,
    RuleSet as RuleSetDB,
    VerificationState,
)


class RuleSetError(Exception):
    """Raised when rule_set selection fails (zero or multiple matches)."""


# ---------------------------------------------------------------------------
# RuleSet selection
# ---------------------------------------------------------------------------

def select_ruleset(
    db: Session,
    jurisdiction: str,
    inspection_date: date,
) -> RuleSetDB:
    """Return the single matching RuleSet for jurisdiction + date.

    Raises RuleSetError on zero or multiple matches — never guesses.
    """
    candidates = (
        db.query(RuleSetDB)
        .filter(
            RuleSetDB.jurisdiction == jurisdiction,
            RuleSetDB.effective_from <= inspection_date,
            (RuleSetDB.effective_to.is_(None) | (RuleSetDB.effective_to > inspection_date)),
        )
        .all()
    )
    if len(candidates) == 0:
        raise RuleSetError(
            f"No rule_set found for jurisdiction='{jurisdiction}' on {inspection_date}"
        )
    if len(candidates) > 1:
        versions = [f"{r.rule_version} ({r.effective_from}–{r.effective_to})" for r in candidates]
        raise RuleSetError(
            f"Multiple overlapping rule_sets for jurisdiction='{jurisdiction}' on {inspection_date}: {versions}"
        )
    return candidates[0]


# ---------------------------------------------------------------------------
# Structured validation_conditions interpreter
# ---------------------------------------------------------------------------

def _check_numeric(value: Any, conditions: Dict[str, Any]) -> Optional[str]:
    """Check a numeric extracted_value against format constraints."""
    amount = None
    if isinstance(value, dict):
        amount = value.get("amount")
    elif isinstance(value, (int, float)):
        amount = value

    if amount is None:
        return "value is not numeric"

    if "min_value" in conditions and amount < conditions["min_value"]:
        return f"value {amount} below minimum {conditions['min_value']}"
    if "max_value" in conditions and amount > conditions["max_value"]:
        return f"value {amount} above maximum {conditions['max_value']}"
    return None


def _check_quantity(value: Any, conditions: Dict[str, Any]) -> Optional[str]:
    """Check a quantity_with_unit extracted_value."""
    if not isinstance(value, dict):
        return "value is not a quantity object"

    val = value.get("value")
    unit = value.get("unit")

    if val is None:
        return "quantity missing 'value'"
    if unit is None:
        return "quantity missing 'unit'"

    allowed = conditions.get("allowed_units", [])
    if allowed and unit.lower() not in [u.lower() for u in allowed]:
        return f"unit '{unit}' not in allowed units {allowed}"

    if "min_value" in conditions and val < conditions["min_value"]:
        return f"quantity value {val} below minimum {conditions['min_value']}"
    if "max_value" in conditions and val > conditions["max_value"]:
        return f"quantity value {val} above maximum {conditions['max_value']}"
    return None


def _check_text(value: Any, conditions: Dict[str, Any]) -> Optional[str]:
    """Check a text extracted_value."""
    text = str(value).strip() if value is not None else ""

    if conditions.get("must_be_present") and not text:
        return "text value is empty"

    min_len = conditions.get("min_length")
    if min_len is not None and len(text) < min_len:
        return f"text length {len(text)} below minimum {min_len}"
    return None


def _check_date(value: Any, conditions: Dict[str, Any]) -> Optional[str]:
    """Check a date extracted_value."""
    if value is None:
        return "date value is missing"
    # Accept string ISO dates
    if isinstance(value, str):
        try:
            date.fromisoformat(value)
        except ValueError:
            return f"date '{value}' is not valid ISO format"
    return None


_FORMAT_CHECKERS = {
    "numeric": _check_numeric,
    "quantity_with_unit": _check_quantity,
    "text": _check_text,
    "date": _check_date,
}


def validate_conditions(
    extracted_value: Any,
    confidence: float,
    conditions: Dict[str, Any],
) -> Tuple[bool, Optional[str]]:
    """Evaluate extracted_value + confidence against structured conditions.

    Returns (passed: bool, reason: str | None).
    reason is None when passed, a specific failure message when failed.
    """
    # Presence check
    if conditions.get("must_be_present"):
        if extracted_value is None:
            return False, "required declaration not found"
        if isinstance(extracted_value, str) and not extracted_value.strip():
            return False, "required declaration is empty"

    # Confidence check
    min_conf = conditions.get("min_confidence")
    if min_conf is not None and confidence < min_conf:
        return False, f"insufficient confidence ({confidence:.2f} < {min_conf})"

    # Format-specific checks
    fmt = conditions.get("format")
    if fmt and fmt in _FORMAT_CHECKERS:
        fail_reason = _FORMAT_CHECKERS[fmt](extracted_value, conditions)
        if fail_reason:
            return False, fail_reason

    return True, None


# ---------------------------------------------------------------------------
# Per-declaration evaluation
# ---------------------------------------------------------------------------

def _evaluate_declaration(
    decl: Optional[DeclDB],
    rule: RuleDB,
    product_category: Optional[str],
) -> Tuple[VerificationState, str, Optional[float]]:
    """Evaluate a single declaration against a rule.

    Returns (verdict, reason, confidence).
    """
    conditions = rule.validation_conditions or {}

    # 1. Applicability check
    applicability = (rule.applicability or "").lower()
    if product_category and applicability and "all" not in applicability:
        if product_category.lower() not in applicability:
            return VerificationState.NOT_APPLICABLE, f"rule not applicable to category '{product_category}'", None

    # 2. Declaration missing
    if decl is None:
        if conditions.get("must_be_present", False):
            return VerificationState.VIOLATION, "required declaration not found", None
        return VerificationState.NOT_APPLICABLE, "declaration not present and not required", None

    # 3. Conflict pass-through
    if hasattr(decl, "conflict") and decl.conflict:
        return VerificationState.CONFLICT, f"conflicting evidence for '{decl.field_name}'", decl.confidence

    # Use verdict field to detect conflict from pipeline
    verdict_val = decl.verdict.value if hasattr(decl.verdict, "value") else str(decl.verdict)
    if verdict_val == "CONFLICT":
        return VerificationState.CONFLICT, f"conflicting evidence for '{decl.field_name}'", decl.confidence

    # 4. Confidence check
    confidence = decl.confidence or 0.0
    min_conf = conditions.get("min_confidence")
    if min_conf is not None and confidence < min_conf:
        return VerificationState.NOT_VERIFIED, f"insufficient confidence ({confidence:.2f} < {min_conf})", confidence

    # 5. Run structured validation
    passed, fail_reason = validate_conditions(decl.extracted_value, confidence, conditions)
    if not passed:
        return VerificationState.VIOLATION, fail_reason or "validation failed", confidence

    return VerificationState.SATISFIED, "all conditions satisfied", confidence


# ---------------------------------------------------------------------------
# Severity ordering
# ---------------------------------------------------------------------------

_SEVERITY = {
    VerificationState.VIOLATION: 0,
    VerificationState.CONFLICT: 1,
    VerificationState.NOT_VERIFIED: 2,
    VerificationState.SATISFIED: 3,
    VerificationState.NOT_APPLICABLE: 4,
}


def _worst(statuses: List[VerificationState]) -> VerificationState:
    """Return the most severe status, ignoring NOT_APPLICABLE."""
    relevant = [s for s in statuses if s != VerificationState.NOT_APPLICABLE]
    if not relevant:
        return VerificationState.NOT_APPLICABLE
    return min(relevant, key=lambda s: _SEVERITY[s])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class RuleEngine:
    """Evaluate a scan's declarations against a versioned rule set."""

    def __init__(self, db: Session, jurisdiction: str = "India"):
        self.db = db
        self.jurisdiction = jurisdiction

    def evaluate(
        self,
        declarations: List[DeclDB],
        inspection_date: date,
        product_category: Optional[str] = None,
    ) -> Tuple[VerificationState, List[Dict[str, Any]]]:
        """Evaluate all declarations against the matching rule set.

        Returns (overall_status, per_declaration_results).
        Each result dict: {rule_id, field_name, verdict, reason, confidence}.
        """
        ruleset = select_ruleset(self.db, self.jurisdiction, inspection_date)
        rules_by_field = {r.required_declaration: r for r in ruleset.rules}

        results: List[Dict[str, Any]] = []
        verdicts: List[VerificationState] = []

        for rule in ruleset.rules:
            # Find matching declaration by field_name
            decl = None
            for d in declarations:
                if d.field_name == rule.required_declaration:
                    decl = d
                    break

            verdict, reason, confidence = _evaluate_declaration(decl, rule, product_category)

            results.append({
                "rule_id": rule.rule_id,
                "field_name": rule.required_declaration,
                "verdict": verdict,
                "reason": reason,
                "confidence": confidence,
            })
            verdicts.append(verdict)

        overall = _worst(verdicts)
        return overall, results
