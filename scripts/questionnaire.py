"""Role selection + Q&A session (PM and TL) — saves answers to data/<Session>/*.json.

PM and TL have different question sets (see CLAUDE.md Phase 8). A session is keyed by
customer_name + reporting_period (folder: data/<CustomerName>_<Q#_YYYY>/).
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

STATUS_MAP = {"1": "Green", "2": "Amber", "3": "Red"}
STATUS_LABELS = {
    "1": "🟢 Green — On track, no major concern",
    "2": "🟡 Amber — Some risk or delay, manageable",
    "3": "🔴 Red   — Significant issue requiring attention",
}

REPORTING_PERIODS = {
    "1": "Q1 2026",
    "2": "Q2 2026",
    "3": "Q3 2026",
    "4": "Q4 2026",
}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def header(title):
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


def ask_choice(prompt, options):
    while True:
        print(prompt)
        for key, label in options.items():
            print(f"  {key}. {label}")
        choice = input("> ").strip()
        if choice in options:
            return choice
        print("Please enter a valid option.\n")


def ask_text(prompt):
    print(prompt)
    while True:
        text = input("> ").strip()
        if text:
            return text
        print("This answer can't be empty, please try again.")


def ask_emails(prompt):
    while True:
        text = ask_text(prompt)
        emails = [e.strip() for e in text.split(",") if e.strip()]
        invalid = [e for e in emails if not EMAIL_RE.match(e)]
        if emails and not invalid:
            return emails
        print(f"Invalid email(s): {', '.join(invalid) if invalid else 'none entered'}. Please try again.")


def session_key(customer_name, reporting_period):
    safe_customer = re.sub(r"\s+", "", customer_name.strip())
    safe_period = reporting_period.replace(" ", "_")
    return f"{safe_customer}_{safe_period}"


def run_pm_session(session_dir, customer_name, reporting_period):
    header("Setup")
    prepared_by = ask_text("Prepared by — enter your name and role (e.g. John Smith, Delivery Manager)")
    recipient_emails = ask_emails(
        "Who should receive this report? Enter stakeholder emails (comma-separated)"
    )

    header("Delivery & Overview")
    pm_q1 = ask_text("What was the overall delivery focus and key activities this quarter?")
    status_choice = ask_choice(
        "What is the overall service delivery status?", STATUS_LABELS
    )
    pm_q2 = STATUS_MAP[status_choice]
    pm_q3 = ask_text(
        "Describe the active services, delivery model, team composition, and reporting cadence."
    )

    header("Achievements & Delivery")
    pm_q4 = ask_text(
        "What were the key achievements this quarter and what business value did they deliver?"
    )
    pm_q5 = ask_text(
        "Summarise each active workstream or project — its status (Green/Amber/Red), progress, and key notes."
    )

    header("Metrics & Customer")
    pm_q6 = ask_text(
        "What were the key service metrics this quarter? Cover CSAT score, SLA compliance %, "
        "and release success rate — include target vs actual for each."
    )
    pm_q7 = ask_text(
        "How was the customer relationship this quarter? Cover satisfaction, communication, "
        "responsiveness, business alignment, and any areas of concern."
    )
    health_choice = ask_choice("Overall relationship health?", STATUS_LABELS)
    pm_q8 = STATUS_MAP[health_choice]

    record = {
        "role": "PM",
        "customer_name": customer_name,
        "reporting_period": reporting_period,
        "prepared_by": prepared_by,
        "recipient_emails": recipient_emails,
        "submitted_at": datetime.now().isoformat(),
        "answers": {
            "pm_q1": pm_q1,
            "pm_q2": pm_q2,
            "pm_q3": pm_q3,
            "pm_q4": pm_q4,
            "pm_q5": pm_q5,
            "pm_q6": pm_q6,
            "pm_q7": pm_q7,
            "pm_q8": pm_q8,
        },
    }
    out_path = os.path.join(session_dir, "pm_answers.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    return record


def run_tl_session(session_dir, customer_name, reporting_period):
    header("Delivery & Achievements")
    tl_q1 = ask_text(
        "From a technical standpoint, what was the delivery focus and key engineering "
        "activities this quarter?"
    )
    status_choice = ask_choice(
        "What is your assessment of the overall delivery status?", STATUS_LABELS
    )
    tl_q2 = STATUS_MAP[status_choice]
    tl_q3 = ask_text(
        "What were the key technical achievements? Include releases, performance "
        "improvements, security work, or architecture changes."
    )

    header("Incidents & Quality")
    tl_q4 = ask_text(
        "What were the support and incident numbers this quarter? Cover total tickets, "
        "resolved, open, critical and major incidents. For any major incident include: "
        "date, issue, root cause, action taken, and current status."
    )
    tl_q5 = ask_text(
        "How was overall quality and delivery health? Cover code quality, QA, release "
        "management, documentation, team communication, and team stability."
    )

    header("Risks & Next Quarter")
    tl_q6 = ask_text(
        "What risks, issues, or dependencies exist? For each, describe the type, impact "
        "level (High/Med/Low), owner, and mitigation or next step."
    )
    tl_q7 = ask_text(
        "What should be the technical focus for next quarter? Include any blockers, "
        "tech debt, or priorities the team must address."
    )

    record = {
        "role": "TL",
        "customer_name": customer_name,
        "reporting_period": reporting_period,
        "submitted_at": datetime.now().isoformat(),
        "answers": {
            "tl_q1": tl_q1,
            "tl_q2": tl_q2,
            "tl_q3": tl_q3,
            "tl_q4": tl_q4,
            "tl_q5": tl_q5,
            "tl_q6": tl_q6,
            "tl_q7": tl_q7,
        },
    }
    out_path = os.path.join(session_dir, "tl_answers.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    return record


def run_questionnaire(preset_role=None, preset_session=None, auto_chain=True):
    """Runs the Q&A session. Returns the session key (folder name) on success, or None if blocked/aborted."""
    header("PM Review Intelligence")
    print("Hi! Let's get your quarterly review session started.")

    if preset_role in ("PM", "TL"):
        role = preset_role
    else:
        role_choice = ask_choice(
            "\nWhat is your role?", {"1": "Product Manager", "2": "Tech Lead"}
        )
        role = "PM" if role_choice == "1" else "TL"
    role_label = "Product Manager" if role == "PM" else "Tech Lead"
    print(f"\nRole set to: {role_label}")

    header("Customer / Project")
    if preset_session:
        customer_name, reporting_period = preset_session
    else:
        customer_name = ask_text("What is the customer / project name?")
        period_choice = ask_choice("What is the reporting period?", REPORTING_PERIODS)
        reporting_period = REPORTING_PERIODS[period_choice]

    session = session_key(customer_name, reporting_period)
    session_dir = os.path.join(DATA_DIR, session)
    pm_path = os.path.join(session_dir, "pm_answers.json")
    tl_path = os.path.join(session_dir, "tl_answers.json")

    if role == "PM":
        if not os.path.exists(session_dir):
            os.makedirs(session_dir)
            print(f"Created new session for '{customer_name}' — {reporting_period}.")
        else:
            print(f"Session for '{customer_name}' — {reporting_period} found.")
        run_pm_session(session_dir, customer_name, reporting_period)
    else:
        if not os.path.exists(pm_path):
            print(
                "\nPM has not submitted yet for this customer/period. "
                "Please ask PM to complete their session first."
            )
            return None
        print(f"Session for '{customer_name}' — {reporting_period} found. Linked to PM submission.")
        os.makedirs(session_dir, exist_ok=True)
        run_tl_session(session_dir, customer_name, reporting_period)

    header("Done")
    if role == "PM":
        print(f"✅ PM submission saved for {customer_name} — {reporting_period}")
        if os.path.exists(tl_path):
            print("TL already submitted. Run agent.py to generate the report.")
    else:
        print(f"✅ Tech Lead submission saved for {customer_name} — {reporting_period}")
        if os.path.exists(pm_path):
            if auto_chain:
                print("Both submissions found. Triggering analysis agent...")
                agent_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent.py")
                subprocess.run([sys.executable, agent_script, session])
            else:
                print("Both submissions found.")

    return session


def main():
    run_questionnaire()


if __name__ == "__main__":
    main()
