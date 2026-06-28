# PM Review Intelligence — CLAUDE.md (Terminal Version)

> Persistent memory for this project.
> Read this before doing anything. Update when plan evolves.

---

## What Was Built

A fully working **terminal-based agentic AI workflow** running inside Claude Code.
No web app. No database. No separate Anthropic API key needed.
Claude itself is the agent — reasons across PM and TL answers,
generates a 14-section Quarterly Service Delivery Report as PDF,
and emails it to stakeholders via Resend.

**Status: ✅ Phase 1–7 complete. Phase 8 (redesign) in progress — PDF fixes applied.**

---

## How To Run

```bash
# Navigate to project
cd "C:\Users\DELL\OneDrive\Desktop\pm-q-session-oc"

# RECOMMENDED — Full automatic workflow
python scripts/run.py

# Manual individual steps
python scripts/questionnaire.py       # PM or TL turn
python scripts/agent.py S7000         # Analysis only
python scripts/generate_pdf.py S7000  # PDF only
python scripts/scheduler.py S7000     # Email only
```

---

## run.py Menu Options

```
1. Full automatic workflow (PM + TL + Analysis + PDF + Email)
2. PM turn only
3. TL turn only
4. Run analysis only
5. Generate PDF only
6. Send email only
```

---

## Question Set — REDESIGNED (Phase 8)

PM and TL now have **different question sets**.
PM covers customer-facing sections. TL covers technical sections only.
Role selection happens first, then customer/project name, then questions.

---

### PM Questions (12 total)

#### Setup (asked first, every session)

| Key | Question | Input Type |
|-----|----------|------------|
| role | "What is your role?" → 1. Product Manager / 2. Tech Lead | Choice |
| customer_name | "What is the customer / project name?" | Free text |
| reporting_period | "What is the reporting period?" → Q1 2026 / Q2 2026 / Q3 2026 / Q4 2026 | Choice |
| prepared_by | "Prepared by — enter your name and role (e.g. John Smith, Delivery Manager)" | Free text |
| recipient_emails | "Who should receive this report? Enter stakeholder emails (comma-separated)" | Email list |

#### Delivery & Overview → fills S1, S2

| Key | Question | Input Type |
|-----|----------|------------|
| pm_q1 | "What was the overall delivery focus and key activities this quarter?" | Free text |
| pm_q2 | "What is the overall service delivery status? 🟢 Green / 🟡 Amber / 🔴 Red" | Choice |
| pm_q3 | "Describe the active services, delivery model, team composition, and reporting cadence." | Free text |

#### Achievements & Delivery → fills S3, S4

| Key | Question | Input Type |
|-----|----------|------------|
| pm_q4 | "What were the key achievements this quarter and what business value did they deliver?" | Free text |
| pm_q5 | "Summarise each active workstream or project — its status (Green/Amber/Red), progress, and key notes." | Free text |

#### Metrics & Customer → fills S5, S9

| Key | Question | Input Type |
|-----|----------|------------|
| pm_q6 | "What were the key service metrics this quarter? Cover CSAT score, SLA compliance %, and release success rate — include target vs actual for each." | Free text |
| pm_q7 | "How was the customer relationship this quarter? Cover satisfaction, communication, responsiveness, business alignment, and any areas of concern." | Free text |
| pm_q8 | "Overall relationship health? 🟢 Green / 🟡 Amber / 🔴 Red" | Choice |

---

### TL Questions (7 total)

#### Setup (asked first, every session)

| Key | Question | Input Type |
|-----|----------|------------|
| role | "What is your role?" → 1. Product Manager / 2. Tech Lead | Choice |
| customer_name | "What is the customer / project name?" → must match PM session | Free text |
| reporting_period | "What is the reporting period?" → must match PM session | Choice |

#### Delivery & Achievements → fills S1, S3, S4

| Key | Question | Input Type |
|-----|----------|------------|
| tl_q1 | "From a technical standpoint, what was the delivery focus and key engineering activities this quarter?" | Free text |
| tl_q2 | "What is your assessment of the overall delivery status? 🟢 Green / 🟡 Amber / 🔴 Red" | Choice |
| tl_q3 | "What were the key technical achievements? Include releases, performance improvements, security work, or architecture changes." | Free text |

#### Incidents & Quality → fills S5, S6, S7

| Key | Question | Input Type |
|-----|----------|------------|
| tl_q4 | "What were the support and incident numbers this quarter? Cover total tickets, resolved, open, critical and major incidents. For any major incident include: date, issue, root cause, action taken, and current status." | Free text |
| tl_q5 | "How was overall quality and delivery health? Cover code quality, QA, release management, documentation, team communication, and team stability." | Free text |

#### Risks & Next Quarter → fills S8, S12

| Key | Question | Input Type |
|-----|----------|------------|
| tl_q6 | "What risks, issues, or dependencies exist? For each, describe the type, impact level (High/Med/Low), owner, and mitigation or next step." | Free text |
| tl_q7 | "What should be the technical focus for next quarter? Include any blockers, tech debt, or priorities the team must address." | Free text |

---

## Agentic Workflow

```
PM TURN
→ Selects role: Product Manager
→ Enters customer name, reporting period, prepared by, recipient emails
→ Answers pm_q1 through pm_q8
→ Saved: data/CustomerName_Q2_2026/pm_answers.json ✅

TL TURN
→ Selects role: Tech Lead
→ Enters same customer name + reporting period → auto-linked to PM session
→ Answers tl_q1 through tl_q7
→ Saved: data/CustomerName_Q2_2026/tl_answers.json ✅

AGENT (triggers automatically when both JSON files exist)
→ Step 1: Cross-analyse overlapping questions (delivery focus, status, achievements)
          AGREE / DISAGREE / COMPLEMENT / BLIND_SPOT
→ Step 2: Detect patterns across all 14 report sections
→ Step 3: Generate S10–S14 (value, lessons, next quarter, management attention, closing)
→ Step 4: Self-check — verify all placeholders are filled, flag gaps
→ Saved: data/CustomerName_Q2_2026/analysis.json ✅

PDF GENERATION (triggers automatically after agent)
→ 14-section Quarterly Service Delivery Report
→ Saved: output/CustomerName_Q2_2026.pdf ✅

EMAIL SCHEDULER (triggers automatically after PDF)
→ SCHEDULE_MODE=monthly  → sends last working day of each month (default)
→ SCHEDULE_MODE=quarterly → sends March / June / September / December
→ TEST_MODE=True          → sends immediately regardless of schedule
→ Reads recipient emails from pm_answers.json
→ Sends PDF to all stakeholders via Resend ✅
```

---

## Report → Question Mapping

Every `[placeholder]` in the report template is filled by a specific question or AI synthesis.

| Report Section | Filled By | Source |
|----------------|-----------|--------|
| Cover: Customer Name | customer_name | PM setup |
| Cover: Reporting Period | reporting_period | PM setup |
| Cover: Prepared By | prepared_by | PM setup |
| Cover: Date | system date | Auto |
| S1: Delivery focus + workstreams | pm_q1 + tl_q1 | PM + TL |
| S1: Overall status badge | pm_q2 vs tl_q2 | PM + TL (disagreement flagged) |
| S1: Highlights + risks | pm_q1 + tl_q1 | PM + TL |
| S1: Next quarter priorities | AI synthesis | Agent (S12 → S1) |
| S2: Service overview table | pm_q3 | PM |
| S3: Key achievements | pm_q4 + tl_q3 | PM + TL |
| S4: Delivery summary table | pm_q5 + tl_q1 | PM + TL |
| S5: Metrics table | pm_q6 + tl_q4 | PM + TL |
| S6: Support & incident table | tl_q4 | TL |
| S7: Quality health table | tl_q5 | TL |
| S8: Risks, issues, dependencies | tl_q6 | TL |
| S9: Customer feedback table | pm_q7 | PM |
| S9: Relationship health status | pm_q8 | PM |
| S10: Value delivered | AI synthesis | Agent (S1–S9) |
| S11: Lessons learned | AI synthesis | Agent (S6, S7, S8 + disagreements) |
| S12: Next quarter focus table | AI synthesis | Agent (pm_q1 + tl_q7) |
| S13: Management attention | AI synthesis | Agent (S8, S9 + disagreements) |
| S14: Closing note | AI synthesis | Agent (S12) |

---

## AI Reasoning Rules

The agent compares answers where both PM and TL cover the same topic
(delivery focus, overall status, achievements).

| Relationship | What AI Does |
|---|---|
| Both agree | Reinforce as strong confirmed signal |
| They disagree | Flag explicitly in S13 Management Attention (source: Disagreement) |
| They complement | Merge into one richer, unified insight |
| One sees risk, other doesn't | Surface as blind spot in S11 Lessons Learned |
| One answered, other didn't | Note the gap — do not ignore or fabricate |

**Status disagreement rule:** If pm_q2 ≠ tl_q2 (e.g. PM says Green, TL says Amber),
this is always escalated to S13 Management Attention as a priority misalignment item.

---

## AI Output (analysis.json) — Updated Schema

```json
{
  "report_meta": {
    "customer_name": "...",
    "reporting_period": "Q2 2026",
    "prepared_by": "...",
    "date_generated": "YYYY-MM-DD",
    "pm_status": "Green|Amber|Red",
    "tl_status": "Green|Amber|Red",
    "status_aligned": true
  },
  "section_synthesis": {
    "s1_executive_summary": {
      "delivery_focus": "...",
      "overall_status": "Green|Amber|Red",
      "highlights": "...",
      "areas_requiring_attention": "...",
      "next_quarter_preview": "..."
    },
    "s3_achievements": [
      { "achievement": "...", "impact": "..." }
    ],
    "s4_delivery_summary": [
      { "workstream": "...", "status": "Green|Amber|Red", "summary": "...", "notes": "..." }
    ],
    "s5_metrics": [
      { "metric": "...", "target": "...", "actual": "...", "status": "Green|Amber|Red", "comment": "..." }
    ],
    "s6_support_summary": {
      "ticket_counts": {
        "total": "...", "resolved": "...", "open": "...",
        "critical": "...", "major": "...", "recurring": "..."
      },
      "major_incidents": [
        { "date": "...", "issue": "...", "impact": "...", "root_cause": "...", "action": "...", "status": "..." }
      ]
    },
    "s7_quality_health": [
      { "area": "Code Quality|QA|Release Management|Documentation|Communication|Team Stability",
        "observation": "...", "status": "Green|Amber|Red", "improvement_action": "..." }
    ],
    "s8_risks": [
      { "type": "Risk|Issue|Dependency", "description": "...",
        "impact": "High|Medium|Low", "owner": "...", "mitigation": "..." }
    ],
    "s9_customer_feedback": {
      "satisfaction": "...", "communication": "...", "responsiveness": "...",
      "business_alignment": "...", "areas_of_concern": "...",
      "relationship_health": "Green|Amber|Red"
    }
  },
  "ai_generated": {
    "s10_value_delivered": {
      "business_value": "...",
      "operational_value": "...",
      "technical_value": "...",
      "strategic_value": "..."
    },
    "s11_lessons_learned": [
      { "lesson": "...", "context": "...", "action": "..." }
    ],
    "s12_next_quarter_focus": [
      { "focus_area": "...", "expected_outcome": "...", "owner": "Product Manager|Tech Lead|Product Manager, Tech Lead" }
    ],
    "s13_management_attention": [
      {
        "item": "...",
        "type": "Decision|Approval|Budget|Resource|Escalation|Misalignment",
        "explanation": "...",
        "urgency": "High|Medium|Low",
        "source": "Product Manager|Tech Lead|Product Manager, Tech Lead|Disagreement"
      }
    ],
    "s14_closing_note": "..."
  },
  "cross_analysis": [
    {
      "topic": "delivery_focus|overall_status|achievements",
      "relationship": "AGREE|DISAGREE|COMPLEMENT|BLIND_SPOT",
      "finding": "one sentence summary"
    }
  ]
}
```

---

## PDF Report Structure — Updated

```
COVER PAGE
→ Full page background image: assets/cover_bg.jpg
→ SELISE logo: top right corner (assets/selise_logo.png), 120x50px
   SELISE logo appears on cover page ONLY — not on any other page
→ Dark semi-transparent navy banner covering bottom 25% of page
→ Inside banner — left side:
   - Vertical white bar (4px)
   - Large white bold: "[Customer Name] — Quarterly Service Delivery Report" (one line)
   - Medium white: "[Reporting Period]" e.g. Q2 2026
   - Small white: "[Date]" e.g. 28 June, 2026
→ Inside banner — right side:
   - Customer logo in white rounded rectangle box (assets/customer_logo.png)
   - If assets/customer_logo.png does not exist → hide box entirely
→ No footer on cover page

S1  Executive Summary
    → 4 prose paragraphs — no subheadings inside S1:
    "During this quarter, the delivery team focused on [...]. Key activities included [...]."
    "Overall service delivery status for the quarter is [badge]." — inline badge same line
    "The quarter was marked by [...], while the main areas requiring attention were [...]."
    "The focus for the next quarter will be [...]."

S2  Service Overview
    → Two-column table (Area | Summary) with exactly 5 rows:
    Active Services | Delivery Model | Key Stakeholders |
    Team Composition | Reporting Cadence

S3  Key Achievements
    → Numbered list, deduplicated from PM + TL answers
    → Each item: bold achievement title + impact explanation on next line
    → No double numbering

S4  Delivery Summary
    → 4-column table: Workstream | Status | Progress Summary | Notes
    → First column header: "Workstream" only (not "Workstream/Project")
    → Workstream column wide enough — names never wrap to second line
    → Status column: coloured badge (Green/Amber/Red)
    → Below table: static Delivery Status Legend sub-table
       Status | Meaning
       Green  | On track, no major concern
       Amber  | Some risk or delay, manageable
       Red    | Significant issue requiring attention

S5  Service Performance Metrics
    → 5-column table: Metric | Target | Actual | Status | Comment
    → All 7 metrics rendered: SLA Compliance, Ticket Resolution Rate,
      Average Response Time, Average Resolution Time, Release Success Rate,
      Defect Leakage, Customer Satisfaction/CSAT
    → Status auto-computed: >= target → Green, within 5% below → Amber, >5% below → Red

S6  Support & Incident Summary
    → Table 1 (3 cols): Category | Count | Summary — 6 rows:
      Total Raised | Resolved | Open | Critical Incidents | Major Incidents | Recurring Issues
    → Bold subheading: "Major Incidents / Escalations"
    → Table 2 (6 cols): Date | Issue | Impact | Root Cause | Action Taken | Current Status

S7  Quality & Delivery Health
    → 4-column table: Area | Observation | Status | Improvement Action
    → Area column minimum 15% page width — no word wrapping in area names
    → All 6 areas: Code Quality | QA | Release Management |
      Documentation | Communication | Team Stability
    → Improvement Action column always populated

S8  Risks, Issues & Dependencies
    → 5-column table: Type | Description | Impact | Owner | Mitigation/Next Step
    → Owner extracted from text — never "Unassigned" if text names an owner
    → Type: Risk | Issue | Dependency

S9  Customer Feedback & Relationship Health
    → Two-column table (Area | Feedback/Observation) with 5 rows:
      Customer Satisfaction | Communication | Responsiveness |
      Business Alignment | Areas of Concern
    → "Overall relationship health:" label + coloured badge on same line (inline)

── AI GENERATED SECTIONS ─────────────────────────────────────────

S10 Value Delivered
    → 4 paragraphs: Business Value | Operational Value | Technical Value | Strategic Value
    → AI synthesises original insights — does not copy-paste input text

S11 Lessons Learned
    → Numbered list: genuine lessons from incidents, quality gaps, risks, disagreements
    → Not generic statements

S12 Next Quarter Focus
    → Table: Focus Area | Expected Outcome | Owner
    → Owner rules:
      PM responsibility only → "Product Manager"
      TL responsibility only → "Tech Lead"
      Shared → "Product Manager, Tech Lead"
      Never use "Both"

S13 Management Attention Required
    → Cards: High / Medium / Low urgency with type badge
    → Source rules:
      From PM only → "Product Manager"
      From TL only → "Tech Lead"
      Raised by both → "Product Manager, Tech Lead"
      Due to disagreement → "Disagreement"
      Never use "Both"

S14 Closing Note
    → Grey box, professional tone
    → References specific next quarter priorities from S12

FOOTER (all pages except cover): [Customer Name] — [Reporting Period] | Page X | Generated by PM Review Intelligence
```

**Status badges** render as coloured inline pills throughout: 🟢 Green / 🟡 Amber / 🔴 Red
**S1 status** shows both PM and TL ratings side by side if they disagree.
**Date format** throughout the report: DD Month, YYYY (e.g. 28 June, 2026)

**Global table rules:**
- All tables span full page width — edges flush with page margins
- Header style: dark navy (#1B3A5C), white bold text, centred
- Alternating row shading
- Label/category columns (first column) never wrap — fixed minimum width
- Only content/description columns may wrap across multiple lines

---

## Folder Structure

```
pm-q-session-oc/
├── CLAUDE.md
├── README.md
├── .env
├── assets/
│   ├── cover_bg.jpg          # Mountain background for cover page
│   ├── selise_logo.png       # SELISE logo — top right of cover page
│   └── customer_logo.png     # Customer logo — bottom right of cover page (optional)
├── data/
│   └── CustomerName_Q2_2026/
│       ├── pm_answers.json
│       ├── tl_answers.json
│       ├── analysis.json
│       └── email_log.json
├── output/
│   └── CustomerName_Q2_2026.pdf
└── scripts/
    ├── run.py             ✅ Master orchestrator (6 menu options)
    ├── questionnaire.py   🔄 Role-split question sets (Phase 8)
    ├── agent.py           🔄 Updated analysis + new schema (Phase 8)
    ├── generate_pdf.py    🔄 14-section report (Phase 8)
    └── scheduler.py       🔄 Monthly + quarterly modes (Phase 8)
```

---

## Environment Variables (.env)

```
RESEND_API_KEY=your_resend_api_key
SENDER_EMAIL=reviews@yourdomain.com

# TEST_MODE: True = skip schedule date check, run now
#            False = only run on scheduled date (month end or quarterly)
TEST_MODE=True

# SCHEDULE_MODE: monthly = last working day of month | quarterly = Mar/Jun/Sep/Dec
SCHEDULE_MODE=monthly

# SEND_EMAIL: True = send email to stakeholders
#             False = skip email, save PDF to output/ folder only
SEND_EMAIL=False
```

| Variable | Values | Default | Purpose |
|----------|--------|---------|---------|
| TEST_MODE | True / False | True | Skip schedule check and run immediately |
| SCHEDULE_MODE | monthly / quarterly | monthly | When to send in production |
| SEND_EMAIL | True / False | False | Whether to actually send email |

**Typical usage:**

| Scenario | TEST_MODE | SEND_EMAIL | Result |
|----------|-----------|------------|--------|
| Claude Code testing | True | False | PDF saved, no email |
| You testing on terminal | True | True | PDF saved, email sends now |
| Real monthly production | False | True | PDF saved, email sends on month end |
| Dry run on terminal | False | False | PDF saved, no email, waits for schedule |

No Anthropic API key needed.
Claude Code Pro subscription handles all AI reasoning.
Resend requires verified domain to send to any email address.

---

## Key Rules & Decisions

- Claude Code (Pro) is the AI — no separate API key needed
- PM and TL answer independently — neither sees other's answers until analysis
- TL cannot start until PM has submitted for that customer + period
- Customer name + reporting period together form the session key (folder name)
- Agent triggers automatically when both pm_answers.json and tl_answers.json exist
- Same customer + same period = overwrite (no versioning)
- Only PM provides stakeholder emails and prepared_by field
- Status disagreement between PM and TL always escalates to S13 Management Attention
- All free-text table answers (workstreams, incidents, risks, metrics) described
  in natural language — agent parses and formats into structured tables
- Legacy projects (old 6-question format) → gracefully default missing fields to empty string
- All 5 scripts remain independently runnable as standalone CLI tools
- run.py orchestrates everything but does not modify individual scripts
- SEND_EMAIL=False during all Claude Code testing — only set True when running on terminal
- Date format throughout the report: DD Month, YYYY (e.g. 28 June, 2026)
- Owner field in S12: "Product Manager", "Tech Lead", or "Product Manager, Tech Lead" — never "Both"
- Source field in S13: "Product Manager", "Tech Lead", "Product Manager, Tech Lead", or "Disagreement" — never "Both"
- assets/cover_bg.jpg and assets/selise_logo.png must exist in project root for cover page
- assets/customer_logo.png is optional — if missing, logo box is hidden on cover page

---

## Build Phases

| Phase | What Was Built | Status |
|-------|----------------|--------|
| 1 | Project scaffold + folder structure + .env | ✅ Complete |
| 2 | Questionnaire — role + 6 questions + JSON save | ✅ Complete |
| 3 | Agent — 4-step agentic reasoning | ✅ Complete |
| 4 | PDF generation — side by side + AI sections | ✅ Complete |
| 5 | Email scheduler — Resend + TEST_MODE | ✅ Complete |
| 6 | run.py master orchestrator — 6 menu options | ✅ Complete |
| 7 | Q6 Customer Satisfaction added + backward compatible | ✅ Complete |
| 8 | Full redesign: role-split questions, 14-section report, cover page, scheduler | 🔄 In progress |

### Phase 8 Checklist

- [ ] `questionnaire.py` — split PM (12Q) and TL (7Q) flows, new JSON schema
- [ ] `agent.py` — updated 4-step reasoning, new analysis.json schema, AI synthesis prompts
- [ ] `generate_pdf.py` — 14-section report, cover page redesign, all table fixes
- [ ] `scheduler.py` — SCHEDULE_MODE + TEST_MODE + SEND_EMAIL logic
- [ ] `assets/` — cover_bg.jpg and selise_logo.png committed to project
- [ ] End-to-end test on new project — all 14 sections verified

---

## Tested & Verified (pre-Phase 8)

- ✅ Full end-to-end run on project S7000
- ✅ PDF generated and received via email
- ✅ Q6 renders correctly in PDF and analysis.json
- ✅ Legacy projects without Q6 don't break
- ✅ All 5 scripts work standalone and via run.py
- ✅ Resend domain verified — can send to any email

---

## Next Phase

SaaS web app version is being built in a separate Claude Project.
See: PM Review Intelligence — SaaS (separate project)
Phase 8 terminal redesign must be completed and tested before
SaaS build begins — the terminal version is the source of truth.

---

## Last Updated
June 28, 2026 — Phase 8 in progress.
Role-split question sets (PM: 12Q, TL: 7Q), 14-section report template,
cover page redesign (background image, SELISE logo, dark banner, customer logo),
all table fixes (S2–S9), AI synthesis fixes (S10–S14), owner/source label rules,
SEND_EMAIL variable added, date format standardised to DD Month YYYY.