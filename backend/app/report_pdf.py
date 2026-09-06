"""PDF report renderer using ReportLab."""
import io
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.report import ReportData, _format_date_value

_DASH = "\u2014"

# Bug 4 fix: Register DejaVu Sans (Unicode-capable, ships with the base
# Debian image) so that ₹ (U+20B9) and other currency glyphs render
# correctly instead of as missing-glyph boxes.
_DEJAVU_DIR = "/usr/share/fonts/truetype/dejavu"
_DEJAVU_NORMAL = os.path.join(_DEJAVU_DIR, "DejaVuSans.ttf")
_DEJAVU_BOLD = os.path.join(_DEJAVU_DIR, "DejaVuSans-Bold.ttf")

if os.path.exists(_DEJAVU_NORMAL):
    pdfmetrics.registerFont(TTFont("DejaVuSans", _DEJAVU_NORMAL))
    pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", _DEJAVU_BOLD))
    from reportlab.pdfbase.pdfmetrics import registerFontFamily
    registerFontFamily("DejaVuSans", normal="DejaVuSans", bold="DejaVuSans-Bold")
    _BASE_FONT = "DejaVuSans"
    _BASE_FONT_BOLD = "DejaVuSans-Bold"
else:
    # Fallback: if DejaVu isn't found (e.g. local dev on Windows), use Helvetica
    _BASE_FONT = "Helvetica"
    _BASE_FONT_BOLD = "Helvetica-Bold"

VERDICT_COLORS = {
    "SATISFIED": colors.HexColor("#16a34a"),
    "VIOLATION": colors.HexColor("#dc2626"),
    "NOT_VERIFIED": colors.HexColor("#d97706"),
    "CONFLICT": colors.HexColor("#7c3aed"),
}


def render_pdf(report: ReportData) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle("Title2", parent=styles["Title"], fontName=_BASE_FONT_BOLD, fontSize=16, spaceAfter=6)
    heading_style = ParagraphStyle("Heading2", parent=styles["Heading2"], fontName=_BASE_FONT_BOLD, fontSize=13, spaceAfter=4, spaceBefore=10)
    body_style = ParagraphStyle("Body2", parent=styles["BodyText"], fontName=_BASE_FONT, fontSize=9, leading=12)
    small_style = ParagraphStyle("Small", parent=styles["BodyText"], fontName=_BASE_FONT, fontSize=8, leading=10, textColor=colors.grey)

    # Title
    story.append(Paragraph("Legal Metrology Compliance Report", title_style))
    story.append(Paragraph(f"Scan ID: {report.scan_id}", body_style))
    story.append(Paragraph(f"Generated: {report.generated_at}", small_style))
    story.append(Spacer(1, 6*mm))

    # Overall status
    status = report.overall_status or "UNKNOWN"
    story.append(Paragraph(f"Overall Status: <b>{status}</b>", body_style))
    story.append(Spacer(1, 4*mm))

    # Product info
    if report.product:
        story.append(Paragraph("Product Information", heading_style))
        p = report.product
        product_data = [
            ["Field", "Value"],
            ["Name", p.get("name") or "\u2014"],
            ["Brand", p.get("brand") or "\u2014"],
            ["Category", p.get("category") or "\u2014"],
            ["Manufacturer", p.get("manufacturer") or "\u2014"],
            ["Barcode", p.get("barcode") or "\u2014"],
            ["MRP", p.get("mrp") or "\u2014"],
            ["Net Quantity", p.get("quantity") or "\u2014"],
        ]
        t = Table(product_data, colWidths=[100, 350])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 6*mm))

    # Declarations
    story.append(Paragraph("Extracted Declarations", heading_style))
    for f in report.fields:
        vcolor = VERDICT_COLORS.get(f.verdict, colors.black)

        # Show verdict: if officer-corrected, show original AI verdict + officer override
        if f.officer_correction and f.ai_verdict:
            ai_vcolor = VERDICT_COLORS.get(f.ai_verdict, colors.black)
            story.append(Paragraph(
                f"<b>{f.field_name}</b> \u2014 "
                f"<font color='{ai_vcolor}'>AI: {f.ai_verdict}</font> \u2192 "
                f"<font color='{vcolor}'>Officer: {f.verdict}</font>",
                body_style
            ))
        else:
            story.append(Paragraph(
                f"<b>{f.field_name}</b> \u2014 <font color='{vcolor}'>{f.verdict}</font>",
                body_style
            ))

        # Nutrition facts: render as table
        if f.field_name == "nutrition_facts" and isinstance(f.extracted_value, list):
            nutrition_data = [["Nutrient", "Value", "Unit", "Confidence"]]
            for n in f.extracted_value:
                val = n.get("value")
                nutrition_data.append([
                    n.get("nutrient", "").replace("_", " ").title(),
                    f"{val}" if val is not None else "\u2014",
                    n.get("unit", ""),
                    f"{n.get('confidence', 0):.0%}",
                ])
            nt = Table(nutrition_data, colWidths=[100, 60, 40, 70])
            nt.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(nt)
        # Date fields: render as readable string
        elif f.field_name in ("manufacture_date", "expiry_date") and isinstance(f.extracted_value, dict):
            story.append(Paragraph(f"  Value: {_format_date_value(f.extracted_value)}", body_style))
        # Cautions: render as quoted text or "Not present"
        elif f.field_name == "cautions":
            if f.extracted_value and isinstance(f.extracted_value, dict) and f.extracted_value.get("present"):
                story.append(Paragraph(f"  Value: \"{f.extracted_value.get('text', '')}\"", body_style))
            else:
                story.append(Paragraph("  Value: Not present", body_style))
        # Default: standard value display
        else:
            story.append(Paragraph(f"  Value: {f.display_value}", body_style))

        # Reason: show both original AI reason and officer override reason if corrected
        if f.officer_correction and f.ai_reason:
            story.append(Paragraph(f"  AI Reason: {f.ai_reason}", small_style))
            story.append(Paragraph(f"  Officer Note: {f.reason}", small_style))
        elif f.reason:
            story.append(Paragraph(f"  Reason: {f.reason}", body_style))

        # Confidence: show "Officer-reviewed" for officer-touched fields, percentage otherwise
        if f.officer_correction:
            story.append(Paragraph(f"  Confidence: Officer-reviewed | Rule: {f.rule_id or _DASH}", small_style))
        else:
            story.append(Paragraph(f"  Confidence: {f.confidence:.1%} | Rule: {f.rule_id or _DASH}", small_style))

        # Evidence
        if f.evidence:
            for ev in f.evidence:
                story.append(Paragraph(
                    f"    [{ev['source_label']}] \"{ev.get('raw_text', '')}\" (conf: {ev['confidence']:.0%})",
                    small_style
                ))

        # Officer correction
        if f.officer_correction:
            oc = f.officer_correction
            corrected_display = oc.get("corrected_value", "\u2014")
            if isinstance(corrected_display, dict):
                from app.report import _format_value
                corrected_display = _format_value(f.field_name, corrected_display)
            story.append(Paragraph(
                f"    Officer Correction: {oc.get('officer_name', 'Officer')} set to {corrected_display} \u2014 {oc.get('reason', '')}",
                ParagraphStyle("Correction", parent=body_style, fontName=_BASE_FONT, textColor=colors.HexColor("#2563eb"), fontSize=8)
            ))

        story.append(Spacer(1, 2*mm))

    # Inspections
    if report.inspections:
        story.append(Paragraph("Officer Reviews", heading_style))
        for insp in report.inspections:
            story.append(Paragraph(f"Officer: {insp.officer_name} | {insp.created_at}", body_style))
            if insp.location:
                loc = insp.location
                loc_text = f"Location: ({loc.latitude:.6f}, {loc.longitude:.6f})"
                if loc.accuracy_meters:
                    loc_text += f" \u00b1{loc.accuracy_meters:.0f}m"
                loc_text += f" [source: {loc.source}]"
                if loc.address_text:
                    loc_text += f" \u2014 {loc.address_text}"
                story.append(Paragraph(loc_text, small_style))
            for a in insp.actions:
                story.append(Paragraph(
                    f"  {a.get('action', '')}: {a.get('field_name', '')} \u2014 {a.get('reason', '')}",
                    small_style
                ))
            story.append(Spacer(1, 3*mm))

    # Summary
    story.append(Paragraph("Summary", heading_style))
    s = report.summary
    summary_data = [
        ["Verdict", "Count"],
        ["Satisfied", str(s.get("SATISFIED", 0))],
        ["Violation", str(s.get("VIOLATION", 0))],
        ["Not Verified", str(s.get("NOT_VERIFIED", 0))],
        ["Conflict", str(s.get("CONFLICT", 0))],
    ]
    t = Table(summary_data, colWidths=[120, 60])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
    ]))
    story.append(t)

    doc.build(story)
    return buf.getvalue()
