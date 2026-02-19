"""PDF generation for clinical documentation export."""

import io
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from models import Session


# ── Shared styles ──

CLINICAL_BLUE = colors.HexColor("#1e40af")
CLINICAL_LIGHT = colors.HexColor("#dbeafe")
SLATE_700 = colors.HexColor("#334155")
SLATE_400 = colors.HexColor("#94a3b8")
SLATE_200 = colors.HexColor("#e2e8f0")


def _base_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=CLINICAL_BLUE,
        spaceAfter=6,
        spaceBefore=14,
        fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        "BodyText14",
        parent=styles["BodyText"],
        fontSize=14,
        leading=20,
        textColor=SLATE_700,
    ))
    styles.add(ParagraphStyle(
        "CodeItem",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        textColor=SLATE_700,
        leftIndent=12,
        bulletFontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        "Footer",
        parent=styles["Normal"],
        fontSize=8,
        textColor=SLATE_400,
        alignment=1,  # center
    ))
    return styles


def _header_table(title: str, session: Session):
    """Build a header block with title, date, visit type."""
    date_str = session.created_at.strftime("%B %d, %Y at %I:%M %p")
    visit_label = session.visit_type.value.replace("_", " ").title()

    data = [
        [title, ""],
        [f"Date: {date_str}", f"Visit Type: {visit_label}"],
    ]
    t = Table(data, colWidths=[4 * inch, 3 * inch])
    t.setStyle(TableStyle([
        ("SPAN", (0, 0), (1, 0)),
        ("FONTNAME", (0, 0), (1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (1, 0), 16),
        ("TEXTCOLOR", (0, 0), (1, 0), CLINICAL_BLUE),
        ("FONTNAME", (0, 1), (1, 1), "Helvetica"),
        ("FONTSIZE", (0, 1), (1, 1), 9),
        ("TEXTCOLOR", (0, 1), (1, 1), SLATE_400),
        ("BOTTOMPADDING", (0, 0), (1, 0), 6),
        ("TOPPADDING", (0, 1), (1, 1), 2),
        ("LINEBELOW", (0, 1), (1, 1), 1, CLINICAL_BLUE),
    ]))
    return t


def _footer_text(text: str, styles):
    return Paragraph(text, styles["Footer"])


def _soap_section(label: str, content: str, styles):
    """Render one SOAP section with header + body paragraphs."""
    elements = []
    elements.append(Paragraph(label, styles["SectionHeader"]))
    if content.strip():
        for line in content.strip().split("\n"):
            line = line.strip()
            if line:
                elements.append(Paragraph(line, styles["BodyText"]))
                elements.append(Spacer(1, 4))
    else:
        elements.append(Paragraph("<i>No content recorded.</i>", styles["BodyText"]))
    return elements


# ── Public API ──


def generate_soap_pdf(session: Session) -> bytes:
    """Generate a professional SOAP note PDF."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        topMargin=0.6 * inch,
        bottomMargin=0.8 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
    )
    styles = _base_styles()
    story = []

    # Header
    story.append(_header_table("Clinical Documentation \u2014 SOAP Note", session))
    story.append(Spacer(1, 16))

    # Patient context
    if session.patient_context:
        ctx = session.patient_context
        parts = []
        if ctx.name:
            parts.append(ctx.name)
        if ctx.age:
            parts.append(f"Age {ctx.age}")
        if ctx.chief_complaint:
            parts.append(f"CC: {ctx.chief_complaint}")
        if parts:
            story.append(Paragraph(f"<b>Patient Context:</b> {', '.join(parts)}", styles["BodyText"]))
            story.append(Spacer(1, 8))

    # SOAP sections
    soap = session.soap_note
    for label, content in [
        ("Subjective", soap.subjective),
        ("Objective", soap.objective),
        ("Assessment", soap.assessment),
        ("Plan", soap.plan),
    ]:
        story.extend(_soap_section(label, content, styles))

    # ICD-10 codes (from assessment)
    icd_codes = [c for c in session.diagnosis_codes if c.source_section == "assessment"]
    if icd_codes:
        story.append(Spacer(1, 6))
        story.append(HRFlowable(width="100%", thickness=0.5, color=SLATE_200))
        story.append(Paragraph("ICD-10 Codes", styles["SectionHeader"]))
        for code in icd_codes:
            confirmed = " (Confirmed)" if code.confirmed else ""
            story.append(Paragraph(
                f"\u2022 <b>{code.code}</b> \u2014 {code.description}{confirmed}",
                styles["CodeItem"],
            ))

    # CPT codes (from plan)
    cpt_codes = [c for c in session.diagnosis_codes if c.source_section == "plan"]
    if cpt_codes:
        story.append(Spacer(1, 6))
        story.append(HRFlowable(width="100%", thickness=0.5, color=SLATE_200))
        story.append(Paragraph("CPT Codes", styles["SectionHeader"]))
        for code in cpt_codes:
            story.append(Paragraph(
                f"\u2022 <b>{code.code}</b> \u2014 {code.description}",
                styles["CodeItem"],
            ))

    # Medications
    if session.medications:
        story.append(Spacer(1, 6))
        story.append(HRFlowable(width="100%", thickness=0.5, color=SLATE_200))
        story.append(Paragraph("Medications", styles["SectionHeader"]))
        for med in session.medications:
            parts = [f"<b>{med.name}</b>"]
            if med.dose:
                parts.append(med.dose)
            if med.frequency:
                parts.append(f"({med.frequency})")
            story.append(Paragraph(f"\u2022 {' '.join(parts)}", styles["CodeItem"]))

    # Interaction flags
    if session.interaction_flags:
        story.append(Spacer(1, 6))
        story.append(Paragraph("Drug Interactions", styles["SectionHeader"]))
        for flag in session.interaction_flags:
            sev = flag.severity.value.upper()
            story.append(Paragraph(
                f"\u2022 <b>[{sev}]</b> {flag.drug_a} + {flag.drug_b}"
                + (f" \u2014 {flag.mechanism}" if flag.mechanism else ""),
                styles["CodeItem"],
            ))

    # Footer
    story.append(Spacer(1, 24))
    story.append(HRFlowable(width="100%", thickness=0.5, color=SLATE_200))
    story.append(Spacer(1, 8))
    story.append(_footer_text(
        "Generated by Scribe AI \u2014 Not a substitute for clinical judgment",
        styles,
    ))
    gen_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    story.append(_footer_text(f"Generated on {gen_time}", styles))

    doc.build(story)
    return buf.getvalue()


def generate_patient_summary_pdf(session: Session) -> bytes:
    """Generate a patient-friendly summary PDF with large readable text."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        topMargin=0.6 * inch,
        bottomMargin=0.8 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
    )
    styles = _base_styles()
    story = []

    # Header
    story.append(_header_table("Your Visit Summary", session))
    story.append(Spacer(1, 20))

    summary = session.patient_summary
    body = styles["BodyText14"]

    # What We Discussed
    story.append(Paragraph("What We Discussed", styles["SectionHeader"]))
    if summary and summary.visit_summary:
        for line in summary.visit_summary.strip().split("\n"):
            if line.strip():
                story.append(Paragraph(line.strip(), body))
                story.append(Spacer(1, 4))
    else:
        story.append(Paragraph("<i>No summary available.</i>", body))
    story.append(Spacer(1, 8))

    # Your Medications
    story.append(Paragraph("Your Medications", styles["SectionHeader"]))
    if summary and summary.new_medications:
        for med in summary.new_medications:
            story.append(Paragraph(f"\u2022 {med}", body))
            story.append(Spacer(1, 4))
    elif session.medications:
        for med in session.medications:
            parts = [med.name]
            if med.dose:
                parts.append(f"- {med.dose}")
            if med.frequency:
                parts.append(f"({med.frequency})")
            story.append(Paragraph(f"\u2022 {' '.join(parts)}", body))
            story.append(Spacer(1, 4))
    else:
        story.append(Paragraph("No medications discussed during this visit.", body))
    story.append(Spacer(1, 8))

    # Next Steps
    story.append(Paragraph("Next Steps", styles["SectionHeader"]))
    has_steps = False
    if summary and summary.follow_up_steps:
        for step in summary.follow_up_steps:
            story.append(Paragraph(f"\u2022 {step}", body))
            story.append(Spacer(1, 4))
        has_steps = True
    if session.follow_ups:
        for fu in session.follow_ups:
            text = fu.action
            if fu.timeframe:
                text += f" ({fu.timeframe})"
            story.append(Paragraph(f"\u2022 {text}", body))
            story.append(Spacer(1, 4))
        has_steps = True
    if not has_steps:
        story.append(Paragraph("No specific follow-up steps at this time.", body))
    story.append(Spacer(1, 8))

    # When to Seek Care
    story.append(Paragraph("When to Seek Care", styles["SectionHeader"]))
    if summary and summary.when_to_seek_care:
        story.append(Paragraph(summary.when_to_seek_care, body))
    else:
        story.append(Paragraph(
            "If your symptoms worsen or you develop new concerns, "
            "please contact your healthcare provider or visit the nearest emergency department.",
            body,
        ))

    # Footer
    story.append(Spacer(1, 30))
    story.append(HRFlowable(width="100%", thickness=0.5, color=SLATE_200))
    story.append(Spacer(1, 8))
    story.append(_footer_text("Provider: [Your Healthcare Provider]", styles))
    story.append(_footer_text("Contact: [Office Phone Number]", styles))
    story.append(Spacer(1, 4))
    story.append(_footer_text(
        "This summary is for your reference. "
        "Always follow up with your provider if you have questions.",
        styles,
    ))

    doc.build(story)
    return buf.getvalue()


def generate_soap_text(session: Session) -> str:
    """Generate a plain-text SOAP note for clipboard copy."""
    lines = []
    date_str = session.created_at.strftime("%B %d, %Y at %I:%M %p")
    visit_label = session.visit_type.value.replace("_", " ").title()

    lines.append("CLINICAL DOCUMENTATION - SOAP NOTE")
    lines.append(f"Date: {date_str}  |  Visit Type: {visit_label}")
    lines.append("=" * 50)

    soap = session.soap_note
    for label, content in [
        ("SUBJECTIVE", soap.subjective),
        ("OBJECTIVE", soap.objective),
        ("ASSESSMENT", soap.assessment),
        ("PLAN", soap.plan),
    ]:
        lines.append("")
        lines.append(label)
        lines.append("-" * len(label))
        lines.append(content.strip() if content.strip() else "(No content recorded)")

    # ICD-10
    icd_codes = [c for c in session.diagnosis_codes if c.source_section == "assessment"]
    if icd_codes:
        lines.append("")
        lines.append("ICD-10 CODES")
        lines.append("-" * 12)
        for c in icd_codes:
            confirmed = " (Confirmed)" if c.confirmed else ""
            lines.append(f"  {c.code} - {c.description}{confirmed}")

    # CPT
    cpt_codes = [c for c in session.diagnosis_codes if c.source_section == "plan"]
    if cpt_codes:
        lines.append("")
        lines.append("CPT CODES")
        lines.append("-" * 9)
        for c in cpt_codes:
            lines.append(f"  {c.code} - {c.description}")

    # Medications
    if session.medications:
        lines.append("")
        lines.append("MEDICATIONS")
        lines.append("-" * 11)
        for med in session.medications:
            parts = [med.name]
            if med.dose:
                parts.append(med.dose)
            if med.frequency:
                parts.append(f"({med.frequency})")
            lines.append(f"  {' '.join(parts)}")

    lines.append("")
    lines.append("=" * 50)
    lines.append("Generated by Scribe AI - Not a substitute for clinical judgment")

    return "\n".join(lines)
