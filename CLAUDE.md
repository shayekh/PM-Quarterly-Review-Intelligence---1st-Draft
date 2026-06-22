# PM Quarterly Review Intelligence — CLAUDE.md

> This file is the persistent memory for this project.
> Always read this before doing anything. Update this file whenever the plan evolves.

---

## What We Are Building

A **terminal-based agentic AI workflow** running entirely inside Claude Code. No web app. No database. No separate API keys for AI. Claude itself is the agent — it asks questions, reasons across answers, makes decisions, generates the report, and triggers the email scheduler.

---

## Who Uses It

- **Product Manager** — starts the session, answers 5 questions from PM perspective, provides stakeholder emails
- **Tech Lead** — answers same 5 questions from technical perspective
- **Stakeholders** — receive the final PDF report via scheduled email (no login needed)

### User Roles
| Role | What They Do |
|---|---|
| Product Manager | Selects role, picks project, answers 5 questions, provides recipient emails |
| Tech Lead | Selects role, picks same project, answers same 5 questions |
| Both | Answer independently — neither sees the other's answers until analysis is done |

---

## Tech Stack

| Layer | Choice |
|---|---|
| Interface | Claude Code (Pro subscription — no separate API key needed) |
| Language | Python |
| Q&A Collection | Claude asks questions → answers saved to JSON files |
| Storage | Local files (`data/ProjectName/`) |
| AI Analysis | Claude itself (inside Claude Code session) |
| PDF Generation | Python `reportlab` |
| Output | `/output/ProjectName_Q1_2026.pdf` |
| Email Sending | Resend API |
| Scheduler | TEST_MODE: sends immediately | PROD: quarterly |

---

## Environment Variables (.env)

```
RESEND_API_KEY=your_resend_api_key
SENDER_EMAIL=your_sender_email
TEST_MODE=True
```

No Anthropic API key needed.
Claude Code (Pro subscription) handles all AI reasoning.
Only Resend is needed for email delivery.

---

## Question Set

Claude asks questions sequentially in one session.
First asks role, then project name, then 5 core questions.
All answers are free text except Overall Status which is a choice.

### Step 0 — Role Selection
```
Claude: "What is your role?"
→ 1. Product Manager
→ 2. Tech Lead
```

### Step 1 — Project Name
```
Claude: "What is the project name?"
→ Free text
```

### 5 Core Questions (same for PM and TL)

Q1 — Executive Summary
```
Claude: "How would you summarize this quarter overall?
         What was the delivery focus and key highlights?"
→ Free text
```

Q2 — Overall Status
```
Claude: "What is the overall delivery status for this quarter?"
→ 🟢 Green — On track, no major concern
→ 🟡 Amber — Some risk or delay, manageable
→ 🔴 Red   — Significant issue requiring attention
```

Q3 — Key Achievements & Value Delivered
```
Claude: "What were the key achievements this quarter
         and what value did they deliver?"
→ Free text
```

Q4 — Risks, Issues & Challenges
```
Claude: "What were the main risks, issues, or challenges
         faced this quarter? What was the impact?"
→ Free text
```

Q5 — Quality & Team Health
```
Claude: "How was the overall quality and team health
         this quarter? Any incidents, blockers, or
         concerns worth noting?"
→ Free text
```

### End of PM Session Only
```
Claude: "Who should receive this quarterly report?
         Enter stakeholder emails (comma separated)"
→ Free text
```

**Total: 2 setup questions + 5 core questions + 1 email (PM only)**

---

## Project Linking Rules

- PM starts session → selects role → picks project name → data tagged to that project
- TL starts session → selects role → picks same project name → automatically linked
- Both answers belong to the same project → agent analyzes them together
- Only PM fills stakeholder emails → TL never touches recipient list
- One project = one PM answer file + one TL answer file + one PDF report

---

## Agentic Workflow

This is a **goal-driven autonomous AI agent** with a sequential multi-step pipeline,
tool use (file system + email), and decision-making logic — all inside one Claude Code session.
Claude IS the agent. No external AI API calls needed.

```
ONE CLAUDE CODE SESSION — THREE TURNS

─────────────── PM TURN ───────────────
Claude: "What is your role?"         → PM selects: Product Manager
Claude: "What is the project name?"  → PM types: "Project A"
Claude asks Q1 → Q5                  → PM answers each
Claude: "Who receives this report?"  → PM enters emails

Saved to: data/ProjectA/pm_answers.json ✅
───────────────────────────────────────
            ↓
────────────── TL TURN ────────────────
Claude: "What is your role?"         → TL selects: Tech Lead
Claude: "What is the project name?"  → TL types: "Project A"
Claude: "Project A found. Linked."
Claude asks Q1 → Q5                  → TL answers each

Saved to: data/ProjectA/tl_answers.json ✅
───────────────────────────────────────
            ↓
────────── AGENT (Claude reasons) ─────
Both files detected. Agent runs automatically.

  PLANS   → knows the full sequence ahead
  ACTS    → reads pm_answers.json + tl_answers.json

  REASONS (Step 1 — Section Analysis)
  → compares PM vs TL answer per question
  → classifies: agree / disagree / complement / blind spot

  REASONS (Step 2 — Pattern Detection)
  → finds recurring themes across all 5 questions
  → identifies critical misalignments

  DECIDES (Step 3 — Report Writing)
  → Lessons Learned
  → Next Quarter Focus
  → Management Attention Required
  → Closing Note

  SELF-CHECKS (Step 4 — Quality)
  → every finding backed by data?
  → all misalignments flagged?
  → refines if weak

  ACTS → generates PDF ✅
  Saved to: output/ProjectA_Q1_2026.pdf
───────────────────────────────────────
            ↓
────────────── SCHEDULER ──────────────
TEST_MODE=True  → email sends immediately after PDF
TEST_MODE=False → email sends quarterly (March/June/Sept/Dec)

Reads emails saved during PM session
Sends PDF to all stakeholders via Resend ✅
───────────────────────────────────────
```

---

## AI Reasoning Rules

| Relationship | What AI Does |
|---|---|
| Both agree | Treat as strong confirmed signal, reinforce in analysis |
| They disagree | Flag root cause misalignment in Management Attention |
| They complement | Merge both views into one richer insight |
| One sees risk, other doesn't | Surface as blind spot, flag urgency |
| One answered, other didn't | Note the gap, don't ignore it |

---

## AI Prompt Template

```
You are a senior delivery consultant analyzing a quarterly service delivery review.

You have received answers from TWO people for the same project:
- Product Manager (PM): focused on delivery, stakeholders, business value
- Tech Lead (TL): focused on technical quality, architecture, engineering health

Read BOTH sets of answers and produce ONE unified holistic analysis.
Do NOT write a comparison. Write one coherent synthesis of both perspectives.

For each question internally assess:
- Do they agree?            → Reinforce as strong signal
- Do they disagree?         → Flag misalignment in Management Attention
- Do they complement?       → Merge into richer insight
- Does one miss something?  → Highlight as blind spot

PM Answers:
{pm_answers}

Tech Lead Answers:
{tl_answers}

Respond ONLY in this JSON format, no preamble, no markdown:
{
  "lessons_learned": [
    { "lesson": "...", "context": "...", "action": "..." }
  ],
  "next_quarter_focus": [
    { "focus_area": "...", "expected_outcome": "...", "owner": "PM|Tech Lead|Both" }
  ],
  "management_attention": [
    {
      "item": "...",
      "type": "Decision|Approval|Budget|Resource|Escalation|Misalignment",
      "explanation": "...",
      "urgency": "High|Medium|Low",
      "source": "PM|Tech Lead|Both|Disagreement"
    }
  ],
  "closing_note": "..."
}
```

---

## PDF Report Structure

```
Cover Page
  → Project Name, Quarter/Year, Date

Q&A Section (PM + TL answers side by side per question)
  ┌─────────────────────┬──────────────────────┐
  │   PM's Answer       │   Tech Lead's Answer  │
  └─────────────────────┴──────────────────────┘

AI Analysis Section (unified, generated by agent)
  → Lessons Learned
  → Next Quarter Focus     (table: Focus Area, Outcome, Owner)
  → Management Attention   (urgency badges: High / Medium / Low)
  → Closing Note

Footer: page numbers, project name, quarter
```

The report tells the **complete story**:
what PM said + what TL said + what AI concluded from both.

---

## Folder Structure

```
pm-review-intelligence/
├── CLAUDE.md
├── .env
├── data/
│   └── ProjectA/
│       ├── pm_answers.json
│       └── tl_answers.json
├── output/
│   └── ProjectA_Q1_2026.pdf
└── scripts/
    ├── questionnaire.py     # Role selection + Q&A session (PM and TL)
    ├── agent.py             # 4-step agentic analysis
    ├── generate_pdf.py      # PDF generation (reportlab)
    └── scheduler.py         # Email sending via Resend
```

---

## Build Phases

| Phase | What Gets Built | Status |
|---|---|---|
| 1 | Project scaffold + folder structure + .env setup | ⬜ Not started |
| 2 | Questionnaire script — role selection + Q&A + saves to JSON | ⬜ Not started |
| 3 | Agent script — 4-step reasoning + analysis output | ⬜ Not started |
| 4 | PDF generation — PM + TL answers + AI analysis combined | ⬜ Not started |
| 5 | Email scheduler — Resend + TEST_MODE | ⬜ Not started |

---

## Key Decisions Made

- No web app, no database, no login — everything runs in Claude Code
- Claude Pro subscription handles all AI — no separate Anthropic API key
- PM and TL answer the same 5 questions independently
- Neither sees the other's answers until analysis is complete
- Agent triggers automatically when both JSON files exist
- AI produces one unified holistic analysis — not a comparison
- Where PM and TL disagree → flagged in Management Attention with source = "Disagreement"
- PDF shows PM + TL answers side by side + AI analysis sections
- Only PM provides stakeholder emails — collected at end of PM session
- TEST_MODE=True sends email immediately after PDF is generated
- PROD mode sends quarterly: March, June, September, December

---

## Last Updated
June 23, 2026 — Full rewrite. Simplified to 5 questions. Role selection added as first step.
Removed all web app references. Confirmed Claude Code handles all AI natively.
