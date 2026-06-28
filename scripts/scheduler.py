"""Email sending via Resend — TEST_MODE sends immediately, otherwise monthly/quarterly schedule."""

import calendar
import html
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


def build_status_line(pm_status, tl_status):
    pm_emoji = STATUS_EMOJI.get(pm_status, "")
    tl_emoji = STATUS_EMOJI.get(tl_status, "")
    if pm_status == tl_status:
        return f"Overall Status: {pm_emoji} {pm_status}"
    return (
        f"PM Status: {pm_emoji} {pm_status} · TL Status: {tl_emoji} {tl_status} "
        f"— Please review misalignment"
    )


def esc(value):
    return html.escape(str(value)) if value else ""


def build_status_html(pm_status, tl_status):
    pm_emoji = STATUS_EMOJI.get(pm_status, "")
    tl_emoji = STATUS_EMOJI.get(tl_status, "")
    if pm_status == tl_status:
        return f"<strong>Overall Status:</strong> {esc(pm_emoji)} {esc(pm_status)}"
    return (
        f"PM Status: {esc(pm_emoji)} {esc(pm_status)} · TL Status: {esc(tl_emoji)} {esc(tl_status)} "
        f"— Please review misalignment"
    )


def build_email_html(customer_name, reporting_period, prepared_by, analysis):
    meta = (analysis or {}).get("report_meta", {})
    pm_status = meta.get("pm_status", "Unknown")
    tl_status = meta.get("tl_status", "Unknown")

    s1 = ((analysis or {}).get("section_synthesis", {})).get("s1_executive_summary", {})
    highlights = s1.get("highlights") or "No highlights available yet."
    focus_next = s1.get("next_quarter_preview") or "No next-quarter focus available yet."

    attention_items = ((analysis or {}).get("ai_generated", {})).get("s13_management_attention", [])
    if attention_items:
        action_required_lines = []
        for item in attention_items:
            action_required_lines.append(
                f"- {esc(item.get('item', ''))} (Urgency: {esc(item.get('urgency', ''))}, "
                f"Source: {esc(item.get('source', ''))})<br>"
                f"&nbsp;&nbsp;{esc(item.get('explanation', ''))}"
            )
        action_required = "<br>".join(action_required_lines)
    else:
        action_required = "No action items flagged this quarter."

    status_line = build_status_html(pm_status, tl_status)

    return f"""<html><body style="font-family: Arial, sans-serif; font-size: 14px; color: #333; line-height: 1.6;">
<p>Dear Concern,</p>

<p>Please find attached the Quarterly Service Delivery Report for {esc(customer_name)}, covering {esc(reporting_period)}, prepared by {esc(prepared_by)}.</p>

<p style="font-size: 15px; font-weight: bold; color: #1B3A5C; border-bottom: 1px solid #cccccc; padding-bottom: 6px; margin-bottom: 10px;">Quick Summary</p>

<p>{status_line}</p>

<p><strong>Key Highlights:</strong><br>
{esc(highlights)}</p>

<p><strong>Focus Next Quarter:</strong><br>
{esc(focus_next)}</p>

<p><strong>Action Required:</strong><br>
{action_required}</p>

<p>The full report is attached as a PDF. Please review at your earliest convenience.</p>

<p>If you have questions or require further clarification, please reach out to us.</p>

<p>Regards,<br>
SELISE Digital Platforms</p>
</body></html>"""


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

    subject = f"Quarterly Service Delivery Report — {customer_name} | {reporting_period}"
    prepared_by = pm.get("prepared_by", "") or (analysis or {}).get("report_meta", {}).get("prepared_by", "")
    body_html = build_email_html(customer_name, reporting_period, prepared_by, analysis)

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
                    "html": body_html,
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
