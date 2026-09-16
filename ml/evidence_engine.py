"""Scores support within supplied resume text; it never treats self-report as fact verification."""

import re

from skill_extractor import extract_skills

ACTION_WORDS = ("built", "developed", "implemented", "led", "designed", "deployed", "improved", "created", "managed", "reduced", "increased", "desarroll", "implement", "cré", "entwick")
OUTCOME_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|users|clients|days|months|years|ms|x)(?![a-z])", re.IGNORECASE)


def score_evidence(skill: str, resume_text: str) -> dict[str, object]:
    """Assess whether a claimed skill has contextual, action, or outcome support."""
    # Match canonical and translated aliases by reusing the skill normalizer on
    # each line (e.g. Spanish "aprendizaje automático" supports ML).
    snippets = [line.strip() for line in resume_text.splitlines() if skill in extract_skills(line)][:3]
    action_support = any(any(word in snippet.lower() for word in ACTION_WORDS) for snippet in snippets)
    outcome_support = any(OUTCOME_PATTERN.search(snippet) for snippet in snippets)
    score = 25 * bool(snippets) + 40 * action_support + 35 * outcome_support
    level = "strong" if score >= 75 else "moderate" if score >= 40 else "self-reported" if score else "none"
    return {
        "snippets": snippets,
        "support_score": score,
        "support_level": level,
        "requires_external_verification": bool(snippets),
        "verification_note": "Resume text is self-reported. Verify material claims with work samples, references, or credential checks.",
    }


def build_evidence_report(skills: list[str], resume_text: str) -> dict[str, object]:
    by_skill = {skill: score_evidence(skill, resume_text) for skill in skills}
    average = round(sum(item["support_score"] for item in by_skill.values()) / len(by_skill), 2) if by_skill else 0.0
    return {"by_skill": by_skill, "evidence_score": average, "verification_status": "unverified_self_report"}
