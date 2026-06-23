# PM Quarterly Review Intelligence
> An agentic AI workflow for quarterly service delivery reviews.
> PM and Tech Lead answer 5 questions each → AI analyzes both → PDF report generated → Email sent to stakeholders.

---

## Quick Start

### Step 1 — Navigate to project folder
```bash
cd "C:\Users\DELL\OneDrive\Desktop\pm-q-session-oc"
```

### Step 2 — Run the master orchestrator (recommended)
```bash
python scripts/run.py
```
This single command drives the whole workflow. It will ask:
1. **What would you like to do?**
   - `1` — Full automatic workflow (PM + TL + Analysis + PDF + Email)
   - `2` — PM turn only
   - `3` — TL turn only
   - `4` — Run analysis only
   - `5` — Generate PDF only
   - `6` — Send email only
2. **Enter project name** — e.g. `S7000`

For option `1`, `run.py` walks through both the PM and TL Q&A sessions back to back, then runs analysis, generates the PDF, and sends the email — printing a step-by-step progress banner and a final summary box. If any step fails, it will ask whether to retry that step before giving up.

Options `2`–`6` run a single stage, with the same pre-checks as running each script manually (e.g. option `3` checks that the PM has already submitted before letting the TL start).

> Prefer to drive the steps yourself instead? See [Manual Commands](#manual-commands-if-needed) below — `questionnaire.py`, `agent.py`, `generate_pdf.py`, and `scheduler.py` all still work exactly as standalone scripts.

### Manual alternative — Step by step

#### PM Turn
```bash
python scripts/questionnaire.py
```
- Select: `1` (Product Manager)
- Enter project name e.g. `S7000`
- Answer 5 questions
- Enter stakeholder emails at the end

#### Tech Lead Turn
```bash
python scripts/questionnaire.py
```
- Select: `2` (Tech Lead)
- Enter **same** project name e.g. `S7000`
- Answer 5 questions
- Agent triggers automatically after submission

---

## What Happens Automatically After TL Submits

```
✅ Both answers saved
🤖 AI Agent analyzes PM + TL answers
📄 PDF report generated
📧 Email sent to stakeholders
🎉 Done!
```

---

## Manual Commands (if needed)

Run each step individually if something fails:

```bash
# Run agent only
python scripts/agent.py S7000

# Run PDF generator only
python scripts/generate_pdf.py S7000

# Run email scheduler only
python scripts/scheduler.py S7000
```

Replace `S7000` with your actual project name.

Equivalent single-stage commands via the orchestrator:
```bash
python scripts/run.py   # then choose 4 (analysis), 5 (PDF), or 6 (email)
```

---

## Output Files

| File | What it is |
|---|---|
| `data/ProjectName/pm_answers.json` | PM's answers |
| `data/ProjectName/tl_answers.json` | Tech Lead's answers |
| `data/ProjectName/analysis.json` | AI agent analysis |
| `data/ProjectName/email_log.json` | Email send log |
| `output/ProjectName_Q2_2026.pdf` | Final PDF report |

---

## Environment Variables (.env)

```
RESEND_API_KEY=your_resend_api_key
SENDER_EMAIL=onboarding@resend.dev
TEST_MODE=True
```

### TEST_MODE
| Value | Behaviour |
|---|---|
| `True` | Email sends immediately after PDF is generated |
| `False` | Email sends only in March / June / September / December |

---

## Email Notes

- Currently using `onboarding@resend.dev` as sender (Resend test address)
- In test mode, emails can only be sent to your own Resend signup email
- To send to any email → verify your domain at resend.com/domains
- Then update `SENDER_EMAIL` to `anything@yourdomain.com` in `.env`

---

## Report Structure

| Section | Source |
|---|---|
| Q&A — PM answers | Product Manager |
| Q&A — TL answers | Tech Lead |
| Lessons Learned | AI Agent |
| Next Quarter Focus | AI Agent |
| Management Attention Required | AI Agent |
| Closing Note | AI Agent |

---

## Quarterly Schedule (when TEST_MODE=False)

| Quarter | Send Month |
|---|---|
| Q1 | March |
| Q2 | June |
| Q3 | September |
| Q4 | December |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `pm_answers.json not found` | Run PM turn first before TL turn |
| `Email failed — gmail domain not verified` | Change `SENDER_EMAIL` to `onboarding@resend.dev` |
| `Can only send to own email` | Use your Resend signup email as stakeholder OR verify a domain |
| `PDF not found` | Run `python scripts/generate_pdf.py ProjectName` manually |
| `Module not found` | Run `pip install reportlab resend python-dotenv` |
| A step fails inside `run.py` | It will ask `Would you like to retry? (y/n)` — fix the issue, then type `y` |

---

## Built With

- **Claude Code** — AI agent + code generation
- **Python** — scripting language
- **reportlab** — PDF generation
- **Resend** — email delivery
- **python-dotenv** — environment variables