"""Tests for consumer flag feature — model, schemas, endpoints."""
import os
import uuid
from unittest.mock import MagicMock

# Set test database URL BEFORE importing any app modules
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("JWT_SECRET", "test-secret-key")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.main import app
from app.database import engine as app_engine

from app.db.models import (
    Officer, OfficerRole, Scan, ScanStatus, ConsumerFlag, FlagStatus, AuditLog,
)

# Replace app engine with StaticPool-backed in-memory SQLite so all
# Session(engine) calls share the same DB (including endpoints).
_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(_test_engine)
TestSession = sessionmaker(bind=_test_engine)

# Patch app's engine so endpoints use our test DB
import app.main as _main
import app.database as _db
_main.engine = _test_engine
_db.engine = _test_engine


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def db_session():
    session = TestSession()
    yield session
    # Clean up all test data between tests (StaticPool shares state)
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    session.close()


@pytest.fixture
def admin_officer(db_session):
    from app.auth import hash_password
    o = Officer(
        id=uuid.uuid4(),
        name="Admin Test",
        email="admin@test.com",
        password_hash=hash_password("correct-password"),
        role=OfficerRole.ADMIN,
    )
    db_session.add(o)
    db_session.commit()
    return o


@pytest.fixture
def completed_scan(db_session):
    scan = Scan(id=uuid.uuid4(), status=ScanStatus.COMPLETED)
    db_session.add(scan)
    db_session.commit()
    return scan


# --- Model tests ---


def test_consumer_flag_model(db_session, completed_scan):
    flag = ConsumerFlag(
        id=uuid.uuid4(),
        scan_id=completed_scan.id,
        reported_fields=["mrp", "net_quantity"],
        reporter_note="MRP looks wrong",
        reporter_contact="test@example.com",
        status=FlagStatus.NEW,
    )
    db_session.add(flag)
    db_session.commit()
    assert flag.id is not None
    assert flag.status == FlagStatus.NEW
    assert flag.reported_fields == ["mrp", "net_quantity"]


def test_flag_status_enum():
    assert FlagStatus.NEW.value == "NEW"
    assert FlagStatus.ACKNOWLEDGED.value == "ACKNOWLEDGED"
    assert FlagStatus.RESOLVED.value == "RESOLVED"
    assert FlagStatus.DISMISSED.value == "DISMISSED"


# --- Schema tests ---


def test_flag_create_request_schema():
    from app.schemas.flag import FlagCreateRequest
    req = FlagCreateRequest(reported_fields=["mrp"], reporter_note="test")
    assert req.reported_fields == ["mrp"]
    assert req.reporter_note == "test"
    assert req.reporter_contact is None


def test_flag_create_response_schema():
    from app.schemas.flag import FlagCreateResponse
    resp = FlagCreateResponse(id=uuid.uuid4(), status=FlagStatus.NEW)
    assert resp.status == FlagStatus.NEW


def test_flag_review_request_schema():
    from app.schemas.flag import FlagReviewRequest
    req = FlagReviewRequest(status=FlagStatus.RESOLVED, officer_notes="Fixed")
    assert req.status == FlagStatus.RESOLVED
    assert req.officer_notes == "Fixed"


# --- Endpoint tests ---


def test_create_flag_requires_valid_scan(client):
    fake_id = uuid.uuid4()
    resp = client.post(f"/scan/{fake_id}/flag", json={"reported_fields": ["mrp"]})
    assert resp.status_code == 404


def test_create_flag_success(client, completed_scan):
    resp = client.post(f"/scan/{completed_scan.id}/flag", json={
        "reported_fields": ["mrp", "net_quantity"],
        "reporter_note": "MRP label is unclear",
        "reporter_contact": "user@example.com",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["status"] == "NEW"


def test_create_flag_minimal(client, completed_scan):
    resp = client.post(f"/scan/{completed_scan.id}/flag", json={"reported_fields": ["mrp"]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "NEW"


def test_list_flags_requires_auth(client):
    resp = client.get("/flags")
    assert resp.status_code == 401


def test_list_flags_requires_admin_or_inspector(client, db_session):
    from app.auth import create_access_token
    viewer = Officer(
        id=uuid.uuid4(), name="Viewer", email="viewer@test.com",
        password_hash="x", role=OfficerRole.VIEWER,
    )
    db_session.add(viewer)
    db_session.commit()
    token = create_access_token(viewer.id, viewer.role.value)
    resp = client.get("/flags", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_list_flags_as_admin(client, admin_officer):
    from app.auth import create_access_token
    token = create_access_token(admin_officer.id, admin_officer.role.value)
    resp = client.get("/flags", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


def test_get_flag_requires_auth(client):
    resp = client.get(f"/flags/{uuid.uuid4()}")
    assert resp.status_code == 401


def test_get_flag_not_found(client, admin_officer):
    from app.auth import create_access_token
    token = create_access_token(admin_officer.id, admin_officer.role.value)
    resp = client.get(f"/flags/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


def test_review_flag_requires_auth(client):
    resp = client.post(f"/flags/{uuid.uuid4()}/review", json={"status": "ACKNOWLEDGED"})
    assert resp.status_code == 401


def test_review_flag_success(client, db_session, completed_scan, admin_officer):
    from app.auth import create_access_token
    flag = ConsumerFlag(
        id=uuid.uuid4(), scan_id=completed_scan.id,
        reported_fields=["mrp"], status=FlagStatus.NEW,
    )
    db_session.add(flag)
    db_session.commit()

    token = create_access_token(admin_officer.id, admin_officer.role.value)
    resp = client.post(
        f"/flags/{flag.id}/review",
        json={"status": "RESOLVED", "officer_notes": "Checked and confirmed"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "RESOLVED"
    assert data["officer_notes"] == "Checked and confirmed"

    audit = db_session.query(AuditLog).filter(
        AuditLog.target_type == "consumer_flag",
        AuditLog.target_id == flag.id,
    ).first()
    assert audit is not None
    assert audit.action == "flag_resolved"
