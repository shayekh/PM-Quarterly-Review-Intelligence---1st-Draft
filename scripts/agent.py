"""4-step agentic analysis: plans, acts, reasons, decides, self-checks — produces unified report data."""

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

AGREE, DISAGREE, COMPLEMENT, BLIND_SPOT = "AGREE", "DISAGREE", "COMPLEMENT", "BLIND_SPOT"

QUESTIONS = [
    ("executive_summary", "Executive Summary"),
    ("overall_status", "Overall Status"),
    ("key_achievements", "Key Achievements & Value Delivered"),
    ("risks_and_challenges", "Risks, Issues & Challenges"),
    ("quality_and_team_health", "Quality & Team Health"),
]

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "for", "with",
    "is", "was", "were", "are", "be", "been", "this", "that", "it", "we", "our",
    "as", "at", "by", "from", "had", "has", "have", "not", "no", "did", "do",
    "than", "then", "there", "their", "they", "them", "i", "us", "all", "some",
    "into", "out", "up", "down", "over", "also", "very", "quite", "just", "still",
    "due", "during", "will", "would", "could", "should", "what", "which", "who",
}

NEGATIVE_WORDS = {
    "delay", "delayed", "risk", "risks", "blocked", "issue", "issues", "behind",
    "failed", "failure", "concern", "concerns", "problem", "problems", "incident",
    "incidents", "slip", "slipped", "gap", "gaps", "challenge", "challenges",
    "bug", "bugs", "burnout", "attrition", "missed", "overdue", "regression",
    "outage", "escalation", "bottleneck",
}

POSITIVE_WORDS = {
    "ontrack", "good", "strong", "success", "successful", "smooth", "stable",
    "healthy", "achieved", "delivered", "exceeded", "improved", "improvement",
    "win", "wins", "great", "solid", "confident", "ahead", "completed", "shipped",
    "launched", "no-issues", "stable",
}


def header(title):
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


def significant_words(text):
    words = re.findall(r"[a-z']+", text.lower())
    return {w for w in words if len(w) > 2 and w not in STOPWORDS}


def jaccard(a, b):
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def count_keyword_hits(text, keyword_set):
    words = significant_words(text)
    return len(words & keyword_set)


def snippet(text, max_words=18):
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "..."


def find_latest_project():
    if not os.path.isdir(DATA_DIR):
        return None
    candidates = []
    for project in os.listdir(DATA_DIR):
        project_dir = os.path.join(DATA_DIR, project)
        pm_path = os.path.join(project_dir, "pm_answers.json")
        tl_path = os.path.join(project_dir, "tl_answers.json")
        if os.path.exists(pm_path) and os.path.exists(tl_path):
            candidates.append((os.path.getmtime(tl_path), project))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def load_submissions(project):
    project_dir = os.path.join(DATA_DIR, project)
    pm_path = os.path.join(project_dir, "pm_answers.json")
    tl_path = os.path.join(project_dir, "tl_answers.json")

    if not os.path.exists(pm_path) or not os.path.exists(tl_path):
        print(f"Error: missing submission(s) for '{project}'.")
        print(f"  pm_answers.json found: {os.path.exists(pm_path)}")
        print(f"  tl_answers.json found: {os.path.exists(tl_path)}")
        sys.exit(1)

    with open(pm_path, "r", encoding="utf-8") as f:
        pm = json.load(f)
    with open(tl_path, "r", encoding="utf-8") as f:
        tl = json.load(f)
    return pm, tl


def classify_relationship(key, pm_text, tl_text):
    if key == "overall_status":
        return AGREE if pm_text == tl_text else DISAGREE

    pm_words = significant_words(pm_text)
    tl_words = significant_words(tl_text)
    pm_wc = len(pm_text.split())
    tl_wc = len(tl_text.split())

    pm_tone = tone_of(pm_text)
    tl_tone = tone_of(tl_text)
    if pm_tone != "neutral" and tl_tone != "neutral" and pm_tone != tl_tone:
        return DISAGREE

    if min(pm_wc, tl_wc) <= 6 and max(pm_wc, tl_wc) >= 12:
        return BLIND_SPOT

    overlap = jaccard(pm_words, tl_words)
    if overlap >= 0.25:
        return AGREE
    return COMPLEMENT


def tone_of(text):
    neg = count_keyword_hits(text, NEGATIVE_WORDS)
    pos = count_keyword_hits(text, POSITIVE_WORDS)
    if neg > pos:
        return "negative"
    if pos > neg:
        return "positive"
    return "neutral"


def make_finding_sentence(label, relationship, pm_text, tl_text):
    if relationship == AGREE:
        return f"PM and Tech Lead both see {label.lower()} the same way — a confirmed, strong signal."
    if relationship == DISAGREE:
        return (
            f"PM and Tech Lead describe {label.lower()} very differently, "
            f"pointing to a misalignment that needs to be reconciled."
        )
    if relationship == COMPLEMENT:
        return (
            f"PM and Tech Lead bring different but complementary angles on {label.lower()}, "
            f"which together give a fuller picture."
        )
    pm_wc, tl_wc = len(pm_text.split()), len(tl_text.split())
    vague_side = "PM" if pm_wc < tl_wc else "Tech Lead"
    return (
        f"On {label.lower()}, {vague_side}'s answer was notably thinner than the other's — "
        f"a possible blind spot worth surfacing."
    )


def step1_section_analysis(pm, tl):
    print("🔍 Step 1: Analyzing each answer...")
    findings = []
    for key, label in QUESTIONS:
        pm_text = str(pm["answers"].get(key, "")).strip()
        tl_text = str(tl["answers"].get(key, "")).strip()
        relationship = classify_relationship(key, pm_text, tl_text)
        finding = make_finding_sentence(label, relationship, pm_text, tl_text)
        findings.append(
            {
                "question": key,
                "label": label,
                "pm_answer": pm_text,
                "tl_answer": tl_text,
                "relationship": relationship,
                "finding": finding,
            }
        )
    return findings


def step2_pattern_detection(findings):
    print("🧠 Step 2: Detecting patterns and themes...")

    word_freq = {}
    for f in findings:
        if f["question"] == "overall_status":
            continue
        for text in (f["pm_answer"], f["tl_answer"]):
            for word in significant_words(text):
                word_freq[word] = word_freq.get(word, 0) + 1
    recurring_words = sorted(
        (w for w, c in word_freq.items() if c >= 2), key=lambda w: -word_freq[w]
    )[:5]
    recurring_themes = [
        f"'{word}' comes up repeatedly across PM and Tech Lead answers" for word in recurring_words
    ]
    if not recurring_themes:
        recurring_themes = ["No single keyword dominates — answers cover varied, distinct ground."]

    critical_misalignments = [
        f"{f['label']}: {f['finding']}" for f in findings if f["relationship"] == DISAGREE
    ]
    strengths = [
        f"{f['label']}: {f['finding']}" for f in findings if f["relationship"] == AGREE
    ]
    risks = [
        f"{f['label']}: {f['finding']}"
        for f in findings
        if f["relationship"] in (DISAGREE, BLIND_SPOT)
        or tone_of(f["pm_answer"]) == "negative"
        or tone_of(f["tl_answer"]) == "negative"
    ]
    if not risks:
        risks = ["No significant shared risks were identified this quarter."]

    return {
        "recurring_themes": recurring_themes,
        "critical_misalignments": critical_misalignments or ["No critical misalignments found this quarter."],
        "strengths": strengths or ["No strong areas of full agreement were identified."],
        "risks": risks,
    }


def step3_report_writing(project, findings, patterns):
    print("✍️  Step 3: Writing analysis report...")

    lessons_learned = []
    next_quarter_focus = []
    management_attention = []

    for f in findings:
        if f["relationship"] == DISAGREE:
            lessons_learned.append(
                {
                    "lesson": f"PM and Tech Lead need a shared definition of '{f['label']}'.",
                    "context": (
                        f"PM said: \"{snippet(f['pm_answer'])}\" while Tech Lead said: "
                        f"\"{snippet(f['tl_answer'])}\" — the contradiction suggests misaligned visibility."
                    ),
                    "action": f"Hold a short alignment conversation on {f['label'].lower()} before next quarter starts.",
                    "_question": f["question"],
                }
            )
            management_attention.append(
                {
                    "item": f"Disagreement on {f['label']}",
                    "type": "Misalignment",
                    "explanation": (
                        f"PM and Tech Lead gave conflicting accounts of {f['label'].lower()}. "
                        f"PM: \"{snippet(f['pm_answer'])}\" | TL: \"{snippet(f['tl_answer'])}\"."
                    ),
                    "urgency": "High",
                    "source": "Disagreement",
                    "_question": f["question"],
                }
            )
            next_quarter_focus.append(
                {
                    "focus_area": f"Resolve misalignment on {f['label'].lower()}",
                    "expected_outcome": "PM and Tech Lead share one consistent view going into next quarter.",
                    "owner": "Both",
                }
            )
        elif f["relationship"] == BLIND_SPOT:
            vague_side = "PM" if len(f["pm_answer"].split()) < len(f["tl_answer"].split()) else "Tech Lead"
            lessons_learned.append(
                {
                    "lesson": f"{vague_side} had less visibility into {f['label'].lower()} than the other side.",
                    "context": f"One answer was substantially more detailed than the other on this question.",
                    "action": f"Encourage {vague_side} to dig deeper into {f['label'].lower()} next quarter.",
                    "_question": f["question"],
                }
            )
            next_quarter_focus.append(
                {
                    "focus_area": f"Close the visibility gap on {f['label'].lower()}",
                    "expected_outcome": f"{vague_side} can speak to this topic with the same depth as the other side.",
                    "owner": vague_side if vague_side == "PM" else "Tech Lead",
                }
            )
        elif f["relationship"] == COMPLEMENT:
            next_quarter_focus.append(
                {
                    "focus_area": f"Keep combining both views on {f['label'].lower()}",
                    "expected_outcome": "The richer, combined picture continues informing decisions.",
                    "owner": "Both",
                }
            )
        elif f["relationship"] == AGREE:
            lessons_learned.append(
                {
                    "lesson": f"{f['label']} is a confirmed strong point this quarter.",
                    "context": f"Both PM and Tech Lead independently described it the same way.",
                    "action": f"Keep doing whatever is driving alignment on {f['label'].lower()}.",
                    "_question": f["question"],
                }
            )

    if patterns["risks"] and patterns["risks"][0] != "No significant shared risks were identified this quarter.":
        management_attention.append(
            {
                "item": "Recurring risk themes flagged this quarter",
                "type": "Escalation",
                "explanation": "; ".join(patterns["risks"][:3]),
                "urgency": "Medium",
                "source": "Both",
                "_question": None,
            }
        )

    status_pm = next((f for f in findings if f["question"] == "overall_status"), None)
    if status_pm and status_pm["pm_answer"] in ("Red",) :
        management_attention.append(
            {
                "item": "Overall delivery status reported as Red",
                "type": "Escalation",
                "explanation": "Both PM and Tech Lead flagged significant issues requiring attention this quarter.",
                "urgency": "High",
                "source": "Both",
                "_question": "overall_status",
            }
        )
    elif status_pm and status_pm["pm_answer"] == "Amber":
        management_attention.append(
            {
                "item": "Overall delivery status reported as Amber",
                "type": "Decision",
                "explanation": "Some risk or delay was reported this quarter — manageable but worth monitoring.",
                "urgency": "Medium",
                "source": "Both",
                "_question": "overall_status",
            }
        )

    generic_lessons = [
        {
            "lesson": "Continue strengthening shared visibility between PM and Tech Lead.",
            "context": "Overall, this quarter's answers were broadly consistent in tone and substance.",
            "action": "Maintain regular sync points between PM and Tech Lead.",
            "_question": None,
        },
        {
            "lesson": "Keep the quarterly review cadence — it is surfacing useful signal.",
            "context": "Comparing independent PM and Tech Lead answers side by side revealed things neither would have flagged alone.",
            "action": "Continue running this review every quarter without skipping a cycle.",
            "_question": None,
        },
    ]
    for generic in generic_lessons:
        if len(lessons_learned) >= 3:
            break
        lessons_learned.append(generic)
    lessons_learned = lessons_learned[:5]

    while len(next_quarter_focus) < 3:
        next_quarter_focus.append(
            {
                "focus_area": "Maintain current delivery cadence",
                "expected_outcome": "Consistency carries into next quarter without regressions.",
                "owner": "Both",
            }
        )
    next_quarter_focus = next_quarter_focus[:5]

    if not management_attention:
        management_attention.append(
            {
                "item": "No items require management escalation this quarter",
                "type": "Decision",
                "explanation": "PM and Tech Lead answers were well aligned with no critical gaps.",
                "urgency": "Low",
                "source": "Both",
                "_question": None,
            }
        )
    management_attention = management_attention[:4]

    agree_count = sum(1 for f in findings if f["relationship"] == AGREE)
    disagree_count = sum(1 for f in findings if f["relationship"] == DISAGREE)
    blind_spot_count = sum(1 for f in findings if f["relationship"] == BLIND_SPOT)
    if status_pm and status_pm["relationship"] == AGREE:
        status_phrase = f"an overall status of {status_pm['pm_answer']}"
    elif status_pm:
        status_phrase = f"a disputed overall status (PM: {status_pm['pm_answer']}, Tech Lead: {status_pm['tl_answer']})"
    else:
        status_phrase = "an unknown overall status"

    closing_note = (
        f"This quarter for {project} closed with {status_phrase}, drawing on "
        f"independent input from both the Product Manager and the Tech Lead. Across the five review "
        f"areas, {agree_count} showed strong alignment between both perspectives"
        + (f", while {disagree_count} surfaced clear disagreements that need to be reconciled" if disagree_count else "")
        + (f" and {blind_spot_count} revealed a visibility gap between the two roles" if blind_spot_count else "")
        + ".\n\n"
        "Taken together, the PM and Tech Lead perspectives tell a single, coherent story of where delivery, "
        "technical health, and team wellbeing stood this quarter rather than two competing narratives. "
        "Where the two sides agreed, those points should be treated as dependable signal; where they diverged, "
        "that gap itself is the most useful finding of this review.\n\n"
        "Heading into next quarter, the priority is to close any open misalignments early, keep reinforcing "
        "what is already working, and ensure both PM and Tech Lead continue reporting with the same level of "
        "detail and visibility."
    )

    return lessons_learned, next_quarter_focus, management_attention, closing_note


def step4_self_check(findings, lessons_learned, next_quarter_focus, management_attention, closing_note):
    print("✅ Step 4: Checking analysis quality...")
    fixes = []

    disagree_keys = {f["question"] for f in findings if f["relationship"] == DISAGREE}
    covered_disagree = {
        m["_question"] for m in management_attention if m.get("source") == "Disagreement" and m.get("_question")
    }
    missing_disagree = disagree_keys - covered_disagree
    for key in missing_disagree:
        f = next(f for f in findings if f["question"] == key)
        management_attention.append(
            {
                "item": f"Disagreement on {f['label']}",
                "type": "Misalignment",
                "explanation": f["finding"],
                "urgency": "High",
                "source": "Disagreement",
                "_question": key,
            }
        )
        fixes.append(f"Added missing management_attention entry for disagreement on {f['label']}")

    blind_spot_keys = {f["question"] for f in findings if f["relationship"] == BLIND_SPOT}
    acknowledged = {l["_question"] for l in lessons_learned if l.get("_question")}
    acknowledged |= {m["_question"] for m in management_attention if m.get("_question")}
    missing_blind = blind_spot_keys - acknowledged
    for key in missing_blind:
        f = next(f for f in findings if f["question"] == key)
        lessons_learned.append(
            {
                "lesson": f"Blind spot acknowledged on {f['label']}.",
                "context": f["finding"],
                "action": f"Review {f['label'].lower()} together before next quarter's session.",
                "_question": key,
            }
        )
        fixes.append(f"Added missing lesson acknowledging blind spot on {f['label']}")

    if any(f["relationship"] == DISAGREE for f in findings) and "fully aligned" in closing_note.lower():
        closing_note = closing_note.replace("fully aligned", "broadly aligned")
        fixes.append("Softened closing_note language to avoid contradicting flagged disagreements")

    if fixes:
        for fix in fixes:
            print(f"   ↳ refined: {fix}")
    else:
        print("   ↳ all checks passed, no refinement needed.")

    return lessons_learned, next_quarter_focus, management_attention, closing_note


def strip_internal_fields(items):
    return [{k: v for k, v in item.items() if not k.startswith("_")} for item in items]


def main():
    project = sys.argv[1] if len(sys.argv) > 1 else find_latest_project()
    if not project:
        print("Error: no project specified and no project with both submissions was found.")
        sys.exit(1)

    pm, tl = load_submissions(project)

    quarter = pm.get("quarter", tl.get("quarter", "Q?"))
    year = pm.get("year", tl.get("year", "????"))

    print(f"🤖 Agent started for {project} — {quarter} {year}")
    print("📖 Reading PM and Tech Lead submissions...")

    findings = step1_section_analysis(pm, tl)
    patterns = step2_pattern_detection(findings)
    lessons_learned, next_quarter_focus, management_attention, closing_note = step3_report_writing(
        project, findings, patterns
    )
    lessons_learned, next_quarter_focus, management_attention, closing_note = step4_self_check(
        findings, lessons_learned, next_quarter_focus, management_attention, closing_note
    )

    analysis = {
        "project": project,
        "quarter": quarter,
        "year": year,
        "generated_at": datetime.now().isoformat(),
        "section_findings": [
            {k: v for k, v in f.items() if k in ("question", "pm_answer", "tl_answer", "relationship", "finding")}
            for f in findings
        ],
        "patterns": patterns,
        "lessons_learned": strip_internal_fields(lessons_learned),
        "next_quarter_focus": next_quarter_focus,
        "management_attention": strip_internal_fields(management_attention),
        "closing_note": closing_note,
    }

    project_dir = os.path.join(DATA_DIR, project)
    out_path = os.path.join(project_dir, "analysis.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2)

    print(f"📊 Analysis complete. Saved to data/{project}/analysis.json")
    print("🚀 Generating PDF report...")

    pdf_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generate_pdf.py")
    subprocess.run([sys.executable, pdf_script, project])


if __name__ == "__main__":
    main()
