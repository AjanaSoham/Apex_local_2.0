"""Candidate-to-job matching orchestration and explainable output."""

from typing import Any
import unicodedata

from embedding_service import active_model_name
from evidence_engine import build_evidence_report
from jd_skill_extractor import extract_jd_skills
from match_model import predict_score
from matcher import calculate_semantic_similarity, calculate_skill_match
from skill_extractor import extract_skills


def _clean_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).replace("\x00", "")
    return "\n".join(line.strip() for line in normalized.splitlines() if line.strip())


def _recommendation(score: float, missing: list[str]) -> str:
    if score >= 75:
        return "Strong match — recommend advancing to a structured interview."
    if score >= 50:
        return "Potential match — review the missing requirements in a screening call."
    if missing:
        return "Low match — consider only if the missing core skills are trainable for this role."
    return "Low match — resume evidence is limited for this job description."


def _interview_questions(matched: list[str], missing: list[str]) -> list[dict[str, str]]:
    questions = []
    for skill in missing[:3]:
        questions.append({"focus": skill, "question": f"What practical experience do you have with {skill}, and what outcome did it produce?"})
    for skill in matched[:3]:
        questions.append({"focus": skill, "question": f"Describe a recent project where you used {skill}; what trade-offs did you make?"})
    return questions


def analyze_candidate(resume_text: str, job_description: str, candidate_name: str = "") -> dict[str, Any]:
    """Evaluate a resume against a job description without making hiring decisions."""
    resume_text, job_description = _clean_text(resume_text), _clean_text(job_description)
    if not resume_text or not job_description:
        raise ValueError("Both resume_text and job_description must contain readable text.")

    resume_skills, required_skills = extract_skills(resume_text), extract_jd_skills(job_description)
    skill_match = calculate_skill_match(resume_skills, required_skills)
    semantic_similarity = calculate_semantic_similarity(resume_text, job_description)
    evidence = build_evidence_report(skill_match["matched_skills"], resume_text)
    final_score, score_model = predict_score(skill_match["skill_match_score"], semantic_similarity * 100, evidence["evidence_score"])

    return {
        "candidate_name": candidate_name,
        "language": "en",
        "scores": {"overall": final_score, "skill_match": skill_match["skill_match_score"], "semantic_similarity": round(semantic_similarity * 100, 2), "evidence_score": evidence["evidence_score"]},
        "skills": {"resume": resume_skills, "required": required_skills, **skill_match},
        "evidence": evidence,
        "explanation": {
            "summary": f"{len(skill_match['matched_skills'])} of {len(required_skills)} identified job skills are represented in the resume.",
            "missing_skill_note": "Missing means not detected in the supplied resume, not that the candidate lacks the skill.",
            "embedding_model": active_model_name(),
            "score_model": score_model["version"],
        },
        "recommendation": _recommendation(final_score, skill_match["missing_skills"]),
        "interview_questions": _interview_questions(skill_match["matched_skills"], skill_match["missing_skills"]),
    }


def rank_candidates(candidates: list[dict[str, str]], job_description: str) -> list[dict[str, Any]]:
    results = [analyze_candidate(item["resume_text"], job_description, item.get("candidate_name", "")) for item in candidates]
    return sorted(results, key=lambda result: result["scores"]["overall"], reverse=True)


def chatbot_reply(question: str, analysis: dict[str, Any]) -> str:
    """Safe, deterministic assistant grounded in one analysis result."""
    question, skills = question.lower(), analysis["skills"]
    if "missing" in question or "gap" in question:
        return "Skills not detected in the resume: " + (", ".join(skills["missing_skills"]) or "none.")
    if "score" in question or "match" in question:
        return f"Overall match score: {analysis['scores']['overall']}%. {analysis['recommendation']}"
    if "evidence" in question:
        return f"Evidence support score is {analysis['scores']['evidence_score']}%. Claims remain self-reported until externally verified."
    return analysis["explanation"]["summary"]
