"""API tests for the versioned /rules endpoint."""

import os
import uuid
from datetime import date, timedelta

# app.config.Settings requires JWT_SECRET at import time. Set it before any
# project imports so this test doesn't depend on a developer's local .env file.
os.environ.setdefault("JWT_SECRET", "test-secret")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.database as _db  # noqa: E402
import app.main as _main  # noqa: E402
from app.db.models import Base, Rule as RuleDB, RuleSet as RuleSetDB  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(db_engine, monkeypatch):
    # Match the application's existing endpoint pattern: handlers read the
    # module-level `engine` and open their own `Session(engine)`. Overriding
    # via monkeypatch (rather than a permanent module-level reassignment)
    # keeps this scoped to each test so it can't leak into other test files
    # (e.g. test_flags.py, which does its own module-level engine swap).
    monkeypatch.setattr(_main, "engine", db_engine)
    monkeypatch.setattr(_db, "engine", db_engine)
    with TestClient(app) as test_client:
        yield test_client


def _seed_ruleset(
    db: Session,
    *,
    version: str,
    effective_from: date,
    effective_to: date | None,
    prefix: str,
    jurisdiction: str = "India",
):
    rule_set = RuleSetDB(
        id=uuid.uuid4(),
        source="Legal Metrology (Packaged Commodities) Rules, 2011",
        rule_version=version,
        effective_from=effective_from,
        effective_to=effective_to,
        jurisdiction=jurisdiction,
    )
    db.add(rule_set)
    db.flush()

    db.add(
        RuleDB(
            rule_id=f"{prefix}-001",
            rule_set_id=rule_set.id,
            source_document="Legal Metrology Act, 2009",
            clause="Rule 6",
            applicability="All pre-packaged goods",
            required_declaration="mrp",
            validation_conditions={"must_be_present": True},
            measurement_requirements=None,
            exceptions=[],
            effective_date=effective_from,
            evidence_requirements=["OCR"],
        )
    )
    db.commit()
    return rule_set


def test_get_rules_returns_active_ruleset_and_rules(client, db_engine):
    today = date.today()

    with Session(db_engine) as db:
        rule_set = _seed_ruleset(
            db,
            version="2026.1",
            effective_from=today - timedelta(days=1),
            effective_to=None,
            prefix="API",
        )
        rule_set_id = str(rule_set.id)  # captured while still attached to db

    response = client.get("/rules")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == rule_set_id
    assert body["source"] == "Legal Metrology (Packaged Commodities) Rules, 2011"
    assert body["rule_version"] == "2026.1"
    assert body["jurisdiction"] == "India"
    assert len(body["rules"]) == 1
    assert body["rules"][0]["rule_id"] == "API-001"
    assert body["rules"][0]["required_declaration"] == "mrp"


def test_get_rules_honors_effective_date(client, db_engine):
    old_date = date(2025, 1, 1)
    new_date = date(2026, 1, 1)

    with Session(db_engine) as db:
        _seed_ruleset(
            db,
            version="2025.1",
            effective_from=old_date,
            effective_to=new_date,
            prefix="OLD",
        )
        _seed_ruleset(
            db,
            version="2026.1",
            effective_from=new_date,
            effective_to=None,
            prefix="NEW",
        )

    response = client.get("/rules", params={"effective_date": "2025-06-01"})
    assert response.status_code == 200
    assert response.json()["rule_version"] == "2025.1"
    assert response.json()["rules"][0]["rule_id"] == "OLD-001"

    response = client.get("/rules", params={"effective_date": "2026-06-01"})
    assert response.status_code == 200
    assert response.json()["rule_version"] == "2026.1"
    assert response.json()["rules"][0]["rule_id"] == "NEW-001"


def test_get_rules_returns_meaningful_404_when_no_ruleset_matches(client):
    response = client.get(
        "/rules",
        params={"effective_date": "2020-01-01", "jurisdiction": "India"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "No rule_set found for jurisdiction='India' on 2020-01-01"
    )
