"""Email sending via Resend — TEST_MODE sends immediately, otherwise monthly/quarterly schedule."""

import calendar
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


def last_working_day(year, month):
    last_day = calendar.monthrange(year, month)[1]
    day = last_day
    while calendar.weekday(year, month, day) >= 5:  # 5=Sat, 6=Sun
        day -= 1
    return day


def is_send_day(now, schedule_mode):
    if schedule_mode == "quarterly":
        return now.month in QUARTER_END_MONTHS and now.day >= last_working_day(now.year, now.month)
    return now.day >= last_working_day(now.year, now.month)


def next_send_description(now, schedule_mode):
    if schedule_mode == "quarterly":
        month, year = now.month, now.year
        for m in QUARTER_END_MONTHS:
            if m > month or (m == month and now.day < last_working_day(year, m)):
                return f"last working day of {MONTH_NAMES[m]} {year}"
        return f"last working day of {MONTH_NAMES[QUARTER_END_MONTHS[0]]} {year + 1}"
    month, year = now.month, now.year
    if now.day < last_working_day(year, month):
        return f"last working day of {MONTH_NAMES[month]} {year}"
    next_month, next_year = (month + 1, year) if month < 12 else (1, year + 1)
    return f"last working day of {MONTH_NAMES[next_month]} {next_year}"


def load_required(session):
    session_dir = os.path.join(DATA_DIR, session)
    pm_path = os.path.join(session_dir, "pm_answers.json")

    if not os.path.exists(pm_path):
        print(f"Error: missing data/{session}/pm_answers.json")
        return None, None, None, None
    with open(pm_path, "r", encoding="utf-8") as f:
        pm = json.load(f)

    pdf_path = os.path.join(OUTPUT_DIR, f"{session}.pdf")
    if not os.path.exists(pdf_path):
        print(f"Error: missing {os.path.relpath(pdf_path, BASE_DIR)}")
        return None, None, None, None

    tl = None
    tl_path = os.path.join(session_dir, "tl_answers.json")
    if os.path.exists(tl_path):
        with open(tl_path, "r", encoding="utf-8") as f:
            tl = json.load(f)

    analysis = None
    analysis_path = os.path.join(session_dir, "analysis.json")
    if os.path.exists(analysis_path):
        with open(analysis_path, "r", encoding="utf-8") as f:
            analysis = json.load(f)

    return pm, tl, analysis, pdf_path


def build_email_html(customer_name, reporting_period, pm, tl, analysis):
    pm_status = pm["answers"].get("pm_q2", "Unknown")
    tl_status = tl["answers"].get("tl_q2", "Unknown") if tl else "Unknown"

    key_highlight = "No analysis available yet."
    focus_next = "No analysis available yet."
    action_required = "No high-urgency items flagged."

    if analysis:
        ai = analysis.get("ai_generated", {})
        lessons = ai.get("s11_lessons_learned") or []
        if lessons:
            key_highlight = lessons[0].get("lesson", key_highlight)
        focuses = ai.get("s12_next_quarter_focus") or []
        if focuses:
            focus_next = focuses[0].get("focus_area", focus_next)
        high_items = [m for m in ai.get("s13_management_attention", []) if m.get("urgency") == "High"]
        if high_items:
            action_required = high_items[0].get("item", action_required)

    return f"""
    <div style="font-family: Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #1f2937;">
      <h2 style="color: #1e3a5f; margin-bottom: 0;">Quarterly Service Delivery Report</h2>
      <p style="color: #2563eb; font-weight: bold; margin-top: 4px;">{reporting_period} &mdash; {customer_name}</p>

      <p>Hello,</p>
      <p>Please find attached the quarterly service delivery report for <strong>{customer_name}</strong>
         covering {reporting_period}.</p>

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


def run_scheduler(session):
    """Sends the report email for `session`. Returns True on success/intentional skip, False on failure."""
    load_dotenv(os.path.join(BASE_DIR, ".env"))

    print(f"📧 Email scheduler started for {session}...")

    pm, tl, analysis, pdf_path = load_required(session)
    if pm is None:
        return False
    customer_name = pm.get("customer_name", session)
    reporting_period = pm.get("reporting_period", "")

    send_email = os.getenv("SEND_EMAIL", "False").strip().lower() == "true"
    if not send_email:
        print(f"Email delivery skipped. PDF saved to output/{os.path.basename(pdf_path)}")
        return True

    test_mode = os.getenv("TEST_MODE", "True").strip().lower() == "true"
    schedule_mode = os.getenv("SCHEDULE_MODE", "monthly").strip().lower()
    if schedule_mode not in ("monthly", "quarterly"):
        schedule_mode = "monthly"
    now = datetime.now()

    if test_mode:
        print("🧪 TEST MODE — Sending email immediately...")
    else:
        if not is_send_day(now, schedule_mode):
            print(f"⏳ Not a scheduled send day ({schedule_mode}). Next send: {next_send_description(now, schedule_mode)}")
            return True

    recipients = pm.get("recipient_emails") or []
    if not recipients:
        print(f"Error: no recipient_emails found in data/{session}/pm_answers.json")
        return False

    subject = f"📊 Quarterly Service Delivery Report — {customer_name} {reporting_period}"
    html = build_email_html(customer_name, reporting_period, pm, tl, analysis)

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

    if sent_to:
        print(f"✅ Email sent to: {', '.join(sent_to)}")
    if failed:
        print("❌ Failed to send to:")
        for email, reason in failed:
            print(f"   - {email}: {reason}")
    print(f"📅 Schedule mode: {schedule_mode} | Next scheduled send: {next_send_description(now, schedule_mode)}")

    log_path = os.path.join(DATA_DIR, session, "email_log.json")
    log = {
        "session": session,
        "customer_name": customer_name,
        "reporting_period": reporting_period,
        "sent_at": now.isoformat(),
        "recipients": sent_to,
        "status": "sent" if sent_to and not failed else ("partial" if sent_to else "failed"),
        "test_mode": test_mode,
        "schedule_mode": schedule_mode,
    }
    if failed:
        log["failed"] = [{"email": email, "reason": reason} for email, reason in failed]
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)

    print("🎉 All done! Full workflow complete.")
    print(f"📄 Report: {os.path.relpath(pdf_path, BASE_DIR).replace(os.sep, '/')}")
    print(f"📧 Emailed to: {len(sent_to)} stakeholders")
    print(f"📝 Log saved to: data/{session}/email_log.json")

    return bool(sent_to)


def main():
    if len(sys.argv) < 2:
        print("Error: session name is required, e.g. `python scheduler.py CustomerName_Q2_2026`")
        sys.exit(1)

    success = run_scheduler(sys.argv[1])
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
