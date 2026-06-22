"""PDF generation (reportlab) — combines PM answers, TL answers, and AI analysis into one report."""

import json
import os
import subprocess
import sys
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
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

NAVY = colors.HexColor("#1e3a5f")
BLUE = colors.HexColor("#2563eb")
LIGHT_BLUE = colors.HexColor("#dbeafe")
GREEN = colors.HexColor("#16a34a")
AMBER = colors.HexColor("#d97706")
RED = colors.HexColor("#dc2626")
LIGHT_GREY = colors.HexColor("#f3f4f6")
GREY_TEXT = colors.HexColor("#555555")

STATUS_COLORS = {"Green": GREEN, "Amber": AMBER, "Red": RED}
URGENCY_COLORS = {"High": RED, "Medium": AMBER, "Low": GREEN}

QUESTIONS = [
    ("executive_summary", "Executive Summary"),
    ("overall_status", "Overall Status"),
    ("key_achievements", "Key Achievements & Value Delivered"),
    ("risks_and_challenges", "Risks, Issues & Challenges"),
    ("quality_and_team_health", "Quality & Team Health"),
]

PAGE_W, PAGE_H = letter
MARGIN = 0.75 * inch

styles = getSampleStyleSheet()
styles.add(ParagraphStyle("SectionHeader", parent=styles["Heading2"], fontName="Helvetica-Bold",
                           fontSize=14, textColor=NAVY, spaceAfter=10, spaceBefore=16))
styles.add(ParagraphStyle("SubHeader", parent=styles["Normal"], fontName="Helvetica-Oblique",
                           fontSize=10, textColor=GREY_TEXT, spaceAfter=12))
styles.add(ParagraphStyle("Body", parent=styles["Normal"], fontName="Helvetica",
                           fontSize=10, leading=14))
styles.add(ParagraphStyle("CellHeader", parent=styles["Normal"], fontName="Helvetica-Bold",
                           fontSize=10, textColor=colors.white, alignment=TA_CENTER))
styles.add(ParagraphStyle("QHeader", parent=styles["Normal"], fontName="Helvetica-Bold",
                           fontSize=11, textColor=colors.white))
styles.add(ParagraphStyle("LessonTitle", parent=styles["Normal"], fontName="Helvetica-Bold",
                           fontSize=11, textColor=NAVY, spaceAfter=4))
styles.add(ParagraphStyle("ActionText", parent=styles["Normal"], fontName="Helvetica-Bold",
                           fontSize=9.5, textColor=NAVY))
styles.add(ParagraphStyle("CardTitle", parent=styles["Normal"], fontName="Helvetica-Bold",
                           fontSize=10.5, textColor=NAVY))
styles.add(ParagraphStyle("CardMeta", parent=styles["Normal"], fontName="Helvetica-Bold",
                           fontSize=8.5))
styles.add(ParagraphStyle("Closing", parent=styles["Normal"], fontName="Helvetica-Oblique",
                           fontSize=10, leading=15, alignment=TA_JUSTIFY))
styles.add(ParagraphStyle("TableCell", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=12))


def header(title):
    print(title)


def load_required(project):
    project_dir = os.path.join(DATA_DIR, project)
    paths = {
        "pm": os.path.join(project_dir, "pm_answers.json"),
        "tl": os.path.join(project_dir, "tl_answers.json"),
        "analysis": os.path.join(project_dir, "analysis.json"),
    }
    missing = [name for name, path in paths.items() if not os.path.exists(path)]
    if missing:
        print(f"Error: missing required file(s) for '{project}': {', '.join(missing)}")
        sys.exit(1)

    loaded = {}
    for name, path in paths.items():
        with open(path, "r", encoding="utf-8") as f:
            loaded[name] = json.load(f)
    return loaded["pm"], loaded["tl"], loaded["analysis"]


def make_cover_callback(project, quarter, year, date_str):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 26)
        canvas.drawCentredString(PAGE_W / 2, PAGE_H * 0.64, "PM Quarterly Review")
        canvas.drawCentredString(PAGE_W / 2, PAGE_H * 0.64 - 32, "Intelligence Report")

        canvas.setFont("Helvetica", 13)
        lines = [
            f"Project: {project}",
            f"Quarter: {quarter} {year}",
            f"Date: {date_str}",
            "",
            "Prepared by: PM + Tech Lead",
            "Analyzed by: AI Agent",
        ]
        y = PAGE_H * 0.64 - 90
        for line in lines:
            if line:
                canvas.drawCentredString(PAGE_W / 2, y, line)
            y -= 22
        canvas.restoreState()

    return draw


def make_footer_callback(project, quarter, year):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(GREY_TEXT)
        canvas.drawString(MARGIN, 0.5 * inch, f"{project} — {quarter} {year}")
        canvas.drawCentredString(PAGE_W / 2, 0.5 * inch, f"Page {doc.page}")
        canvas.drawRightString(PAGE_W - MARGIN, 0.5 * inch, "Generated by PM Review Intelligence")
        canvas.restoreState()

    return draw


def status_badge_table(label, status):
    color = STATUS_COLORS.get(status, colors.grey)
    inner = Table([[Paragraph(f"{label}: {status.upper()}", styles["CellHeader"])]], colWidths=[2.6 * inch])
    inner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BOX", (0, 0), (-1, -1), 0.5, color),
    ]))
    return inner


def build_qa_section(pm, tl):
    flow = [Paragraph("Submissions Overview", styles["SectionHeader"])]
    for key, label in QUESTIONS:
        flow.append(Spacer(1, 6))
        q_header = Table([[Paragraph(f"{label}", styles["QHeader"])]], colWidths=[PAGE_W - 2 * MARGIN])
        q_header.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), NAVY),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        flow.append(q_header)

        if key == "overall_status":
            badges = Table(
                [[status_badge_table("Product Manager", pm["answers"][key]),
                  status_badge_table("Tech Lead", tl["answers"][key])]],
                colWidths=[(PAGE_W - 2 * MARGIN) / 2] * 2,
            )
            badges.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ]))
            flow.append(badges)
        else:
            pm_text = pm["answers"].get(key, "") or "(no answer provided)"
            tl_text = tl["answers"].get(key, "") or "(no answer provided)"
            qa_table = Table(
                [
                    [Paragraph("Product Manager", styles["CellHeader"]), Paragraph("Tech Lead", styles["CellHeader"])],
                    [Paragraph(pm_text, styles["TableCell"]), Paragraph(tl_text, styles["TableCell"])],
                ],
                colWidths=[(PAGE_W - 2 * MARGIN) / 2] * 2,
            )
            qa_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), BLUE),
                ("BACKGROUND", (0, 1), (-1, 1), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]))
            flow.append(qa_table)
        flow.append(Spacer(1, 14))
    return flow


def build_analysis_section(analysis):
    flow = [
        Paragraph("AI Agent Analysis", styles["SectionHeader"]),
        Paragraph("Generated by analyzing both PM and Tech Lead perspectives", styles["SubHeader"]),
    ]

    flow.append(Paragraph("Lessons Learned", styles["SectionHeader"]))
    for lesson in analysis.get("lessons_learned", []):
        flow.append(Paragraph(lesson.get("lesson", ""), styles["LessonTitle"]))
        flow.append(Paragraph(lesson.get("context", ""), styles["Body"]))
        action_table = Table(
            [[Paragraph(f"Action: {lesson.get('action', '')}", styles["ActionText"])]],
            colWidths=[PAGE_W - 2 * MARGIN],
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

    flow.append(Paragraph("Next Quarter Focus", styles["SectionHeader"]))
    focus_rows = [[Paragraph("Focus Area", styles["CellHeader"]),
                   Paragraph("Expected Outcome", styles["CellHeader"]),
                   Paragraph("Owner", styles["CellHeader"])]]
    for item in analysis.get("next_quarter_focus", []):
        focus_rows.append([
            Paragraph(item.get("focus_area", ""), styles["TableCell"]),
            Paragraph(item.get("expected_outcome", ""), styles["TableCell"]),
            Paragraph(item.get("owner", ""), styles["TableCell"]),
        ])
    focus_table = Table(focus_rows, colWidths=[2.2 * inch, 2.8 * inch, 1.0 * inch])
    focus_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GREY]),
    ]))
    flow.append(focus_table)
    flow.append(Spacer(1, 18))

    flow.append(Paragraph("Management Attention Required", styles["SectionHeader"]))
    for item in analysis.get("management_attention", []):
        urgency = item.get("urgency", "Low")
        border_color = URGENCY_COLORS.get(urgency, GREEN)
        card_content = [
            Paragraph(f"{urgency.upper()} URGENCY — {item.get('type', '')}", styles["CardMeta"]),
            Paragraph(item.get("item", ""), styles["CardTitle"]),
            Paragraph(item.get("explanation", ""), styles["Body"]),
            Paragraph(f"Source: {item.get('source', '')}", styles["SubHeader"]),
        ]
        card = Table(
            [["", card_content]],
            colWidths=[0.12 * inch, PAGE_W - 2 * MARGIN - 0.12 * inch],
        )
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
    flow.append(Paragraph("Closing Note", styles["SectionHeader"]))
    closing_table = Table(
        [[Paragraph(analysis.get("closing_note", "").replace("\n\n", "<br/><br/>"), styles["Closing"])]],
        colWidths=[PAGE_W - 2 * MARGIN],
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


def build_pdf(project, pm, tl, analysis, out_path):
    quarter = analysis.get("quarter", "Q?")
    year = analysis.get("year", "????")
    date_str = datetime.now().strftime("%B %d, %Y")

    content_frame = Frame(MARGIN, MARGIN, PAGE_W - 2 * MARGIN, PAGE_H - 2 * MARGIN, id="content")
    cover_frame = Frame(0, 0, PAGE_W, PAGE_H, id="cover")

    doc = BaseDocTemplate(
        out_path,
        pagesize=letter,
        pageTemplates=[
            PageTemplate(id="Cover", frames=[cover_frame],
                         onPage=make_cover_callback(project, quarter, year, date_str)),
            PageTemplate(id="Content", frames=[content_frame],
                         onPage=make_footer_callback(project, quarter, year)),
        ],
    )

    story = [Spacer(1, 1), NextPageTemplate("Content"), PageBreak()]
    story += build_qa_section(pm, tl)
    story.append(PageBreak())
    story += build_analysis_section(analysis)

    doc.build(story)


def main():
    if len(sys.argv) < 2:
        print("Error: project name is required, e.g. `python generate_pdf.py ProjectName`")
        sys.exit(1)

    project = sys.argv[1]
    print(f"📄 Generating PDF report for {project}...")

    pm, tl, analysis = load_required(project)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    quarter = analysis.get("quarter", "Q?")
    year = analysis.get("year", "????")
    out_path = os.path.join(OUTPUT_DIR, f"{project}_{quarter}_{year}.pdf")

    build_pdf(project, pm, tl, analysis, out_path)

    rel_path = os.path.relpath(out_path, BASE_DIR).replace("\\", "/")
    print(f"✅ PDF saved to {rel_path}")
    print("🚀 Triggering email scheduler...")

    scheduler_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scheduler.py")
    subprocess.run([sys.executable, scheduler_script, project])


if __name__ == "__main__":
    main()
