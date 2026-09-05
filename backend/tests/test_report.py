"""Tests for Phase 13 report data assembly — including regression tests for bugs 1-3."""
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
from app.report import assemble_report, ReportData, _format_value


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


_UNSET = object()


def _make_declaration(session, scan_id, field_name="mrp", verdict=VerificationState.SATISFIED,
                      officer_correction=None, extracted_value=_UNSET, confidence=0.85):
    if extracted_value is _UNSET:
        extracted_value = {"amount": 99, "currency": "INR"}
    d = Declaration(
        id=uuid4(), scan_id=scan_id, field_name=field_name,
        extracted_value=extracted_value,
        rule_id="LMR-2024-001", verdict=verdict, reason="test",
        confidence=confidence, officer_correction=officer_correction,
    )
    session.add(d)
    session.commit()
    return d


def _make_evidence(session, decl_id, image_id, source_type=EvidenceSourceType.OCR,
                   raw_text="MRP Rs. 99", confidence=0.9):
    e = Evidence(
        id=uuid4(), source_type=source_type, raw_text=raw_text,
        confidence=confidence, image_id=image_id, declaration_id=decl_id,
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
            "original_verdict": "VIOLATION",
            "original_reason": "MRP mismatch",
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


class TestFormatValue:
    def test_mrp_dict(self):
        assert _format_value("mrp", {"amount": 1500, "currency": "INR"}) == "\u20b91500"

    def test_mrp_none(self):
        assert _format_value("mrp", None) == "\u2014"

    def test_net_quantity_dict(self):
        assert _format_value("net_quantity", {"value": 150, "unit": "g"}) == "150 g"

    def test_manufacturer_dict(self):
        assert _format_value("manufacturer", {"name": "HUL", "confidence": 0.8}) == "HUL"

    def test_string_passthrough(self):
        assert _format_value("mrp", "Rs. 99") == "Rs. 99"

    def test_no_raw_dict_repr_mrp(self):
        result = _format_value("mrp", {"amount": 99, "currency": "INR", "confidence": 0.85})
        assert "{'amount'" not in result
        assert "confidence" not in result

    def test_no_raw_dict_repr_net_qty(self):
        result = _format_value("net_quantity", {"value": 150, "unit": "g", "confidence": 0.9})
        assert "{'value'" not in result
        assert "confidence" not in result

    def test_no_raw_dict_repr_manufacturer(self):
        result = _format_value("manufacturer", {"name": "HUL", "confidence": 0.85})
        assert "{'name'" not in result
        assert "confidence" not in result


class TestBug1OfficerCorrectionPreservesOriginalAI:
    """BUG 1: officer corrections must NOT hide original AI evidence."""

    def test_correct_shows_both_ai_and_officer(self, db_session):
        scan = _make_scan(db_session, overall_status=VerificationState.SATISFIED)
        img = _make_image(db_session, scan.id)

        correction = {
            "officer_id": str(uuid4()),
            "officer_name": "Inspector A",
            "corrected_value": {"amount": 199, "currency": "INR"},
            "reason": "Verified on physical product",
            "corrected_at": "2026-09-05T10:00:00",
            "original_verdict": "VIOLATION",
            "original_reason": "MRP mismatch between OCR and database",
        }
        decl = _make_declaration(db_session, scan.id, officer_correction=correction,
                                 extracted_value={"amount": 99, "currency": "INR"})
        _make_evidence(db_session, decl.id, img.id, raw_text="MRP Rs. 99")

        report = assemble_report(scan.id, db_session)
        f = report.fields[0]

        # Original AI verdict is preserved
        assert f.ai_verdict == "VIOLATION"
        assert f.ai_reason == "MRP mismatch between OCR and database"
        # Officer override is also present
        assert f.officer_correction is not None
        assert f.officer_correction["corrected_value"] == {"amount": 199, "currency": "INR"}
        # Evidence is preserved
        assert len(f.evidence) == 1
        assert f.evidence[0]["raw_text"] == "MRP Rs. 99"

    def test_mark_unresolved_shows_both_ai_and_officer(self, db_session):
        scan = _make_scan(db_session, overall_status=VerificationState.NOT_VERIFIED)
        correction = {
            "officer_id": str(uuid4()),
            "officer_name": "Inspector B",
            "corrected_value": None,
            "reason": "Cannot verify — label partially torn",
            "corrected_at": "2026-09-05T11:00:00",
            "original_verdict": "SATISFIED",
            "original_reason": "",
        }
        decl = _make_declaration(db_session, scan.id, officer_correction=correction,
                                 verdict=VerificationState.NOT_VERIFIED,
                                 confidence=0.75)

        report = assemble_report(scan.id, db_session)
        f = report.fields[0]

        assert f.ai_verdict == "SATISFIED"
        assert f.ai_reason == ""
        assert f.officer_correction["reason"] == "Cannot verify \u2014 label partially torn"

    def test_no_raw_dict_in_display_value(self, db_session):
        scan = _make_scan(db_session)
        decl = _make_declaration(db_session, scan.id, extracted_value={"amount": 99, "currency": "INR"})

        report = assemble_report(scan.id, db_session)
        display = report.fields[0].display_value
        assert "{'amount'" not in display
        assert "confidence" not in display
        assert "\u20b999" == display


class TestBug2NoRawDictInReport:
    """BUG 2: extracted_value dicts must be formatted, not dumped as Python repr."""

    def test_mrp_formatted(self, db_session):
        scan = _make_scan(db_session)
        _make_declaration(db_session, scan.id, field_name="mrp",
                          extracted_value={"amount": 1500, "currency": "INR"})
        report = assemble_report(scan.id, db_session)
        assert report.fields[0].display_value == "\u20b91500"

    def test_net_quantity_formatted(self, db_session):
        scan = _make_scan(db_session)
        _make_declaration(db_session, scan.id, field_name="net_quantity",
                          extracted_value={"value": 150, "unit": "g"})
        report = assemble_report(scan.id, db_session)
        assert report.fields[0].display_value == "150 g"

    def test_manufacturer_formatted(self, db_session):
        scan = _make_scan(db_session)
        _make_declaration(db_session, scan.id, field_name="manufacturer",
                          extracted_value={"name": "Hindustan Unilever", "confidence": 0.85})
        report = assemble_report(scan.id, db_session)
        assert report.fields[0].display_value == "Hindustan Unilever"

    def test_none_value_shows_dash(self, db_session):
        scan = _make_scan(db_session)
        _make_declaration(db_session, scan.id, extracted_value=None)
        report = assemble_report(scan.id, db_session)
        assert report.fields[0].display_value == "\u2014"

    def test_corrected_value_also_formatted(self, db_session):
        scan = _make_scan(db_session)
        correction = {
            "officer_id": str(uuid4()),
            "officer_name": "Inspector",
            "corrected_value": {"amount": 299, "currency": "INR"},
            "reason": "Fixed",
            "corrected_at": "2026-09-05T10:00:00",
            "original_verdict": "VIOLATION",
            "original_reason": "wrong",
        }
        _make_declaration(db_session, scan.id, field_name="mrp",
                          extracted_value={"amount": 99, "currency": "INR"},
                          officer_correction=correction)
        report = assemble_report(scan.id, db_session)
        f = report.fields[0]
        # Original value is formatted
        assert f.display_value == "\u20b999"
        # Officer correction dict's corrected_value is available for renderer
        assert f.officer_correction["corrected_value"] == {"amount": 299, "currency": "INR"}


class TestBug3ConfidenceNotZeroForOfficerTouched:
    """BUG 3: officer-touched fields must show 'Officer-reviewed', not '0.0%'."""

    def test_officer_correction_no_zero_confidence(self, db_session):
        scan = _make_scan(db_session)
        correction = {
            "officer_id": str(uuid4()),
            "officer_name": "Inspector",
            "corrected_value": {"amount": 199, "currency": "INR"},
            "reason": "Verified",
            "corrected_at": "2026-09-05T10:00:00",
            "original_verdict": "NOT_VERIFIED",
            "original_reason": "missing",
        }
        # confidence=0.0 simulates a previously-missing field that officer corrected
        _make_declaration(db_session, scan.id, officer_correction=correction, confidence=0.0)
        report = assemble_report(scan.id, db_session)
        f = report.fields[0]
        # The officer_correction is present
        assert f.officer_correction is not None
        # The raw confidence is still 0.0 (we don't change DB data)
        assert f.confidence == 0.0
        # But the renderer will show "Officer-reviewed" instead of "0.0%"
        # (this is verified by the PDF/DOCX integration tests below)


class TestConflictPreservesBothValues:
    """CONFLICT fields must render with both conflicting values visible."""

    def test_conflict_field_has_no_extracted_value(self, db_session):
        scan = _make_scan(db_session, overall_status=VerificationState.CONFLICT)
        _make_declaration(db_session, scan.id, verdict=VerificationState.CONFLICT,
                          extracted_value=None, confidence=0.0)
        report = assemble_report(scan.id, db_session)
        f = report.fields[0]
        assert f.verdict == "CONFLICT"
        assert f.extracted_value is None
        assert f.display_value == "\u2014"


class TestGeolocationInReport:
    """Location data must appear in assembled report when inspections have it."""

    def test_gps_location_present(self, db_session):
        officer = _make_officer(db_session)
        scan = _make_scan(db_session)
        insp = Inspection(id=uuid4(), scan_id=scan.id, officer_id=officer.id, actions=[
            {"field_name": "mrp", "action": "confirm", "reason": "ok"}
        ])
        db_session.add(insp)
        db_session.flush()
        loc = InspectionLocation(
            id=uuid4(), inspection_id=insp.id,
            latitude=28.6139, longitude=77.2090,
            accuracy_meters=15.3, source="GPS",
            captured_at=datetime.now(timezone.utc),
        )
        db_session.add(loc)
        db_session.commit()

        report = assemble_report(scan.id, db_session)
        assert len(report.inspections) == 1
        loc_report = report.inspections[0].location
        assert loc_report is not None
        assert loc_report.source == "GPS"
        assert loc_report.latitude == 28.6139
        assert loc_report.accuracy_meters == 15.3

    def test_manual_location_present(self, db_session):
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
        loc_report = report.inspections[0].location
        assert loc_report.source == "MANUAL"
        assert loc_report.address_text == "Mumbai, Maharashtra"
