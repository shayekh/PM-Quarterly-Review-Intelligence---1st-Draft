"""PDF generation (reportlab) — builds the 14-section Quarterly Service Delivery Report."""

import json
import os
import subprocess
import sys
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
COVER_BG_PATH = os.path.join(ASSETS_DIR, "cover_bg.jpg")
SELISE_LOGO_PATH = os.path.join(ASSETS_DIR, "selise_logo.png")
CUSTOMER_LOGO_PATH = os.path.join(ASSETS_DIR, "customer_logo.png")

NAVY = colors.HexColor("#1B3A5C")
BLUE = colors.HexColor("#2563eb")
LIGHT_BLUE = colors.HexColor("#dbeafe")
GREEN = colors.HexColor("#16a34a")
AMBER = colors.HexColor("#d97706")
RED = colors.HexColor("#dc2626")
LIGHT_GREY = colors.HexColor("#f3f4f6")
GREY_TEXT = colors.HexColor("#555555")

STATUS_COLORS = {"Green": GREEN, "Amber": AMBER, "Red": RED}
STATUS_EMOJI = {"Green": "🟢", "Amber": "🟡", "Red": "🔴"}
URGENCY_COLORS = {"High": RED, "Medium": AMBER, "Low": GREEN}

PAGE_W, PAGE_H = letter
MARGIN = 0.75 * inch

styles = getSampleStyleSheet()
styles.add(ParagraphStyle("SectionHeader", parent=styles["Heading2"], fontName="Helvetica-Bold",
                           fontSize=14, textColor=NAVY, spaceAfter=10, spaceBefore=16,
                           leftIndent=0, firstLineIndent=0))
styles.add(ParagraphStyle("SubHeader", parent=styles["Normal"], fontName="Helvetica-Oblique",
                           fontSize=10, textColor=GREY_TEXT, spaceAfter=12, leftIndent=0))
styles.add(ParagraphStyle("Body", parent=styles["Normal"], fontName="Helvetica",
                           fontSize=10, leading=14, leftIndent=0))
styles.add(ParagraphStyle("CellHeader", parent=styles["Normal"], fontName="Helvetica-Bold",
                           fontSize=9.5, textColor=colors.white, alignment=TA_CENTER))
styles.add(ParagraphStyle("LessonTitle", parent=styles["Normal"], fontName="Helvetica-Bold",
                           fontSize=11, textColor=NAVY, spaceAfter=4, leftIndent=0))
styles.add(ParagraphStyle("ActionText", parent=styles["Normal"], fontName="Helvetica-Bold",
                           fontSize=9.5, textColor=NAVY))
styles.add(ParagraphStyle("CardTitle", parent=styles["Normal"], fontName="Helvetica-Bold",
                           fontSize=10.5, textColor=NAVY))
styles.add(ParagraphStyle("CardMeta", parent=styles["Normal"], fontName="Helvetica-Bold",
                           fontSize=8.5))
styles.add(ParagraphStyle("Closing", parent=styles["Normal"], fontName="Helvetica-Oblique",
                           fontSize=10, leading=15, alignment=TA_JUSTIFY))
styles.add(ParagraphStyle("TableCell", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=12))
styles.add(ParagraphStyle("LegendHeader", parent=styles["Normal"], fontName="Helvetica-Bold",
                           fontSize=8, textColor=colors.white, alignment=TA_CENTER))
styles.add(ParagraphStyle("LegendCell", parent=styles["Normal"], fontName="Helvetica",
                           fontSize=8, leading=10))


def load_required(session):
    session_dir = os.path.join(DATA_DIR, session)
    paths = {
        "pm": os.path.join(session_dir, "pm_answers.json"),
        "tl": os.path.join(session_dir, "tl_answers.json"),
        "analysis": os.path.join(session_dir, "analysis.json"),
    }
    missing = [name for name, path in paths.items() if not os.path.exists(path)]
    if missing:
        print(f"Error: missing required file(s) for '{session}': {', '.join(missing)}")
        return None, None, None

    loaded = {}
    for name, path in paths.items():
        with open(path, "r", encoding="utf-8") as f:
            loaded[name] = json.load(f)
    return loaded["pm"], loaded["tl"], loaded["analysis"]


def draw_cover_background(canvas):
    """Draws assets/cover_bg.jpg edge-to-edge, cropping (not stretching) to cover the full page."""
    img = ImageReader(COVER_BG_PATH)
    img_w, img_h = img.getSize()
    scale = max(PAGE_W / img_w, PAGE_H / img_h)
    draw_w, draw_h = img_w * scale, img_h * scale
    x = (PAGE_W - draw_w) / 2
    y = (PAGE_H - draw_h) / 2
    canvas.drawImage(img, x, y, width=draw_w, height=draw_h, mask="auto")


def draw_cover_logo(canvas):
    """SELISE logo, top-right, 120x50pt, 20pt in from the top and right edges."""
    logo_w, logo_h = 120, 50
    x = PAGE_W - 20 - logo_w
    y = PAGE_H - 20 - logo_h
    canvas.drawImage(SELISE_LOGO_PATH, x, y, width=logo_w, height=logo_h,
                      mask="auto", preserveAspectRatio=True, anchor="n")


def fit_single_line_font_size(text, font, max_width, start_size=20, min_size=12, step=0.5):
    size = start_size
    while size > min_size and stringWidth(text, font, size) > max_width:
        size -= step
    return size


def draw_cover_banner_and_text(canvas, customer_name, reporting_period, date_str):
    banner_height = PAGE_H * 0.25
    banner_center_y = banner_height / 2
    padding = 24

    canvas.saveState()
    canvas.setFillColorRGB(30 / 255, 45 / 255, 60 / 255, alpha=0.85)
    canvas.rect(0, 0, PAGE_W, banner_height, fill=1, stroke=0)
    canvas.restoreState()

    logo_box_w, logo_box_h = 160, 70
    logo_box_x = PAGE_W - padding - logo_box_w
    logo_box_y = banner_center_y - logo_box_h / 2
    has_customer_logo = os.path.exists(CUSTOMER_LOGO_PATH)

    bar_x = padding
    text_x = bar_x + 4 + 12
    text_max_width = (logo_box_x - 16 - text_x) if has_customer_logo else (PAGE_W - padding - text_x)

    title_text = f"{customer_name} — Quarterly Service Delivery Report"
    title_font_size = fit_single_line_font_size(title_text, "Helvetica-Bold", text_max_width)
    title_leading = title_font_size * 1.2

    period_font_size = 13
    period_leading = period_font_size * 1.2

    date_font_size = 11
    date_leading = date_font_size * 1.2

    gap = 8
    block_height = title_leading + gap + period_leading + gap + date_leading
    block_top = banner_center_y + block_height / 2
    block_bottom = banner_center_y - block_height / 2

    canvas.saveState()
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", title_font_size)
    title_baseline = block_top - title_leading * 0.82
    canvas.drawString(text_x, title_baseline, title_text)

    canvas.setFont("Helvetica", period_font_size)
    period_baseline = title_baseline - title_leading * 0.4 - gap - period_leading * 0.6
    canvas.drawString(text_x, period_baseline, reporting_period)

    canvas.setFillColor(colors.HexColor("#d1d9e0"))
    canvas.setFont("Helvetica", date_font_size)
    date_baseline = period_baseline - period_leading * 0.4 - gap - date_leading * 0.6
    canvas.drawString(text_x, date_baseline, date_str)
    canvas.restoreState()

    canvas.saveState()
    canvas.setFillColor(colors.white)
    canvas.rect(bar_x, block_bottom, 4, block_height, fill=1, stroke=0)
    canvas.restoreState()

    if has_customer_logo:
        canvas.saveState()
        canvas.setFillColor(colors.white)
        canvas.roundRect(logo_box_x, logo_box_y, logo_box_w, logo_box_h, 8, fill=1, stroke=0)
        canvas.restoreState()

        logo_img = ImageReader(CUSTOMER_LOGO_PATH)
        img_w, img_h = logo_img.getSize()
        inner_pad = 12
        avail_w, avail_h = logo_box_w - 2 * inner_pad, logo_box_h - 2 * inner_pad
        scale = min(avail_w / img_w, avail_h / img_h)
        draw_w, draw_h = img_w * scale, img_h * scale
        img_x = logo_box_x + (logo_box_w - draw_w) / 2
        img_y = logo_box_y + (logo_box_h - draw_h) / 2
        canvas.drawImage(logo_img, img_x, img_y, width=draw_w, height=draw_h, mask="auto")


def make_cover_callback(customer_name, reporting_period, prepared_by, date_str):
    def draw(canvas, doc):
        draw_cover_background(canvas)
        draw_cover_logo(canvas)
        draw_cover_banner_and_text(canvas, customer_name, reporting_period, date_str)

    return draw


def make_footer_callback(customer_name, reporting_period):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(GREY_TEXT)
        canvas.drawString(MARGIN, 0.5 * inch, f"{customer_name} — {reporting_period}")
        canvas.drawCentredString(PAGE_W / 2, 0.5 * inch, f"Page {doc.page}")
        canvas.drawRightString(PAGE_W - MARGIN, 0.5 * inch, "Generated by Service Delivery Intelligence")
        canvas.restoreState()

    return draw


def full_width():
    return PAGE_W - 2 * MARGIN


def col_widths(fractions):
    """Converts column-width fractions (must sum to ~1.0) into point widths spanning full_width()."""
    width = full_width()
    return [width * f for f in fractions]


CELL_PADDING = 16  # combined left+right cell padding + small buffer, in points
BADGE_COL_WIDTH = 1.0 * inch


def label_col_width(header, values, min_fraction=0.0):
    """Computes a fixed width wide enough to fit the longest label on a single line,
    so a label/category column (e.g. Workstream, Area, Metric) never word-wraps."""
    candidates = [stringWidth(header, "Helvetica-Bold", 9.5)]
    candidates += [stringWidth(str(v), "Helvetica", 9) for v in values if v]
    width = max(candidates) + CELL_PADDING
    return max(width, min_fraction * full_width())


def widths_with_fixed_at(num_cols, fixed_by_index, var_ratio_by_index):
    """Builds a column-width list of length `num_cols`. Columns named in `fixed_by_index`
    (a dict of index -> point width) keep that exact width regardless of position. The
    remaining page width is split among the columns in `var_ratio_by_index` (index -> relative
    weight) proportionally to their weights."""
    widths = [0] * num_cols
    for i, w in fixed_by_index.items():
        widths[i] = w
    remaining = full_width() - sum(fixed_by_index.values())
    ratio_total = sum(var_ratio_by_index.values())
    for i, ratio in var_ratio_by_index.items():
        widths[i] = remaining * ratio / ratio_total
    return widths


def status_pill(status):
    color = STATUS_COLORS.get(status, colors.grey)
    t = Table([[Paragraph(f"{STATUS_EMOJI.get(status, '')} {status}", styles["CellHeader"])]], colWidths=[1.6 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    return t


def status_badge_cell(status):
    color = STATUS_COLORS.get(status, colors.grey)
    if status == "N/A":
        color = colors.grey
    t = Table([[Paragraph(f"{STATUS_EMOJI.get(status, '')} {status}".strip(), styles["CellHeader"])]],
              colWidths=[0.9 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    return t


def section_table(headers, rows, col_widths, badge_col=None):
    data = [[Paragraph(h, styles["CellHeader"]) for h in headers]]
    for row in rows:
        rendered = []
        for i, c in enumerate(row):
            if i == badge_col:
                rendered.append(status_badge_cell(c))
            else:
                rendered.append(Paragraph(str(c) if c else "—", styles["TableCell"]))
        data.append(rendered)
    table = Table(data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (badge_col, 1), (badge_col, -1), "CENTER") if badge_col is not None else ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GREY]),
    ]))
    return table


def build_s1_executive_summary(s1):
    flow = [Paragraph("S1 — Executive Summary", styles["SectionHeader"])]
    status = s1.get("overall_status", "Green")
    color_hex = STATUS_COLORS.get(status, colors.grey).hexval()[2:]

    p1 = s1.get("delivery_focus", "") or "During this quarter, the delivery team's focus is not yet recorded."
    p2 = (
        f"Overall service delivery status for the quarter is "
        f"<font color=\"#{color_hex}\"><b>{STATUS_EMOJI.get(status, '')} {status}</b></font>."
    )
    p3 = (
        f"The quarter was marked by {s1.get('highlights', '') or 'steady progress'}, while the main areas "
        f"requiring attention were {s1.get('areas_requiring_attention', '') or 'no significant concerns'}."
    )
    p4 = f"The focus for next quarter will be {s1.get('next_quarter_preview', '') or 'maintaining current delivery cadence'}."

    for p in (p1, p2, p3, p4):
        flow.append(Paragraph(p, styles["Body"]))
        flow.append(Spacer(1, 8))
    return flow


def build_s2_service_overview(s2):
    flow = [Paragraph("S2 — Service Overview", styles["SectionHeader"])]
    rows = [
        ["Active Services", s2.get("active_services", "")],
        ["Delivery Model", s2.get("delivery_model", "")],
        ["Key Stakeholders", s2.get("key_stakeholders", "")],
        ["Team Composition", s2.get("team_composition", "")],
        ["Reporting Cadence", s2.get("reporting_cadence", "")],
    ]
    area_width = label_col_width("Area", [r[0] for r in rows])
    flow.append(section_table(["Area", "Summary"], rows,
                               widths_with_fixed_at(2, {0: area_width}, {1: 1.0})))
    return flow


def build_s3_achievements(s3):
    flow = [Paragraph("S3 — Key Achievements", styles["SectionHeader"])]
    rows = [[f"{i}. {item.get('achievement', '')}", item.get("impact", "")] for i, item in enumerate(s3, 1)]
    flow.append(section_table(["Achievement", "Impact"], rows, col_widths([0.40, 0.60])))
    return flow


def build_delivery_status_legend():
    rows = [
        ["Green", "On track, no major concern"],
        ["Amber", "Some risk or delay, manageable"],
        ["Red", "Significant issue requiring attention"],
    ]
    data = [[Paragraph("Status", styles["LegendHeader"]), Paragraph("Meaning", styles["LegendHeader"])]]
    for status, meaning in rows:
        data.append([Paragraph(status, styles["LegendCell"]), Paragraph(meaning, styles["LegendCell"])])

    table_width = 3.2 * inch
    table = Table(data, colWidths=[0.9 * inch, table_width - 0.9 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#94a3b8")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GREY]),
    ]))

    # Centre the small table on the page by wrapping it in a full-width outer table.
    outer = Table([[table]], colWidths=[full_width()])
    outer.setStyle(TableStyle([
        ("ALIGN", (0, 0), (0, 0), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return [Paragraph("Delivery Status Legend", styles["SubHeader"]), outer]


def build_report_body(pm, tl, analysis):
    flow = []
    s = analysis["section_synthesis"]

    flow += build_s1_executive_summary(s["s1_executive_summary"])
    flow.append(PageBreak())

    flow += build_s2_service_overview(s["s2_service_overview"])
    flow.append(Spacer(1, 14))

    flow += build_s3_achievements(s["s3_achievements"])
    flow.append(Spacer(1, 8))

    flow.append(Paragraph("S4 — Delivery Summary", styles["SectionHeader"]))
    s4_rows = [[r["workstream"], r["status"], r["summary"], r["notes"]] for r in s["s4_delivery_summary"]]
    workstream_width = label_col_width("Workstream", [r[0] for r in s4_rows])
    flow.append(section_table(
        ["Workstream", "Status", "Progress Summary", "Notes"],
        s4_rows,
        widths_with_fixed_at(4, {0: workstream_width, 1: BADGE_COL_WIDTH}, {2: 0.65, 3: 0.35}),
        badge_col=1,
    ))
    flow.append(Spacer(1, 10))
    flow += build_delivery_status_legend()
    flow.append(PageBreak())

    flow.append(Paragraph("S5 — Service Performance Metrics", styles["SectionHeader"]))
    s5_rows = [[r["metric"], r["target"], r["actual"], r["status"], r["comment"]] for r in s["s5_metrics"]]
    metric_width = label_col_width("Metric", [r[0] for r in s5_rows])
    target_width = label_col_width("Target", [r[1] for r in s5_rows])
    actual_width = label_col_width("Actual", [r[2] for r in s5_rows])
    flow.append(section_table(
        ["Metric", "Target", "Actual", "Status", "Comment"],
        s5_rows,
        widths_with_fixed_at(5, {0: metric_width, 1: target_width, 2: actual_width, 3: BADGE_COL_WIDTH}, {4: 1.0}),
        badge_col=3,
    ))
    flow.append(PageBreak())

    flow.append(Paragraph("S6 — Support & Incident Summary", styles["SectionHeader"]))
    counts = s["s6_support_summary"]["ticket_counts"]

    def pct(num, den):
        n, d = parse_num(num), parse_num(den)
        return f"{round(n / d * 100, 1)}%" if n is not None and d else "N/A"

    def parse_num(raw):
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    ticket_rows = [
        ["Total Raised", counts.get("total", "0"), "Total support tickets logged this quarter."],
        ["Resolved", counts.get("resolved", "0"), f"{pct(counts.get('resolved'), counts.get('total'))} resolution rate this quarter."],
        ["Open", counts.get("open", "0"), "Tickets still awaiting resolution."],
        ["Critical Incidents", counts.get("critical", "0"), "Incidents classified as critical severity."],
        ["Major Incidents", counts.get("major", "0"), "Incidents classified as major severity (see below)."],
        ["Recurring Issues", counts.get("recurring", "0"), "Issues that reoccurred more than once this quarter."],
    ]
    category_width = label_col_width("Category", [r[0] for r in ticket_rows])
    count_width = label_col_width("Count", [r[1] for r in ticket_rows])
    flow.append(section_table(["Category", "Count", "Summary"], ticket_rows,
                               widths_with_fixed_at(3, {0: category_width, 1: count_width}, {2: 1.0})))
    flow.append(Spacer(1, 14))

    flow.append(Paragraph("Major Incidents / Escalations", styles["LessonTitle"]))
    incidents = s["s6_support_summary"]["major_incidents"]
    if incidents:
        flow.append(section_table(
            ["Date", "Issue", "Impact", "Root Cause", "Action Taken", "Current Status"],
            [[r["date"], r["issue"], r["impact"], r["root_cause"], r["action"], r["status"]] for r in incidents],
            col_widths([0.10, 0.18, 0.18, 0.18, 0.18, 0.18]),
        ))
    else:
        flow.append(Paragraph("No major incidents reported this quarter.", styles["Body"]))
    flow.append(PageBreak())

    flow.append(Paragraph("S7 — Quality & Delivery Health", styles["SectionHeader"]))
    s7_rows = [[r["area"], r["observation"], r["status"], r["improvement_action"]] for r in s["s7_quality_health"]]
    area_width = label_col_width("Area", [r[0] for r in s7_rows], min_fraction=0.15)
    flow.append(section_table(
        ["Area", "Observation", "Status", "Improvement Action"],
        s7_rows,
        widths_with_fixed_at(4, {0: area_width, 2: BADGE_COL_WIDTH}, {1: 0.55, 3: 0.45}),
        badge_col=2,
    ))
    flow.append(PageBreak())

    flow.append(Paragraph("S8 — Risks, Issues & Dependencies", styles["SectionHeader"]))
    s8_rows = [[r["type"], r["description"], r["impact"], r["owner"], r["mitigation"]] for r in s["s8_risks"]]
    type_width = label_col_width("Type", [r[0] for r in s8_rows])
    impact_width = label_col_width("Impact", [r[2] for r in s8_rows])
    owner_width = label_col_width("Owner", [r[3] for r in s8_rows])
    flow.append(section_table(
        ["Type", "Description", "Impact", "Owner", "Mitigation/Next Step"],
        s8_rows,
        widths_with_fixed_at(5, {0: type_width, 2: impact_width, 3: owner_width}, {1: 0.55, 4: 0.45}),
    ))
    flow.append(Spacer(1, 14))

    flow.append(Paragraph("S9 — Customer Feedback & Relationship Health", styles["SectionHeader"]))
    fb = s["s9_customer_feedback"]
    feedback_rows = [
        ["Customer Satisfaction", fb.get("satisfaction", "")],
        ["Communication", fb.get("communication", "")],
        ["Responsiveness", fb.get("responsiveness", "")],
        ["Business Alignment", fb.get("business_alignment", "")],
        ["Areas of Concern", fb.get("areas_of_concern", "")],
    ]
    fb_area_width = label_col_width("Area", [r[0] for r in feedback_rows])
    flow.append(section_table(["Area", "Feedback/Observation"], feedback_rows,
                               widths_with_fixed_at(2, {0: fb_area_width}, {1: 1.0})))
    flow.append(Spacer(1, 10))
    relationship_health = fb.get("relationship_health", "Green")
    health_color_hex = STATUS_COLORS.get(relationship_health, colors.grey).hexval()[2:]
    flow.append(Paragraph(
        f"Overall relationship health: "
        f"<font color=\"#{health_color_hex}\"><b>{STATUS_EMOJI.get(relationship_health, '')} {relationship_health}</b></font>.",
        styles["LessonTitle"],
    ))
    flow.append(PageBreak())

    return flow


def build_ai_sections(analysis):
    flow = [
        Paragraph("AI Generated Analysis", styles["SectionHeader"]),
        Paragraph("Synthesised by cross-analysing PM and Tech Lead submissions", styles["SubHeader"]),
    ]
    ai = analysis["ai_generated"]

    flow.append(Paragraph("S10 — Value Delivered", styles["SectionHeader"]))
    v = ai["s10_value_delivered"]
    for title, key in (("Business Value", "business_value"), ("Operational Value", "operational_value"),
                        ("Technical Value", "technical_value"), ("Strategic Value", "strategic_value")):
        flow.append(Paragraph(f"<b>{title}</b>", styles["LessonTitle"]))
        flow.append(Paragraph(v.get(key, "") or "Not provided.", styles["Body"]))
        flow.append(Spacer(1, 6))

    flow.append(Paragraph("S11 — Lessons Learned", styles["SectionHeader"]))
    for i, lesson in enumerate(ai["s11_lessons_learned"], 1):
        flow.append(Paragraph(f"{i}. {lesson.get('lesson', '')}", styles["LessonTitle"]))
        flow.append(Paragraph(lesson.get("context", ""), styles["Body"]))
        action_table = Table(
            [[Paragraph(f"Action: {lesson.get('action', '')}", styles["ActionText"])]],
            colWidths=[full_width()],
        )
        action_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BLUE),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("BOX", (0, 0), (-1, -1), 0.5, BLUE),
        ]))
        flow.append(Spacer(1, 4))
        flow.append(action_table)
        flow.append(Spacer(1, 14))

    flow.append(Paragraph("S12 — Next Quarter Focus", styles["SectionHeader"]))

    def render_owner(owner):
        return "Product Manager, Tech Lead" if owner == "Both" else owner

    flow.append(section_table(
        ["Focus Area", "Expected Outcome", "Owner"],
        [[r["focus_area"], r["expected_outcome"], render_owner(r["owner"])] for r in ai["s12_next_quarter_focus"]],
        col_widths([0.34, 0.46, 0.20]),
    ))
    flow.append(Spacer(1, 18))

    flow.append(Paragraph("S13 — Management Attention Required", styles["SectionHeader"]))
    for item in ai["s13_management_attention"]:
        urgency = item.get("urgency", "Low")
        border_color = URGENCY_COLORS.get(urgency, GREEN)
        card_content = [
            Paragraph(f"{urgency.upper()} URGENCY — {item.get('type', '')}", styles["CardMeta"]),
            Paragraph(item.get("item", ""), styles["CardTitle"]),
            Paragraph(item.get("explanation", ""), styles["Body"]),
            Paragraph(f"Source: {item.get('source', '')}", styles["SubHeader"]),
        ]
        card = Table([["", card_content]], colWidths=[0.12 * inch, full_width() - 0.12 * inch])
        card.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), border_color),
            ("BACKGROUND", (1, 0), (1, 0), LIGHT_GREY),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (1, 0), (1, 0), 8),
            ("BOTTOMPADDING", (1, 0), (1, 0), 8),
            ("LEFTPADDING", (1, 0), (1, 0), 10),
            ("RIGHTPADDING", (1, 0), (1, 0), 10),
            ("TOPPADDING", (0, 0), (0, 0), 0),
            ("BOTTOMPADDING", (0, 0), (0, 0), 0),
            ("LEFTPADDING", (0, 0), (0, 0), 0),
            ("RIGHTPADDING", (0, 0), (0, 0), 0),
        ]))
        flow.append(card)
        flow.append(Spacer(1, 10))

    flow.append(Spacer(1, 8))
    flow.append(Paragraph("S14 — Closing Note", styles["SectionHeader"]))
    closing_table = Table(
        [[Paragraph(ai.get("s14_closing_note", "").replace("\n\n", "<br/><br/>"), styles["Closing"])]],
        colWidths=[full_width()],
    )
    closing_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GREY),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
    ]))
    flow.append(closing_table)
    return flow


def format_cover_date(iso_date):
    try:
        dt = datetime.strptime(iso_date, "%Y-%m-%d")
    except (TypeError, ValueError):
        return iso_date or ""
    return f"{dt.day} {dt.strftime('%B')}, {dt.year}"


def build_pdf(pm, tl, analysis, out_path):
    meta = analysis["report_meta"]
    customer_name = meta["customer_name"]
    reporting_period = meta["reporting_period"]
    prepared_by = meta.get("prepared_by", "")
    date_str = format_cover_date(meta.get("date_generated", ""))

    content_frame = Frame(MARGIN, MARGIN, PAGE_W - 2 * MARGIN, PAGE_H - 2 * MARGIN, id="content")
    cover_frame = Frame(0, 0, PAGE_W, PAGE_H, id="cover")

    doc = BaseDocTemplate(
        out_path,
        pagesize=letter,
        pageTemplates=[
            PageTemplate(id="Cover", frames=[cover_frame],
                         onPage=make_cover_callback(customer_name, reporting_period, prepared_by, date_str)),
            PageTemplate(id="Content", frames=[content_frame],
                         onPage=make_footer_callback(customer_name, reporting_period)),
        ],
    )

    story = [Spacer(1, 1), NextPageTemplate("Content"), PageBreak()]
    story += build_report_body(pm, tl, analysis)
    story += build_ai_sections(analysis)

    doc.build(story)


def run_pdf(session, auto_chain=True):
    """Generates the PDF report for `session`. Returns True on success, False on failure."""
    print(f"📄 Generating PDF report for {session}...")

    pm, tl, analysis = load_required(session)
    if pm is None:
        return False

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    customer_name = analysis["report_meta"]["customer_name"]
    reporting_period = analysis["report_meta"]["reporting_period"]
    out_path = os.path.join(OUTPUT_DIR, f"{session}.pdf")

    build_pdf(pm, tl, analysis, out_path)

    rel_path = os.path.relpath(out_path, BASE_DIR).replace("\\", "/")
    print(f"✅ PDF saved to {rel_path}")

    if auto_chain:
        print("🚀 Triggering email scheduler...")
        scheduler_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scheduler.py")
        subprocess.run([sys.executable, scheduler_script, session])

    return True


def main():
    if len(sys.argv) < 2:
        print("Error: session name is required, e.g. `python generate_pdf.py CustomerName_Q2_2026`")
        sys.exit(1)

    success = run_pdf(sys.argv[1])
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
