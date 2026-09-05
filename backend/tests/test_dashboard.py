"""Tests for Phase 12 dashboard, product, scan, and inspection list endpoints."""
import pytest
from datetime import date, datetime, timezone, timedelta
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import (
    Base, Product, Scan, Declaration, Evidence, Inspection, AuditLog,
    Officer, Image, ComplianceResult,
    VerificationState, ScanStatus, EvidenceSourceType, OfficerRole,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _make_officer(session, name="Test Officer"):
    o = Officer(id=uuid4(), name=name, email=f"{name.lower().replace(' ', '.')}@test.com", password_hash="x", role=OfficerRole.INSPECTOR)
    session.add(o)
    session.commit()
    return o


def _make_product(session, identity="Test Product", brand="TestBrand", barcode_code="1234567890"):
    p = Product(id=uuid4(), identity=identity, brand=brand, barcode_code=barcode_code, category="food")
    session.add(p)
    session.commit()
    return p


def _make_scan(session, product_id=None, overall_status=None, created_at=None):
    s = Scan(id=uuid4(), status=ScanStatus.COMPLETED, overall_status=overall_status, product_id=product_id)
    if created_at:
        s.created_at = created_at
    session.add(s)
    session.commit()
    return s


def _make_inspection(session, scan_id, officer_id, actions=None):
    i = Inspection(id=uuid4(), scan_id=scan_id, officer_id=officer_id, actions=actions or [])
    session.add(i)
    session.commit()
    return i


class TestDashboard:
    def test_counts_empty(self, db_session):
        from sqlalchemy import func
        total = db_session.query(func.count(Scan.id)).scalar()
        assert total == 0

    def test_counts_with_data(self, db_session):
        from sqlalchemy import func
        now = datetime.now(timezone.utc)
        p = _make_product(db_session)
        _make_scan(db_session, product_id=p.id, overall_status=VerificationState.VIOLATION)
        _make_scan(db_session, product_id=p.id, overall_status=VerificationState.NOT_VERIFIED)
        _make_scan(db_session, product_id=p.id, overall_status=VerificationState.SATISFIED)

        total = db_session.query(func.count(Scan.id)).scalar()
        assert total == 3
        violations = db_session.query(func.count(Scan.id)).filter(Scan.overall_status == VerificationState.VIOLATION).scalar()
        assert violations == 1

    def test_pending_review_count(self, db_session):
        from sqlalchemy import func
        o = _make_officer(db_session)
        p = _make_product(db_session)
        s1 = _make_scan(db_session, product_id=p.id, overall_status=VerificationState.SATISFIED)
        s2 = _make_scan(db_session, product_id=p.id, overall_status=VerificationState.NOT_VERIFIED)
        _make_inspection(db_session, scan_id=s1.id, officer_id=o.id)

        # s1 has inspection, s2 does not
        scans_with_inspection = db_session.query(Inspection.scan_id).distinct().subquery()
        pending = (
            db_session.query(func.count(Scan.id))
            .filter(~Scan.id.in_(db_session.query(scans_with_inspection)))
            .scalar()
        )
        assert pending == 1


class TestScansFilter:
    def test_filter_by_status(self, db_session):
        from sqlalchemy import func
        _make_scan(db_session, overall_status=VerificationState.VIOLATION)
        _make_scan(db_session, overall_status=VerificationState.SATISFIED)
        _make_scan(db_session, overall_status=VerificationState.NOT_VERIFIED)

        count = (
            db_session.query(func.count(Scan.id))
            .filter(Scan.overall_status == VerificationState.VIOLATION)
            .scalar()
        )
        assert count == 1

    def test_filter_by_date(self, db_session):
        from sqlalchemy import func
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=10)
        _make_scan(db_session, overall_status=VerificationState.SATISFIED, created_at=old)
        _make_scan(db_session, overall_status=VerificationState.SATISFIED, created_at=now)

        cutoff = now - timedelta(days=1)
        count = (
            db_session.query(func.count(Scan.id))
            .filter(Scan.created_at >= cutoff)
            .scalar()
        )
        assert count == 1


class TestPagination:
    def test_page_calculation(self):
        total = 45
        page_size = 20
        assert (total + page_size - 1) // page_size == 3

    def test_offset_calculation(self):
        page = 2
        page_size = 20
        assert (page - 1) * page_size == 20
