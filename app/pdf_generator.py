"""Flashpoint — PDF report generator using ReportLab Platypus.

Generates a professional incident report PDF entirely in-memory,
returning raw bytes so FastAPI can stream the response directly.
Fields are filled BY NAME via IncidentReport.model_dump().
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.schemas import IncidentReport

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

NAVY = colors.HexColor("#1a2744")
LIGHT_NAVY = colors.HexColor("#2a3d5c")
ACCENT = colors.HexColor("#3b82f6")       # bright blue accent
WHITE = colors.white
LIGHT_BG = colors.HexColor("#f1f5f9")     # section background
BORDER = colors.HexColor("#cbd5e1")       # subtle border colour
TEXT_DARK = colors.HexColor("#0f172a")
TEXT_MUTED = colors.HexColor("#64748b")

# ---------------------------------------------------------------------------
# Paragraph styles
# ---------------------------------------------------------------------------

_base = getSampleStyleSheet()

STYLE_HEADER_TITLE = ParagraphStyle(
    "HeaderTitle",
    parent=_base["Normal"],
    fontName="Helvetica-Bold",
    fontSize=20,
    textColor=WHITE,
    alignment=TA_CENTER,
    spaceAfter=2,
)

STYLE_HEADER_SUB = ParagraphStyle(
    "HeaderSub",
    parent=_base["Normal"],
    fontName="Helvetica",
    fontSize=9,
    textColor=colors.HexColor("#94a3b8"),
    alignment=TA_CENTER,
    spaceAfter=0,
)

STYLE_SECTION = ParagraphStyle(
    "SectionHeading",
    parent=_base["Normal"],
    fontName="Helvetica-Bold",
    fontSize=12,
    textColor=NAVY,
    spaceBefore=14,
    spaceAfter=6,
    borderPadding=(0, 0, 2, 0),
)

STYLE_LABEL = ParagraphStyle(
    "FieldLabel",
    parent=_base["Normal"],
    fontName="Helvetica-Bold",
    fontSize=9,
    textColor=TEXT_MUTED,
)

STYLE_VALUE = ParagraphStyle(
    "FieldValue",
    parent=_base["Normal"],
    fontName="Helvetica",
    fontSize=10,
    textColor=TEXT_DARK,
    leading=14,
)

STYLE_BULLET = ParagraphStyle(
    "BulletItem",
    parent=_base["Normal"],
    fontName="Helvetica",
    fontSize=10,
    textColor=TEXT_DARK,
    leading=14,
    leftIndent=12,
)

STYLE_SUMMARY = ParagraphStyle(
    "SummaryBody",
    parent=_base["Normal"],
    fontName="Helvetica",
    fontSize=10,
    textColor=TEXT_DARK,
    leading=15,
    spaceBefore=4,
)

STYLE_FOOTER = ParagraphStyle(
    "Footer",
    parent=_base["Normal"],
    fontName="Helvetica-Oblique",
    fontSize=8,
    textColor=TEXT_MUTED,
    alignment=TA_CENTER,
)


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------


def _build_header(report_id: str, timestamp: str) -> list:
    """Dark navy header bar with title, timestamp, and report ID."""

    title = Paragraph("INCIDENT REPORT", STYLE_HEADER_TITLE)
    subtitle = Paragraph(
        f"Report ID: {report_id} &nbsp;|&nbsp; Generated: {timestamp}",
        STYLE_HEADER_SUB,
    )

    # Single-cell table acts as a coloured banner
    header_table = Table(
        [[title], [subtitle]],
        colWidths=[7.5 * inch],
    )
    header_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (0, 0), 18),
                ("BOTTOMPADDING", (0, -1), (0, -1), 14),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("ROUNDEDCORNERS", [6, 6, 0, 0]),
            ]
        )
    )
    return [header_table]


def _section_heading(text: str) -> Paragraph:
    """Return a styled section heading with a subtle left-border effect."""
    return Paragraph(f"▎ {text}", STYLE_SECTION)


def _field_row(label: str, value: str) -> Table:
    """Two-column label→value row rendered as a mini table."""
    lbl = Paragraph(label, STYLE_LABEL)
    val = Paragraph(value, STYLE_VALUE)
    tbl = Table([[lbl, val]], colWidths=[1.8 * inch, 5.7 * inch])
    tbl.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, BORDER),
            ]
        )
    )
    return tbl


def _bulleted_list(items: list[str]) -> ListFlowable:
    """Render a list of strings as a bulleted ListFlowable."""
    return ListFlowable(
        [ListItem(Paragraph(item, STYLE_BULLET)) for item in items],
        bulletType="bullet",
        bulletFontSize=7,
        bulletColor=ACCENT,
        leftIndent=18,
        spaceBefore=2,
        spaceAfter=2,
    )


def _summary_box(text: str) -> Table:
    """Full-width summary text inside a light-background card."""
    para = Paragraph(text, STYLE_SUMMARY)
    tbl = Table([[para]], colWidths=[7.5 * inch])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("ROUNDEDCORNERS", [4, 4, 4, 4]),
            ]
        )
    )
    return tbl


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_pdf(report: IncidentReport) -> bytes:
    """Render *report* as a professional PDF and return raw bytes.

    Fields are accessed by NAME through ``report.model_dump()``,
    so the layout always maps to the correct schema field regardless
    of declaration order.
    """
    buffer = BytesIO()
    report_id = uuid.uuid4().hex[:8].upper()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=0.4 * inch,
        bottomMargin=0.6 * inch,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        title="Flashpoint Incident Report",
        author="Flashpoint",
    )

    # --- Collect the data by NAME ---
    data = report.model_dump()

    story: list = []

    # ── Header ──────────────────────────────────────────────────────────
    story.extend(_build_header(report_id, timestamp))
    story.append(Spacer(1, 14))

    # ── Section 1: Incident Details ─────────────────────────────────────
    story.append(_section_heading("Incident Details"))
    story.append(_field_row("Location", data["location"]))
    story.append(_field_row("Date / Time", data["datetime"]))
    story.append(_field_row("Incident Type", data["incident_type"]))
    story.append(Spacer(1, 6))

    # ── Section 2: Response ─────────────────────────────────────────────
    story.append(_section_heading("Response"))
    units = data["units_involved"]
    if units:
        story.append(_bulleted_list(units))
    else:
        story.append(Paragraph("No units reported.", STYLE_VALUE))
    story.append(Spacer(1, 6))

    # ── Section 3: Casualties & Hazards ─────────────────────────────────
    story.append(_section_heading("Casualties &amp; Hazards"))
    story.append(
        _field_row("Injuries Reported", str(data["injuries"]))
    )
    story.append(Spacer(1, 4))
    hazards = data["hazards"]
    if hazards:
        story.append(Paragraph("Identified Hazards:", STYLE_LABEL))
        story.append(Spacer(1, 2))
        story.append(_bulleted_list(hazards))
    else:
        story.append(
            Paragraph("No hazards identified.", STYLE_VALUE)
        )
    story.append(Spacer(1, 6))

    # ── Section 4: Summary ──────────────────────────────────────────────
    story.append(_section_heading("Summary"))
    story.append(_summary_box(data["summary"]))
    story.append(Spacer(1, 20))

    # ── Footer ──────────────────────────────────────────────────────────
    story.append(
        Paragraph(
            "Generated by Flashpoint &nbsp;|&nbsp; Powered by Mistral (local)",
            STYLE_FOOTER,
        )
    )

    # --- Build PDF ---
    doc.build(story)
    return buffer.getvalue()
