"""Seed script: inserts one admin officer and one rule_set with 2-3 rules."""
import uuid
import os
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.db.models import Base, Officer, OfficerRole, RuleSet, Rule
from app.auth import hash_password

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@postgres:5432/sih26034",
)

OFFICER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
RULESET_ID = uuid.UUID("00000000-0000-0000-0000-000000000010")


def seed() -> None:
    engine = create_engine(DATABASE_URL)
    with Session(engine) as session:
        # Officer
        existing = session.get(Officer, OFFICER_ID)
        if not existing:
            session.add(Officer(
                id=OFFICER_ID,
                name="Admin User",
                email="admin@sih26034.local",
                password_hash=hash_password("admin123"),
                role=OfficerRole.ADMIN,
            ))
            print("  inserted officer")

        # RuleSet + Rules
        rs = session.get(RuleSet, RULESET_ID)
        if not rs:
            rs = RuleSet(
                id=RULESET_ID,
                source="Legal Metrology (Packaged Commodities) Rules, 2011",
                rule_version="2024.1",
                effective_from=date(2024, 1, 1),
                effective_to=None,
                jurisdiction="India",
            )
            session.add(rs)
            session.flush()

            rules = [
                Rule(
                    rule_id="LMR-2024-001",
                    rule_set_id=RULESET_ID,
                    source_document="Legal Metrology Act, 2009",
                    clause="Rule 5",
                    applicability="All pre-packaged goods",
                    required_declaration="mrp",
                    validation_conditions={
                        "must_be_present": True,
                        "min_confidence": 0.6,
                        "format": "numeric",
                        "min_value": 0,
                    },
                    measurement_requirements=None,
                    exceptions=["Exempt for export goods"],
                    effective_date=date(2024, 1, 1),
                    evidence_requirements=["OCR", "BARCODE"],
                ),
                Rule(
                    rule_id="LMR-2024-002",
                    rule_set_id=RULESET_ID,
                    source_document="Legal Metrology Act, 2009",
                    clause="Rule 6",
                    applicability="All pre-packaged goods",
                    required_declaration="net_quantity",
                    validation_conditions={
                        "must_be_present": True,
                        "min_confidence": 0.6,
                        "format": "quantity_with_unit",
                        "allowed_units": ["g", "kg", "ml", "l"],
                    },
                    measurement_requirements=None,
                    exceptions=[],
                    effective_date=date(2024, 1, 1),
                    evidence_requirements=["OCR"],
                ),
                Rule(
                    rule_id="LMR-2024-003",
                    rule_set_id=RULESET_ID,
                    source_document="Legal Metrology Act, 2009",
                    clause="Rule 7",
                    applicability="All pre-packaged goods",
                    required_declaration="manufacturer",
                    validation_conditions={
                        "must_be_present": True,
                        "min_confidence": 0.6,
                        "format": "text",
                        "min_length": 1,
                    },
                    measurement_requirements=None,
                    exceptions=[],
                    effective_date=date(2024, 1, 1),
                    evidence_requirements=["OCR", "PRODUCT_DATABASE"],
                ),
            ]
            for r in rules:
                session.add(r)
            print(f"  inserted rule_set with {len(rules)} rules")

        session.commit()
        print("seed done")


if __name__ == "__main__":
    seed()
