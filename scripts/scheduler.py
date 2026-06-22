"""Email sending via Resend — TEST_MODE sends immediately, PROD sends quarterly."""

import json
import os
import sys
from datetime import datetime

import resend
from dotenv import load_dotenv

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

QUARTER_END_MONTHS = [3, 6, 9, 12]
MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
STATUS_EMOJI = {"Green": "🟢", "Amber": "🟡", "Red": "🔴"}


def next_quarter_end(after_date):
    month, year = after_date.month, after_date.year
    for m in QUARTER_END_MONTHS:
        if m > month:
            return m, year
    return QUARTER_END_MONTHS[0], year + 1


def load_required(project):
    project_dir = os.path.join(DATA_DIR, project)
    pm_path = os.path.join(project_dir, "pm_answers.json")

    if not os.path.exists(pm_path):
        print(f"Error: missing data/{project}/pm_answers.json")
        sys.exit(1)
    with open(pm_path, "r", encoding="utf-8") as f:
        pm = json.load(f)

    quarter = pm.get("quarter", "Q?")
    year = pm.get("year", "????")
    pdf_path = os.path.join(OUTPUT_DIR, f"{project}_{quarter}_{year}.pdf")
    if not os.path.exists(pdf_path):
        print(f"Error: missing {os.path.relpath(pdf_path, BASE_DIR)}")
        sys.exit(1)

    tl = None
    tl_path = os.path.join(project_dir, "tl_answers.json")
    if os.path.exists(tl_path):
        with open(tl_path, "r", encoding="utf-8") as f:
            tl = json.load(f)

    analysis = None
    analysis_path = os.path.join(project_dir, "analysis.json")
    if os.path.exists(analysis_path):
        with open(analysis_path, "r", encoding="utf-8") as f:
            analysis = json.load(f)

    return pm, tl, analysis, pdf_path


def build_email_html(project, quarter, year, pm, tl, analysis):
    pm_status = pm["answers"].get("overall_status", "Unknown")
    tl_status = tl["answers"].get("overall_status", "Unknown") if tl else "Unknown"

    key_highlight = "No analysis available yet."
    focus_next = "No analysis available yet."
    action_required = "No high-urgency items flagged."

    if analysis:
        lessons = analysis.get("lessons_learned") or []
        if lessons:
            key_highlight = lessons[0].get("lesson", key_highlight)
        focuses = analysis.get("next_quarter_focus") or []
        if focuses:
            focus_next = focuses[0].get("focus_area", focus_next)
        high_items = [m for m in analysis.get("management_attention", []) if m.get("urgency") == "High"]
        if high_items:
            action_required = high_items[0].get("item", action_required)

    return f"""
    <div style="font-family: Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #1f2937;">
      <h2 style="color: #1e3a5f; margin-bottom: 0;">PM Quarterly Review Intelligence</h2>
      <p style="color: #2563eb; font-weight: bold; margin-top: 4px;">{quarter} {year} Report &mdash; {project}</p>

      <p>Hello,</p>
      <p>Please find attached the quarterly service delivery report for <strong>{project}</strong>
         covering {quarter} {year}.</p>

      <h3 style="color: #1e3a5f; border-bottom: 1px solid #e5e7eb; padding-bottom: 4px;">Quick Summary</h3>
      <p>
        PM Status: {STATUS_EMOJI.get(pm_status, '')} {pm_status}<br/>
        TL Status: {STATUS_EMOJI.get(tl_status, '')} {tl_status}
      </p>

      <p><strong>Key Highlights:</strong><br/>{key_highlight}</p>
      <p><strong>Focus Next Quarter:</strong><br/>{focus_next}</p>
      <p><strong>Action Required:</strong><br/>{action_required}</p>

      <p>Full report attached as PDF.</p>

      <p>Regards,<br/>PM Review Intelligence System</p>
    </div>
    """


def main():
    if len(sys.argv) < 2:
        print("Error: project name is required, e.g. `python scheduler.py ProjectName`")
        sys.exit(1)

    project = sys.argv[1]
    load_dotenv(os.path.join(BASE_DIR, ".env"))

    print(f"📧 Email scheduler started for {project}...")

    pm, tl, analysis, pdf_path = load_required(project)
    quarter = pm.get("quarter", "Q?")
    year = pm.get("year", "????")

    test_mode = os.getenv("TEST_MODE", "True").strip().lower() == "true"
    now = datetime.now()

    if test_mode:
        print("🧪 TEST MODE — Sending email immediately...")
    else:
        if now.month not in QUARTER_END_MONTHS:
            next_month, next_year = next_quarter_end(now)
            print(
                f"⏳ Not a quarter-end month. "
                f"Next send: {MONTH_NAMES[next_month]} {next_year}"
            )
            sys.exit(0)

    recipients = pm.get("stakeholder_emails") or []
    if not recipients:
        print(f"Error: no stakeholder_emails found in data/{project}/pm_answers.json")
        sys.exit(1)

    subject = f"📊 Quarterly Review Report — {project} {quarter} {year}"
    html = build_email_html(project, quarter, year, pm, tl, analysis)

    resend.api_key = os.getenv("RESEND_API_KEY")
    sender = os.getenv("SENDER_EMAIL")

    with open(pdf_path, "rb") as f:
        pdf_bytes = list(f.read())
    attachment = {"filename": os.path.basename(pdf_path), "content": pdf_bytes}

    sent_to = []
    failed = []
    for email in recipients:
        try:
            resend.Emails.send(
                {
                    "from": sender,
                    "to": email,
                    "subject": subject,
                    "html": html,
                    "attachments": [attachment],
                }
            )
            sent_to.append(email)
        except Exception as exc:
            failed.append((email, str(exc)))

    next_month, next_year = next_quarter_end(now)
    if sent_to:
        print(f"✅ Email sent to: {', '.join(sent_to)}")
    if failed:
        print("❌ Failed to send to:")
        for email, reason in failed:
            print(f"   - {email}: {reason}")
    print(f"📅 Next scheduled send: {MONTH_NAMES[next_month]} {next_year}")

    log_path = os.path.join(DATA_DIR, project, "email_log.json")
    log = {
        "project": project,
        "quarter": quarter,
        "year": year,
        "sent_at": now.isoformat(),
        "recipients": sent_to,
        "status": "sent" if sent_to and not failed else ("partial" if sent_to else "failed"),
        "test_mode": test_mode,
    }
    if failed:
        log["failed"] = [{"email": email, "reason": reason} for email, reason in failed]
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)

    print("🎉 All done! Full workflow complete.")
    print(f"📄 Report: {os.path.relpath(pdf_path, BASE_DIR).replace(os.sep, '/')}")
    print(f"📧 Emailed to: {len(sent_to)} stakeholders")
    print(f"📝 Log saved to: data/{project}/email_log.json")

    if not sent_to:
        sys.exit(1)


if __name__ == "__main__":
    main()
