"""PDF report renderer using ReportLab."""
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_LEFT, TA_CENTER

from app.report import ReportData


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

    title_style = ParagraphStyle("Title2", parent=styles["Title"], fontSize=16, spaceAfter=6)
    heading_style = ParagraphStyle("Heading2", parent=styles["Heading2"], fontSize=13, spaceAfter=4, spaceBefore=10)
    body_style = ParagraphStyle("Body2", parent=styles["BodyText"], fontSize=9, leading=12)
    small_style = ParagraphStyle("Small", parent=styles["BodyText"], fontSize=8, leading=10, textColor=colors.grey)

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
            ["Name", p.get("name") or "—"],
            ["Brand", p.get("brand") or "—"],
            ["Category", p.get("category") or "—"],
            ["Manufacturer", p.get("manufacturer") or "—"],
            ["Barcode", p.get("barcode") or "—"],
            ["MRP", p.get("mrp") or "—"],
            ["Net Quantity", p.get("quantity") or "—"],
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
        story.append(Paragraph(
            f"<b>{f.field_name}</b> — <font color='{vcolor}'>{f.verdict}</font>",
            body_style
        ))
        if f.extracted_value is not None:
            story.append(Paragraph(f"  Value: {f.extracted_value}", body_style))
        if f.reason:
            story.append(Paragraph(f"  Reason: {f.reason}", body_style))
        story.append(Paragraph(f"  Confidence: {f.confidence:.1%} | Rule: {f.rule_id or '—'}", small_style))

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
            story.append(Paragraph(
                f"    Officer Correction: {oc.get('officer_name', 'Officer')} set to {oc.get('corrected_value')} — {oc.get('reason', '')}",
                ParagraphStyle("Correction", parent=body_style, textColor=colors.HexColor("#2563eb"), fontSize=8)
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
                    loc_text += f" ±{loc.accuracy_meters:.0f}m"
                loc_text += f" [source: {loc.source}]"
                if loc.address_text:
                    loc_text += f" — {loc.address_text}"
                story.append(Paragraph(loc_text, small_style))
            for a in insp.actions:
                story.append(Paragraph(
                    f"  {a.get('action', '')}: {a.get('field_name', '')} — {a.get('reason', '')}",
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
