"""Role selection + Q&A session (PM and TL) — saves answers to data/<Project>/*.json"""

import json
import os
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


def current_quarter_year():
    now = datetime.now()
    quarter = (now.month - 1) // 3 + 1
    return f"Q{quarter}", str(now.year)


def run_questionnaire(preset_role=None, preset_project=None, auto_chain=True):
    """Runs the Q&A session. Returns the project name on success, or None if blocked/aborted."""
    header("PM Quarterly Review Intelligence")
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

    header("Project")
    project = preset_project if preset_project else ask_text("What is the project name?")
    project_dir = os.path.join(DATA_DIR, project)
    pm_path = os.path.join(project_dir, "pm_answers.json")
    tl_path = os.path.join(project_dir, "tl_answers.json")

    if role == "PM":
        if not os.path.exists(project_dir):
            os.makedirs(project_dir)
            print(f"Created new project folder for '{project}'.")
        else:
            print(f"Project '{project}' found.")
    else:
        if not os.path.exists(pm_path):
            print(
                "\nPM has not submitted yet for this project. "
                "Please ask PM to complete their session first."
            )
            return None
        print(f"Project '{project}' found. Linked to PM submission.")

    header("Q1 — Executive Summary")
    executive_summary = ask_text(
        "How would you summarize this quarter overall?\n"
        "What was the delivery focus and key highlights?"
    )

    header("Q2 — Overall Status")
    status_choice = ask_choice(
        "What is the overall delivery status for this quarter?",
        STATUS_LABELS,
    )
    overall_status = STATUS_MAP[status_choice]

    header("Q3 — Key Achievements & Value Delivered")
    key_achievements = ask_text(
        "What were the key achievements this quarter\n"
        "and what value did they deliver?"
    )

    header("Q4 — Risks, Issues & Challenges")
    risks_and_challenges = ask_text(
        "What were the main risks, issues, or challenges\n"
        "faced this quarter? What was the impact?"
    )

    header("Q5 — Quality & Team Health")
    quality_and_team_health = ask_text(
        "How was the overall quality and team health\n"
        "this quarter? Any incidents, blockers, or\n"
        "concerns worth noting?"
    )

    stakeholder_emails = None
    if role == "PM":
        header("Stakeholder Emails")
        emails_text = ask_text(
            "Who should receive this quarterly report?\n"
            "Enter stakeholder emails (comma separated):"
        )
        stakeholder_emails = [e.strip() for e in emails_text.split(",") if e.strip()]

    quarter, year = current_quarter_year()
    record = {
        "role": role,
        "project": project,
        "quarter": quarter,
        "year": year,
        "submitted_at": datetime.now().isoformat(),
        "answers": {
            "executive_summary": executive_summary,
            "overall_status": overall_status,
            "key_achievements": key_achievements,
            "risks_and_challenges": risks_and_challenges,
            "quality_and_team_health": quality_and_team_health,
        },
    }
    if role == "PM":
        record["stakeholder_emails"] = stakeholder_emails

    os.makedirs(project_dir, exist_ok=True)
    out_path = pm_path if role == "PM" else tl_path
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)

    header("Done")
    if role == "PM":
        print(f"✅ PM submission saved for {project}")
        if os.path.exists(tl_path):
            print("TL already submitted. Run agent.py to generate the report.")
    else:
        print(f"✅ Tech Lead submission saved for {project}")
        if os.path.exists(pm_path):
            if auto_chain:
                print("Both submissions found. Triggering analysis agent...")
                agent_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent.py")
                subprocess.run([sys.executable, agent_script, project])
            else:
                print("Both submissions found.")

    return project


def main():
    run_questionnaire()


if __name__ == "__main__":
    main()
