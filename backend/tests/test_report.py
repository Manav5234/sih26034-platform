"""Tests for Phase 13 report data assembly."""
import pytest
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import (
    Base, Product, Scan, Declaration, Evidence, Inspection, InspectionLocation,
    Officer, Image, ComplianceResult,
    VerificationState, ScanStatus, EvidenceSourceType, OfficerRole,
)
from app.report import assemble_report, ReportData


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _make_officer(session):
    o = Officer(id=uuid4(), name="Test Inspector", email="test@test.com", password_hash="x", role=OfficerRole.INSPECTOR)
    session.add(o)
    session.commit()
    return o


def _make_product(session):
    p = Product(id=uuid4(), identity="Test Product", brand="TestBrand", barcode_code="123456", category="food", mrp_amount=99.0, mrp_currency="INR")
    session.add(p)
    session.commit()
    return p


def _make_scan(session, product_id=None, overall_status=VerificationState.SATISFIED):
    s = Scan(id=uuid4(), status=ScanStatus.COMPLETED, overall_status=overall_status, product_id=product_id)
    session.add(s)
    session.commit()
    return s


def _make_image(session, scan_id):
    img = Image(id=uuid4(), scan_id=scan_id, url="/uploads/test/img.jpg")
    session.add(img)
    session.commit()
    return img


def _make_declaration(session, scan_id, field_name="mrp", verdict=VerificationState.SATISFIED, officer_correction=None):
    d = Declaration(
        id=uuid4(), scan_id=scan_id, field_name=field_name,
        extracted_value={"amount": 99, "currency": "INR"},
        rule_id="LMR-2024-001", verdict=verdict, reason="test",
        confidence=0.85, officer_correction=officer_correction,
    )
    session.add(d)
    session.commit()
    return d


def _make_evidence(session, decl_id, image_id, source_type=EvidenceSourceType.OCR):
    e = Evidence(
        id=uuid4(), source_type=source_type, raw_text="MRP Rs. 99",
        confidence=0.9, image_id=image_id, declaration_id=decl_id,
    )
    session.add(e)
    session.commit()
    return e


class TestReportAssembly:
    def test_basic_report(self, db_session):
        product = _make_product(db_session)
        scan = _make_scan(db_session, product_id=product.id)
        img = _make_image(db_session, scan.id)
        decl = _make_declaration(db_session, scan.id)
        _make_evidence(db_session, decl.id, img.id)

        report = assemble_report(scan.id, db_session)
        assert isinstance(report, ReportData)
        assert report.scan_id == str(scan.id)
        assert report.product is not None
        assert report.product["name"] == "Test Product"
        assert len(report.fields) == 1
        assert report.fields[0].field_name == "mrp"
        assert report.fields[0].verdict == "SATISFIED"
        assert len(report.fields[0].evidence) == 1

    def test_conflict_field_renders(self, db_session):
        scan = _make_scan(db_session, overall_status=VerificationState.CONFLICT)
        decl = _make_declaration(db_session, scan.id, verdict=VerificationState.CONFLICT)
        report = assemble_report(scan.id, db_session)
        assert report.fields[0].verdict == "CONFLICT"
        assert report.summary["CONFLICT"] == 1

    def test_not_verified_field_renders(self, db_session):
        scan = _make_scan(db_session, overall_status=VerificationState.NOT_VERIFIED)
        decl = _make_declaration(db_session, scan.id, verdict=VerificationState.NOT_VERIFIED)
        report = assemble_report(scan.id, db_session)
        assert report.fields[0].verdict == "NOT_VERIFIED"
        assert report.summary["NOT_VERIFIED"] == 1

    def test_officer_correction_in_report(self, db_session):
        scan = _make_scan(db_session)
        correction = {
            "officer_id": str(uuid4()),
            "officer_name": "Inspector A",
            "corrected_value": {"amount": 199, "currency": "INR"},
            "reason": "OCR missed MRP",
            "corrected_at": "2026-09-05T10:00:00",
        }
        decl = _make_declaration(db_session, scan.id, officer_correction=correction)
        report = assemble_report(scan.id, db_session)
        assert report.fields[0].officer_correction is not None
        assert report.fields[0].officer_correction["officer_name"] == "Inspector A"

    def test_inspection_with_location(self, db_session):
        officer = _make_officer(db_session)
        scan = _make_scan(db_session)
        insp = Inspection(id=uuid4(), scan_id=scan.id, officer_id=officer.id, actions=[])
        db_session.add(insp)
        db_session.flush()
        loc = InspectionLocation(
            id=uuid4(), inspection_id=insp.id,
            latitude=28.6139, longitude=77.2090,
            accuracy_meters=15.0, source="GPS",
            captured_at=datetime.now(timezone.utc),
        )
        db_session.add(loc)
        db_session.commit()

        report = assemble_report(scan.id, db_session)
        assert len(report.inspections) == 1
        assert report.inspections[0].location is not None
        assert report.inspections[0].location.source == "GPS"
        assert report.inspections[0].location.latitude == 28.6139

    def test_manual_location_source(self, db_session):
        officer = _make_officer(db_session)
        scan = _make_scan(db_session)
        insp = Inspection(id=uuid4(), scan_id=scan.id, officer_id=officer.id, actions=[])
        db_session.add(insp)
        db_session.flush()
        loc = InspectionLocation(
            id=uuid4(), inspection_id=insp.id,
            latitude=19.0760, longitude=72.8777,
            accuracy_meters=None, source="MANUAL",
            address_text="Mumbai, Maharashtra",
            captured_at=datetime.now(timezone.utc),
        )
        db_session.add(loc)
        db_session.commit()

        report = assemble_report(scan.id, db_session)
        assert report.inspections[0].location.source == "MANUAL"
        assert report.inspections[0].location.accuracy_meters is None
        assert report.inspections[0].location.address_text == "Mumbai, Maharashtra"
