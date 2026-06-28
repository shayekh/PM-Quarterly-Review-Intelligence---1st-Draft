"""4-step agentic analysis over PM (12Q) and TL (7Q) submissions.

Step 1: cross-analyse overlapping questions (delivery focus, status, achievements).
Step 2: detect patterns across all report sections, building section_synthesis (S1-S9).
Step 3: synthesise the AI-generated sections (S10-S14) from the extracted facts —
        these must be genuinely new analytical sentences, never a copy/paste of the
        PM or TL free-text answers.
Step 4: self-check — verify placeholders are filled, flag gaps.

Produces data/<session>/analysis.json matching the schema in CLAUDE.md.
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

AGREE, DISAGREE, COMPLEMENT, BLIND_SPOT = "AGREE", "DISAGREE", "COMPLEMENT", "BLIND_SPOT"

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
    "outage", "escalation", "bottleneck", "deferred", "rollback", "rollbacks",
    "under-resourced", "capacity", "stale",
}

POSITIVE_WORDS = {
    "ontrack", "good", "strong", "success", "successful", "smooth", "stable",
    "healthy", "achieved", "delivered", "exceeded", "improved", "improvement",
    "win", "wins", "great", "solid", "confident", "ahead", "completed", "shipped",
    "launched", "no-issues", "adequate",
}

STATUS_WORDS = {"green": "Green", "amber": "Amber", "red": "Red"}


def header(title):
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


# ---------------------------------------------------------------------------
# Generic text helpers
# ---------------------------------------------------------------------------

def strip_negated_phrases(text):
    """Removes 'no X' / 'not X' / 'non-X' so negated terms don't count as negative signal."""
    return re.sub(r"\b(?:no|not|non)[\s-]+\w+", "", text, flags=re.IGNORECASE)


def significant_words(text):
    words = re.findall(r"[a-z']+", text.lower())
    return {w for w in words if len(w) > 2 and w not in STOPWORDS}


def jaccard(a, b):
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def count_keyword_hits(text, keyword_set):
    words = significant_words(strip_negated_phrases(text))
    return len(words & keyword_set)


def snippet(text, max_words=18):
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "..."


def tone_of(text):
    neg = count_keyword_hits(text, NEGATIVE_WORDS)
    pos = count_keyword_hits(text, POSITIVE_WORDS)
    if neg > pos:
        return "negative"
    if pos > neg:
        return "positive"
    return "neutral"


def split_sentences(text):
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text.strip())
    return [p.strip() for p in parts if p.strip()]


def split_numbered(text):
    """Splits text like '1. Foo bar. 2. Baz qux.' into clean items."""
    if not text:
        return []
    parts = re.split(r"(?:^|\s)\d+\.\s+", text.strip())
    return [p.strip().rstrip(".") for p in parts if p.strip()]


def find_status_word(text, default="Green"):
    lowered = text.lower()
    for word, status in STATUS_WORDS.items():
        # Require a real word boundary, not a hyphenated compound like "blue-green".
        if re.search(rf"(?<![\w-]){word}(?![\w-])", lowered):
            return status
    neg = count_keyword_hits(text, NEGATIVE_WORDS)
    pos = count_keyword_hits(text, POSITIVE_WORDS)
    if neg >= 2 and neg > pos:
        return "Red"
    if neg >= 1 and neg >= pos:
        return "Amber"
    return default


def find_impact(text, default="Medium"):
    lowered = text.lower()
    if "high" in lowered:
        return "High"
    if "low" in lowered:
        return "Low"
    if "med" in lowered:
        return "Medium"
    return default


def first_match(pattern, text, group=1, flags=re.IGNORECASE):
    m = re.search(pattern, text, flags)
    return m.group(group).strip() if m else ""


def parse_number(raw):
    if not raw:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", raw)
    return float(m.group(1)) if m else None


def find_latest_session():
    if not os.path.isdir(DATA_DIR):
        return None
    candidates = []
    for session in os.listdir(DATA_DIR):
        session_dir = os.path.join(DATA_DIR, session)
        pm_path = os.path.join(session_dir, "pm_answers.json")
        tl_path = os.path.join(session_dir, "tl_answers.json")
        if os.path.exists(pm_path) and os.path.exists(tl_path):
            candidates.append((os.path.getmtime(tl_path), session))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def load_submissions(session):
    session_dir = os.path.join(DATA_DIR, session)
    pm_path = os.path.join(session_dir, "pm_answers.json")
    tl_path = os.path.join(session_dir, "tl_answers.json")

    if not os.path.exists(pm_path) or not os.path.exists(tl_path):
        print(f"Error: missing submission(s) for '{session}'.")
        print(f"  pm_answers.json found: {os.path.exists(pm_path)}")
        print(f"  tl_answers.json found: {os.path.exists(tl_path)}")
        return None, None

    with open(pm_path, "r", encoding="utf-8") as f:
        pm = json.load(f)
    with open(tl_path, "r", encoding="utf-8") as f:
        tl = json.load(f)

    # Defensive cleanup: a mangled console encoding can turn an em-dash into U+FFFD.
    for submission in (pm, tl):
        for key, val in submission.get("answers", {}).items():
            if isinstance(val, str):
                submission["answers"][key] = val.replace("�", "—")

    return pm, tl


def classify_relationship(is_status, pm_text, tl_text):
    if is_status:
        return AGREE if pm_text == tl_text else DISAGREE

    pm_words = significant_words(pm_text)
    tl_words = significant_words(tl_text)
    pm_wc, tl_wc = len(pm_text.split()), len(tl_text.split())

    pm_tone, tl_tone = tone_of(pm_text), tone_of(tl_text)
    if pm_tone != "neutral" and tl_tone != "neutral" and pm_tone != tl_tone:
        return DISAGREE

    if min(pm_wc, tl_wc) <= 6 and max(pm_wc, tl_wc) >= 12:
        return BLIND_SPOT

    if jaccard(pm_words, tl_words) >= 0.2:
        return AGREE
    return COMPLEMENT


# ---------------------------------------------------------------------------
# Step 1 — cross analysis on the three overlapping topics
# ---------------------------------------------------------------------------

CROSS_TOPICS = [
    ("delivery_focus", "pm_q1", "tl_q1", False),
    ("overall_status", "pm_q2", "tl_q2", True),
    ("achievements", "pm_q4", "tl_q3", False),
]


def step1_cross_analysis(pm, tl):
    print("🔍 Step 1: Cross-analysing overlapping PM/TL answers...")
    cross_analysis = []
    relationships = {}
    for topic, pm_key, tl_key, is_status in CROSS_TOPICS:
        pm_text = str(pm["answers"].get(pm_key, "")).strip()
        tl_text = str(tl["answers"].get(tl_key, "")).strip()
        relationship = classify_relationship(is_status, pm_text, tl_text)
        relationships[topic] = {"relationship": relationship, "pm": pm_text, "tl": tl_text}

        if relationship == AGREE:
            finding = f"PM and Tech Lead align on {topic.replace('_', ' ')} — a confirmed, strong signal."
        elif relationship == DISAGREE:
            finding = f"PM and Tech Lead describe {topic.replace('_', ' ')} differently — a misalignment to reconcile."
        elif relationship == COMPLEMENT:
            finding = f"PM and Tech Lead bring complementary angles on {topic.replace('_', ' ')}."
        else:
            finding = f"One side gave a much thinner answer on {topic.replace('_', ' ')} — a possible blind spot."

        cross_analysis.append({"topic": topic, "relationship": relationship, "finding": finding})
    return cross_analysis, relationships


# ---------------------------------------------------------------------------
# S2 — Service Overview
# ---------------------------------------------------------------------------

S2_FIELD_KEYWORDS = [
    ("active_services", ["active services"]),
    ("delivery_model", ["delivery model"]),
    ("key_stakeholders", ["stakeholder"]),
    ("team_composition", ["team composition", "team is composed", "composition includes"]),
    ("reporting_cadence", ["reporting cadence", "report cadence"]),
]


def parse_s2_service_overview(pm_q3):
    fields = {key: "" for key, _ in S2_FIELD_KEYWORDS}
    for sentence in split_sentences(pm_q3):
        lowered = sentence.lower()
        for key, keywords in S2_FIELD_KEYWORDS:
            if fields[key]:
                continue
            if any(kw in lowered for kw in keywords):
                fields[key] = sentence
                break
    for key in fields:
        if not fields[key]:
            fields[key] = "Not provided."
    return fields


# ---------------------------------------------------------------------------
# S3 — Key Achievements (merged + deduplicated)
# ---------------------------------------------------------------------------

def parse_achievement_item(item):
    for dash in (" — ", " - "):
        if dash in item:
            title, impact = item.split(dash, 1)
            return title.strip(), impact.strip()
    words = item.split()
    return " ".join(words[:8]), " ".join(words[8:]) or item


def merge_achievements(pm_q4, tl_q3):
    raw_items = [parse_achievement_item(i) for i in split_numbered(pm_q4)]
    raw_items += [parse_achievement_item(i) for i in split_numbered(tl_q3)]

    merged = []
    for title, impact in raw_items:
        title_words = significant_words(title)
        duplicate = None
        for existing in merged:
            if jaccard(title_words, significant_words(existing["achievement"])) >= 0.45:
                duplicate = existing
                break
        if duplicate:
            if impact and impact not in duplicate["impact"]:
                duplicate["impact"] = duplicate["impact"] or impact
        else:
            merged.append({"achievement": title, "impact": impact})
    return merged[:6]


# ---------------------------------------------------------------------------
# S4 — Delivery Summary
# ---------------------------------------------------------------------------

WORKSTREAM_PATTERN = re.compile(
    r"([A-Z][\w &/]+?):\s*(Green|Amber|Red)\s*[—-]\s*(.*?)(?=(?:[A-Z][\w &/]+?:\s*(?:Green|Amber|Red))|$)",
    re.DOTALL,
)


def parse_s4_delivery_summary(pm_q5):
    rows = []
    for match in WORKSTREAM_PATTERN.finditer(pm_q5 or ""):
        name, status, summary = match.groups()
        summary = summary.strip().rstrip(".")
        sentences = split_sentences(summary)
        notes = sentences[1] if len(sentences) > 1 else ""
        rows.append({
            "workstream": name.strip(),
            "status": status,
            "summary": sentences[0] if sentences else summary,
            "notes": notes,
        })
    if not rows and pm_q5:
        rows.append({
            "workstream": "Delivery",
            "status": find_status_word(pm_q5),
            "summary": snippet(pm_q5, 20),
            "notes": "",
        })
    return rows


# ---------------------------------------------------------------------------
# S5 — Service Performance Metrics
# ---------------------------------------------------------------------------

METRIC_DEFS = [
    ("SLA Compliance", ["sla compliance", "sla"], True, "%"),
    ("Ticket Resolution Rate", ["resolution rate"], True, "%"),
    ("Average Response Time", ["response time"], False, "hours"),
    ("Average Resolution Time", ["resolution time"], False, "hours"),
    ("Release Success Rate", ["release success"], True, "%"),
    ("Defect Leakage", ["defect leakage"], False, "%"),
    ("CSAT", ["csat", "customer satisfaction score"], True, ""),
]


def extract_target_actual(text, keywords):
    for sentence in split_sentences(text):
        lowered = sentence.lower()
        if any(kw in lowered for kw in keywords):
            target = first_match(r"target(?: is| of)?(?: below| above)?\s*([\d.]+\s*(?:%|/5\.0|hours?)?)", sentence)
            actual = first_match(r"actual(?: is)?\s*([\d.]+\s*(?:%|/5\.0|hours?)?)", sentence)
            if target or actual:
                return target, actual, sentence
    return "", "", ""


def compute_metric_status(target_raw, actual_raw, higher_is_better):
    target_val, actual_val = parse_number(target_raw), parse_number(actual_raw)
    if target_val is None or actual_val is None or target_val == 0:
        return "N/A"
    diff_pct = (actual_val - target_val) / target_val * 100
    if not higher_is_better:
        diff_pct = -diff_pct
    if diff_pct >= 0:
        return "Green"
    if diff_pct >= -5:
        return "Amber"
    return "Red"


def parse_s5_metrics(pm_q6, tl_q4, s6_support):
    combined = " ".join(filter(None, [pm_q6, tl_q4]))
    rows = []
    for name, keywords, higher_is_better, _unit in METRIC_DEFS:
        target, actual, sentence = extract_target_actual(combined, keywords)
        if not target and not actual and name == "Ticket Resolution Rate":
            counts = s6_support["ticket_counts"]
            total, resolved = parse_number(counts.get("total")), parse_number(counts.get("resolved"))
            if total and resolved is not None:
                actual = f"{round(resolved / total * 100, 1)}%"
                target = "90%"
                sentence = f"{resolved} of {int(total)} tickets resolved this quarter."
        status = compute_metric_status(target, actual, higher_is_better) if (target and actual) else "N/A"
        rows.append({
            "metric": name,
            "target": target or "N/A",
            "actual": actual or "N/A",
            "status": status,
            "comment": sentence or "Not reported this quarter.",
        })
    return rows


# ---------------------------------------------------------------------------
# S6 — Support & Incident Summary
# ---------------------------------------------------------------------------

TICKET_COUNT_PATTERNS = {
    "total": r"total tickets raised:?\s*(\d+)",
    "resolved": r"resolved:?\s*(\d+)",
    "open": r"open:?\s*(\d+)",
    "critical": r"critical incidents:?\s*(\d+)",
    "major": r"major incidents:?\s*(\d+)",
    "recurring": r"recurring issues:?\s*(\d+)",
}

MAJOR_INCIDENT_PATTERN = re.compile(
    r"Major incident \d+:\s*([^,]+),\s*(.*?),\s*impact was (.*?),\s*root cause was (.*?),\s*"
    r"action taken was (.*?),\s*current status (.*?)(?=(?:Major incident \d+:)|$)",
    re.IGNORECASE | re.DOTALL,
)


def parse_s6_support_summary(tl_q4):
    text = tl_q4 or ""
    ticket_counts = {}
    for key, pattern in TICKET_COUNT_PATTERNS.items():
        ticket_counts[key] = first_match(pattern, text) or "0"

    major_incidents = []
    for match in MAJOR_INCIDENT_PATTERN.finditer(text):
        date, issue, impact, root_cause, action, status = match.groups()
        major_incidents.append({
            "date": date.strip(),
            "issue": issue.strip().rstrip("."),
            "impact": impact.strip().rstrip("."),
            "root_cause": root_cause.strip().rstrip("."),
            "action": action.strip().rstrip("."),
            "status": status.strip().rstrip("."),
        })

    return {"ticket_counts": ticket_counts, "major_incidents": major_incidents}


# ---------------------------------------------------------------------------
# S7 — Quality & Delivery Health
# ---------------------------------------------------------------------------

QUALITY_AREAS = [
    ("Code Quality", ["code quality"]),
    ("QA", ["qa has", "qa is", "qa coverage", "test coverage", "quality assurance"]),
    ("Release Management", ["release management"]),
    ("Documentation", ["documentation"]),
    ("Communication", ["team communication", "communication is"]),
    ("Team Stability", ["team stability"]),
]

IMPROVEMENT_HINT_PATTERN = re.compile(
    r"(?:need to|should|allocate|plan to|going forward,?)\s+(.*?)(?:\.|$)", re.IGNORECASE
)


def infer_improvement_action(area, observation, status):
    hint = first_match(IMPROVEMENT_HINT_PATTERN.pattern, observation)
    if hint:
        return hint[0].upper() + hint[1:]
    if status == "Green":
        return f"Maintain current {area.lower()} practices into next quarter."
    return f"Define a corrective action plan for {area.lower()} ahead of next quarter."


def parse_s7_quality_health(tl_q5):
    rows = []
    text = tl_q5 or ""
    for area, keywords in QUALITY_AREAS:
        sentence = next(
            (s for s in split_sentences(text) if any(kw in s.lower() for kw in keywords)), None
        )
        observation = sentence or "Not provided this quarter."
        status = find_status_word(observation, default="Green")
        rows.append({
            "area": area,
            "observation": observation,
            "status": status,
            "improvement_action": infer_improvement_action(area, observation, status),
        })
    return rows


# ---------------------------------------------------------------------------
# S8 — Risks, Issues & Dependencies
# ---------------------------------------------------------------------------

RISK_ITEM_PATTERN = re.compile(
    r"(Risk|Issue|Dependency)\s*\d+:\s*(.*?)\s*[—-]\s*(High|Medium|Low) impact,\s*owner ([^,]+?),\s*"
    r"(?:mitigation is|next step is|action is)\s*(.*?)(?=(?:Risk|Issue|Dependency)\s*\d+:|$)",
    re.IGNORECASE | re.DOTALL,
)


def parse_s8_risks(tl_q6):
    rows = []
    text = tl_q6 or ""
    for match in RISK_ITEM_PATTERN.finditer(text):
        item_type, description, impact, owner, mitigation = match.groups()
        rows.append({
            "type": item_type.title(),
            "description": description.strip().rstrip("."),
            "impact": impact.title(),
            "owner": owner.strip().rstrip("."),
            "mitigation": mitigation.strip().rstrip("."),
        })
    if not rows and text:
        for item in split_sentences(text):
            lowered = item.lower()
            item_type = "Risk" if "risk" in lowered else ("Dependency" if "depend" in lowered else "Issue")
            rows.append({
                "type": item_type,
                "description": item,
                "impact": find_impact(item),
                "owner": first_match(r"owner ([^,.]+)", item) or "Unassigned",
                "mitigation": first_match(r"(?:mitigation|next step|action) (?:is )?(.*)", item),
            })
    return rows


# ---------------------------------------------------------------------------
# S9 — Customer Feedback & Relationship Health
# ---------------------------------------------------------------------------

S9_FIELD_KEYWORDS = [
    ("satisfaction", ["satisfaction is", "satisfaction has", "satisfaction was"]),
    ("communication", ["communication has", "communication is", "communication was"]),
    ("responsiveness", ["responsiveness"]),
    ("business_alignment", ["business alignment", "alignment is"]),
    ("areas_of_concern", ["concern", "concerns"]),
]


def parse_s9_customer_feedback(pm_q7, pm_q8):
    fields = {key: "" for key, _ in S9_FIELD_KEYWORDS}
    for sentence in split_sentences(pm_q7 or ""):
        lowered = sentence.lower()
        for key, keywords in S9_FIELD_KEYWORDS:
            if fields[key]:
                continue
            if any(kw in lowered for kw in keywords):
                fields[key] = sentence
                break
    for key in fields:
        if not fields[key]:
            fields[key] = "Not provided."
    fields["relationship_health"] = pm_q8 or "Green"
    return fields


# ---------------------------------------------------------------------------
# Step 2 — section synthesis (S1-S9)
# ---------------------------------------------------------------------------

def step2_section_synthesis(pm, tl, relationships):
    print("🧠 Step 2: Extracting and structuring section data (S1-S9)...")
    pm_a, tl_a = pm["answers"], tl["answers"]

    s3 = merge_achievements(pm_a.get("pm_q4", ""), tl_a.get("tl_q3", ""))
    s6 = parse_s6_support_summary(tl_a.get("tl_q4", ""))
    s8 = parse_s8_risks(tl_a.get("tl_q6", ""))

    status_rel = relationships["overall_status"]
    overall_status = status_rel["pm"] if status_rel["relationship"] == AGREE else status_rel["pm"]

    top_achievements = "; ".join(a["achievement"][0].lower() + a["achievement"][1:] for a in s3[:2]) or "no major highlights reported"
    attention_areas = "; ".join(r["description"][0].lower() + r["description"][1:] for r in s8[:2]) or "no significant concerns reported"
    next_preview = [s for s in split_sentences(tl_a.get("tl_q7", "")) if len(s.split()) > 4]
    next_preview_text = " ".join(next_preview[:2]) if next_preview else "no priorities reported yet"

    pm_focus_sentence = next(iter(split_sentences(pm_a.get("pm_q1", ""))), "")
    tl_focus_sentence = next(iter(split_sentences(tl_a.get("tl_q1", ""))), "")
    delivery_focus = pm_focus_sentence
    if tl_focus_sentence:
        delivery_focus += f" On the engineering side, {tl_focus_sentence[0].lower()}{tl_focus_sentence[1:]}"

    s1 = {
        "delivery_focus": delivery_focus.strip(),
        "overall_status": overall_status,
        "highlights": top_achievements,
        "areas_requiring_attention": attention_areas,
        "next_quarter_preview": next_preview_text,
    }

    s2 = parse_s2_service_overview(pm_a.get("pm_q3", ""))
    s4 = parse_s4_delivery_summary(pm_a.get("pm_q5", ""))
    s5 = parse_s5_metrics(pm_a.get("pm_q6", ""), tl_a.get("tl_q4", ""), s6)
    s7 = parse_s7_quality_health(tl_a.get("tl_q5", ""))
    s9 = parse_s9_customer_feedback(pm_a.get("pm_q7", ""), pm_a.get("pm_q8", ""))

    return {
        "s1_executive_summary": s1,
        "s2_service_overview": s2,
        "s3_achievements": s3,
        "s4_delivery_summary": s4,
        "s5_metrics": s5,
        "s6_support_summary": s6,
        "s7_quality_health": s7,
        "s8_risks": s8,
        "s9_customer_feedback": s9,
    }


# ---------------------------------------------------------------------------
# Step 3 — AI-generated sections (S10-S14), synthesised from extracted facts
# ---------------------------------------------------------------------------

def step3_ai_sections(pm, tl, cross_analysis, relationships, section_synthesis):
    print("✍️  Step 3: Synthesising AI sections (S10-S14) from extracted facts...")
    pm_a, tl_a = pm["answers"], tl["answers"]
    s = section_synthesis

    achievements = s["s3_achievements"]
    metrics = {m["metric"]: m for m in s["s5_metrics"]}
    incidents = s["s6_support_summary"]["major_incidents"]
    counts = s["s6_support_summary"]["ticket_counts"]
    risks = s["s8_risks"]
    amber_red_quality = [q for q in s["s7_quality_health"] if q["status"] != "Green"]

    # --- S10: Value Delivered — built from concrete numbers, never copied text ---
    business_bits = [a["achievement"] for a in achievements[:2]]
    csat = metrics.get("CSAT", {})
    s10 = {
        "business_value": (
            f"Delivery of {', '.join(business_bits) if business_bits else 'this quarter’s release set'} "
            f"translated into measurable customer-facing gains, against a backdrop of "
            f"{csat.get('actual', 'N/A')} CSAT versus a {csat.get('target', 'N/A')} target."
        ),
        "operational_value": (
            f"{counts.get('resolved', '0')} of {counts.get('total', '0')} support tickets were resolved with "
            f"{counts.get('critical', '0')} critical incidents, though {len(incidents)} major incident(s) this "
            f"quarter point to remaining gaps in release validation."
        ),
        "technical_value": (
            f"Engineering shipped {len(achievements)} notable technical achievements this quarter, while "
            f"{len(amber_red_quality)} of {len(s['s7_quality_health'])} quality dimensions still need attention "
            f"before the next release cycle."
        ),
        "strategic_value": (
            f"The current trajectory positions the team for its next milestone, contingent on resolving "
            f"{len(risks)} open risk/issue/dependency item(s) tracked this quarter."
        ),
    }

    # --- S11: Lessons Learned — from incidents, quality gaps, risks, disagreements ---
    lessons_learned = []
    for incident in incidents[:2]:
        lessons_learned.append({
            "lesson": f"Incident on {incident['date'] or 'an unspecified date'} exposed a gap in {incident['root_cause'] or 'pre-release validation'}.",
            "context": f"Impact: {incident['impact'] or 'service disruption'}. Resolved via: {incident['action'] or 'an emergency fix'}.",
            "action": "Add an automated pre-release check that would have caught this class of failure.",
        })
    for q in amber_red_quality[:2]:
        lessons_learned.append({
            "lesson": f"{q['area']} is trending {q['status']} and needs structural attention, not just a one-off fix.",
            "context": q["observation"],
            "action": q["improvement_action"],
        })
    high_risks = [r for r in risks if r["impact"] == "High"]
    for r in high_risks[:2]:
        lessons_learned.append({
            "lesson": f"Unresolved high-impact {r['type'].lower()} could affect delivery if not closed out.",
            "context": r["description"],
            "action": r["mitigation"] or f"Assign a clear owner and deadline for this {r['type'].lower()}.",
        })
    for entry in cross_analysis:
        if entry["relationship"] == DISAGREE:
            data = relationships[entry["topic"]]
            lessons_learned.append({
                "lesson": f"PM and Tech Lead read {entry['topic'].replace('_', ' ')} differently this quarter.",
                "context": f"PM: \"{snippet(data['pm'])}\" | TL: \"{snippet(data['tl'])}\"",
                "action": f"Align on {entry['topic'].replace('_', ' ')} before reporting next quarter.",
            })
    if not lessons_learned:
        lessons_learned.append({
            "lesson": "No significant gaps surfaced this quarter.",
            "context": "Incidents, quality checks, and risk tracking were all within acceptable bounds.",
            "action": "Maintain current operating cadence.",
        })
    lessons_learned = lessons_learned[:6]

    # --- S12: Next Quarter Focus — tl_q7 split into individual rows ---
    PM_OWNED_KEYWORDS = [
        "customer satisfaction", "stakeholder communication", "pricing", "contract",
        "business relationship", "business alignment", "account management",
    ]
    SHARED_OWNED_KEYWORDS = [
        "launch", "go-live", "go live", "production launch", "public launch",
        "customer", "stakeholder",
    ]

    def classify_focus_owner(text):
        lowered = text.lower()
        if any(kw in lowered for kw in PM_OWNED_KEYWORDS):
            return "Product Manager"
        if any(kw in lowered for kw in SHARED_OWNED_KEYWORDS):
            return "Product Manager, Tech Lead"
        return "Tech Lead"

    focus_sentences = split_sentences(tl_a.get("tl_q7", ""))
    LEAD_IN_PATTERN = re.compile(r"\bmust focus on\b|\bfocus(?:es)? on (?:the following|three|two|four|several)\b", re.IGNORECASE)
    next_quarter_focus = []
    for sentence in focus_sentences:
        cleaned = re.sub(r"^(First|Second|Third|Finally|Also),?\s*", "", sentence).strip()
        cleaned = re.sub(r"^We also need to\s*", "", cleaned, flags=re.IGNORECASE).strip()
        if LEAD_IN_PATTERN.search(cleaned):
            continue
        if len(cleaned.split()) < 3 or ("—" not in cleaned and "-" not in cleaned and len(cleaned.split()) < 6):
            continue
        outcome = "Closes out this priority ahead of next quarter's review."
        if "before go-live" in cleaned.lower() or "launch" in cleaned.lower():
            outcome = "De-risks the upcoming launch milestone."
        elif "tech debt" in cleaned.lower() or "documentation" in cleaned.lower():
            outcome = "Reduces accumulated technical debt and improves maintainability."
        elif "certification" in cleaned.lower() or "integration" in cleaned.lower():
            outcome = "Unblocks full feature/vendor coverage."
        next_quarter_focus.append({
            "focus_area": snippet(cleaned, 16),
            "expected_outcome": outcome,
            "owner": classify_focus_owner(cleaned),
        })
    if not next_quarter_focus:
        next_quarter_focus.append({
            "focus_area": "Maintain current delivery cadence",
            "expected_outcome": "Consistency carries into next quarter without regressions.",
            "owner": "Product Manager, Tech Lead",
        })
    next_quarter_focus = next_quarter_focus[:5]

    # --- S13: Management Attention — from S8 risks + S9 concerns + disagreements ---
    management_attention = []
    type_keyword_map = [
        ("Budget", ["budget", "cost", "spend"]),
        ("Resource", ["capacity", "engineer", "headcount", "hire", "staff"]),
        ("Approval", ["approval", "sign-off", "sign off"]),
        ("Decision", ["certification", "vendor", "documentation", "tech debt"]),
        ("Escalation", ["escalat", "provision", "production environment", "launch"]),
    ]

    def classify_type(text):
        lowered = text.lower()
        for type_name, keywords in type_keyword_map:
            if any(kw in lowered for kw in keywords):
                return type_name
        return "Escalation"

    for r in risks:
        if r["impact"] != "High":
            continue
        management_attention.append({
            "item": snippet(r["description"], 10),
            "type": classify_type(r["description"]),
            "explanation": f"{r['description']} (Owner: {r['owner']}). Mitigation: {r['mitigation'] or 'not yet defined'}.",
            "urgency": "High",
            "source": "Tech Lead",
        })

    concern_text = s["s9_customer_feedback"].get("areas_of_concern", "")
    if concern_text and concern_text != "Not provided.":
        management_attention.append({
            "item": "Customer-raised concern needs a response",
            "type": "Decision",
            "explanation": concern_text,
            "urgency": "Medium",
            "source": "Product Manager",
        })

    for entry in cross_analysis:
        if entry["relationship"] == DISAGREE:
            data = relationships[entry["topic"]]
            management_attention.append({
                "item": f"Disagreement on {entry['topic'].replace('_', ' ')}",
                "type": "Misalignment",
                "explanation": f"PM: \"{snippet(data['pm'])}\" | TL: \"{snippet(data['tl'])}\"",
                "urgency": "High",
                "source": "Disagreement",
            })

    pm_status, tl_status = pm_a.get("pm_q2"), tl_a.get("tl_q2")
    if pm_status == "Red" or tl_status == "Red":
        management_attention.append({
            "item": "Overall delivery status reported as Red",
            "type": "Escalation",
            "explanation": "Significant delivery issues were flagged this quarter requiring management attention.",
            "urgency": "High",
            "source": "Product Manager, Tech Lead" if pm_status == tl_status else "Disagreement",
        })

    if not management_attention:
        management_attention.append({
            "item": "No items require management escalation this quarter",
            "type": "Decision",
            "explanation": "PM and Tech Lead answers were well aligned with no critical gaps.",
            "urgency": "Low",
            "source": "Product Manager, Tech Lead",
        })
    management_attention = management_attention[:6]

    # --- S14: Closing note — references S12 focus areas by name ---
    focus_names = [snippet(f["focus_area"].rstrip("."), 8) for f in next_quarter_focus[:3]]
    agree_count = sum(1 for e in cross_analysis if e["relationship"] == AGREE)
    closing_note = (
        f"This quarter delivered against {len(achievements)} key achievements while surfacing "
        f"{len(incidents)} major incident(s) and {len(high_risks)} high-impact risk(s) that still need closing out. "
        f"PM and Tech Lead were aligned on {agree_count} of {len(cross_analysis)} reviewed topics.\n\n"
        f"Heading into next quarter, the priority is: {'; '.join(focus_names) if focus_names else 'maintaining current delivery cadence'}. "
        "Tracking these specific items at the next steering call will keep the team ahead of the risks identified this quarter."
    )

    return {
        "s10_value_delivered": s10,
        "s11_lessons_learned": lessons_learned,
        "s12_next_quarter_focus": next_quarter_focus,
        "s13_management_attention": management_attention,
        "s14_closing_note": closing_note,
    }


# ---------------------------------------------------------------------------
# Step 4 — self check
# ---------------------------------------------------------------------------

def step4_self_check(cross_analysis, section_synthesis, ai_generated):
    print("✅ Step 4: Checking analysis quality...")
    fixes = []

    disagree_topics = {e["topic"] for e in cross_analysis if e["relationship"] == DISAGREE}
    covered = {
        m["item"] for m in ai_generated["s13_management_attention"] if m.get("source") == "Disagreement"
    }
    for topic in disagree_topics:
        label = topic.replace("_", " ")
        if not any(label in item.lower() for item in covered):
            ai_generated["s13_management_attention"].append({
                "item": f"Disagreement on {label}",
                "type": "Misalignment",
                "explanation": f"PM and Tech Lead disagreed on {label}.",
                "urgency": "High",
                "source": "Disagreement",
            })
            fixes.append(f"Added missing management_attention entry for disagreement on {label}")

    if not section_synthesis["s5_metrics"]:
        section_synthesis["s5_metrics"].append({
            "metric": "Not provided", "target": "N/A", "actual": "N/A", "status": "N/A", "comment": "No metrics data found."
        })
        fixes.append("Filled missing s5_metrics with placeholder")

    if not section_synthesis["s8_risks"]:
        section_synthesis["s8_risks"].append({
            "type": "Risk", "description": "No risks reported this quarter.",
            "impact": "Low", "owner": "—", "mitigation": "",
        })
        fixes.append("Filled missing s8_risks with placeholder")

    for row in section_synthesis["s7_quality_health"]:
        if not row.get("improvement_action"):
            row["improvement_action"] = f"Define a corrective action plan for {row['area'].lower()} ahead of next quarter."
            fixes.append(f"Filled missing improvement_action for {row['area']}")

    for row in section_synthesis["s8_risks"]:
        if not row.get("owner") or row["owner"].lower() == "unassigned":
            fixes.append(f"Owner not explicitly named for risk: {snippet(row['description'], 8)}")

    if fixes:
        for fix in fixes:
            print(f"   ↳ refined: {fix}")
    else:
        print("   ↳ all checks passed, no refinement needed.")

    return section_synthesis, ai_generated


def run_agent(session, auto_chain=True):
    """Runs the 4-step analysis for `session`. Returns True on success, False on failure."""
    pm, tl = load_submissions(session)
    if pm is None or tl is None:
        return False

    customer_name = pm.get("customer_name", session)
    reporting_period = pm.get("reporting_period", "")

    print(f"🤖 Agent started for {customer_name} — {reporting_period}")
    print("📖 Reading PM and Tech Lead submissions...")

    cross_analysis, relationships = step1_cross_analysis(pm, tl)
    section_synthesis = step2_section_synthesis(pm, tl, relationships)
    ai_generated = step3_ai_sections(pm, tl, cross_analysis, relationships, section_synthesis)
    section_synthesis, ai_generated = step4_self_check(cross_analysis, section_synthesis, ai_generated)

    pm_status = pm["answers"].get("pm_q2", "Green")
    tl_status = tl["answers"].get("tl_q2", "Green")

    analysis = {
        "report_meta": {
            "customer_name": customer_name,
            "reporting_period": reporting_period,
            "prepared_by": pm.get("prepared_by", ""),
            "date_generated": datetime.now().strftime("%Y-%m-%d"),
            "pm_status": pm_status,
            "tl_status": tl_status,
            "status_aligned": pm_status == tl_status,
        },
        "section_synthesis": section_synthesis,
        "ai_generated": ai_generated,
        "cross_analysis": cross_analysis,
    }

    session_dir = os.path.join(DATA_DIR, session)
    out_path = os.path.join(session_dir, "analysis.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2)

    print(f"📊 Analysis complete. Saved to data/{session}/analysis.json")

    if auto_chain:
        print("🚀 Generating PDF report...")
        pdf_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generate_pdf.py")
        subprocess.run([sys.executable, pdf_script, session])

    return True


def main():
    session = sys.argv[1] if len(sys.argv) > 1 else find_latest_session()
    if not session:
        print("Error: no session specified and no session with both submissions was found.")
        sys.exit(1)

    success = run_agent(session)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
