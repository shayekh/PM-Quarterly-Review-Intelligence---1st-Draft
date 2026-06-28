"""Master orchestrator — runs the full PM Review Intelligence workflow end to end."""

import os
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPTS_DIR)
DATA_DIR = os.path.join(BASE_DIR, "data")
sys.path.insert(0, SCRIPTS_DIR)

from questionnaire import run_questionnaire, session_key, REPORTING_PERIODS, ask_text, ask_choice
from agent import run_agent
from generate_pdf import run_pdf
from scheduler import run_scheduler


def divider():
    print("─" * 35)


def session_paths(session):
    session_dir = os.path.join(DATA_DIR, session)
    return {
        "pm": os.path.join(session_dir, "pm_answers.json"),
        "tl": os.path.join(session_dir, "tl_answers.json"),
        "analysis": os.path.join(session_dir, "analysis.json"),
    }


def prompt_session():
    print("\nEnter customer / project name:")
    customer_name = input("> ").strip()
    while not customer_name:
        print("Customer name can't be empty.")
        customer_name = input("> ").strip()
    period_choice = ask_choice("What is the reporting period?", REPORTING_PERIODS)
    reporting_period = REPORTING_PERIODS[period_choice]
    return customer_name, reporting_period


def run_with_retry(step_name, func, *args, **kwargs):
    """Runs `func`, and on failure (return value of False or an exception) asks the user
    whether to retry that step. Returns whatever `func` returned on eventual success,
    or None if the user chooses not to retry."""
    while True:
        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            print(f"❌ Error during {step_name}: {exc}")
            result = False

        if result:
            return result

        print(f"❌ {step_name} did not complete successfully.")
        retry = input("Would you like to retry? (y/n) > ").strip().lower()
        if retry != "y":
            print("Exiting.")
            sys.exit(1)


def main():
    print("╔════════════════════════════════════════╗")
    print("║   PM Review Intelligence               ║")
    print("║   Agentic Workflow                     ║")
    print("╚════════════════════════════════════════╝")

    print(
        "\nWhat would you like to do?\n"
        "1. Full automatic workflow (PM + TL + Analysis + PDF + Email)\n"
        "2. PM turn only\n"
        "3. TL turn only\n"
        "4. Run analysis only\n"
        "5. Generate PDF only\n"
        "6. Send email only"
    )
    while True:
        mode = input("> ").strip()
        if mode in {"1", "2", "3", "4", "5", "6"}:
            break
        print("Please enter a number from 1-6.")

    customer_name, reporting_period = prompt_session()
    session = session_key(customer_name, reporting_period)
    paths = session_paths(session)

    if mode == "1":
        divider()
        print("📋 STEP 1 OF 5 — PM Q&A Session")
        divider()
        run_with_retry(
            "PM Q&A session",
            lambda: run_questionnaire(preset_role="PM", preset_session=(customer_name, reporting_period), auto_chain=False),
        )

        divider()
        print("📋 STEP 2 OF 5 — Tech Lead Q&A Session")
        divider()
        run_with_retry(
            "Tech Lead Q&A session",
            lambda: run_questionnaire(preset_role="TL", preset_session=(customer_name, reporting_period), auto_chain=False),
        )

        divider()
        print("🤖 STEP 3 OF 5 — AI Agent Analysis")
        divider()
        run_with_retry("AI Agent Analysis", run_agent, session, auto_chain=False)

        divider()
        print("📄 STEP 4 OF 5 — Generating PDF")
        divider()
        run_with_retry("PDF generation", run_pdf, session, auto_chain=False)

        divider()
        print("📧 STEP 5 OF 5 — Sending Email")
        divider()
        run_with_retry("Email send", run_scheduler, session)

        import json
        with open(paths["pm"], "r", encoding="utf-8") as f:
            pm = json.load(f)
        recipients = pm.get("recipient_emails") or []
        pdf_rel = f"output/{session}.pdf"

        inner_width = 40

        def box_line(text=""):
            print(f"║{text:<{inner_width}}║")

        print(f"╔{'═' * inner_width}╗")
        box_line("   ✅ WORKFLOW COMPLETE")
        box_line()
        box_line(f"   Customer: {customer_name}")
        box_line(f"   Report:   {pdf_rel}")
        box_line(f"   Emailed:  {len(recipients)} stakeholders")
        print(f"╚{'═' * inner_width}╝")

    elif mode == "2":
        run_with_retry(
            "PM Q&A session",
            lambda: run_questionnaire(preset_role="PM", preset_session=(customer_name, reporting_period), auto_chain=False),
        )
        print("✅ PM turn complete. Run TL turn next.")

    elif mode == "3":
        if not os.path.exists(paths["pm"]):
            print(
                f"Error: pm_answers.json not found for '{session}'. "
                "PM must complete their turn first."
            )
            sys.exit(1)
        run_with_retry(
            "Tech Lead Q&A session",
            lambda: run_questionnaire(preset_role="TL", preset_session=(customer_name, reporting_period), auto_chain=False),
        )
        print("✅ TL turn complete.")

    elif mode == "4":
        missing = [name for name in ("pm", "tl") if not os.path.exists(paths[name])]
        if missing:
            print(f"Error: missing {', '.join(f'{m}_answers.json' for m in missing)} for '{session}'.")
            sys.exit(1)
        run_with_retry("AI Agent Analysis", run_agent, session, auto_chain=False)
        print("✅ Analysis complete.")

    elif mode == "5":
        if not os.path.exists(paths["analysis"]):
            print(f"Error: analysis.json not found for '{session}'. Run analysis first.")
            sys.exit(1)
        run_with_retry("PDF generation", run_pdf, session, auto_chain=False)
        print("✅ PDF generated.")

    elif mode == "6":
        pdf_path = os.path.join(BASE_DIR, "output", f"{session}.pdf")
        if not os.path.exists(pdf_path):
            print(f"Error: PDF not found for '{session}' (expected output/{session}.pdf).")
            sys.exit(1)
        run_with_retry("Email send", run_scheduler, session)
        print("✅ Email sent.")


if __name__ == "__main__":
    main()
