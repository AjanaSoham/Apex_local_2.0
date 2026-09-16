import math

from embedding_service import generate_embedding


def calculate_semantic_similarity(
    resume_text: str,
    job_description: str
) -> float:
    """
    Calculate semantic similarity between resume
    and job description.

    Returns a value between 0 and 1.
    """

    resume_embedding = generate_embedding(resume_text)
    jd_embedding = generate_embedding(job_description)

    numerator = sum(left * right for left, right in zip(resume_embedding, jd_embedding))
    left_norm = math.sqrt(sum(value * value for value in resume_embedding))
    right_norm = math.sqrt(sum(value * value for value in jd_embedding))
    similarity = numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0

    return round(float(similarity), 4)


def calculate_skill_match(
    resume_skills: list,
    required_skills: list
) -> dict:
    """
    Calculate matched and missing skills.
    """

    # Convert both lists to lowercase for comparison
    resume_skill_map = {
        skill.lower().strip(): skill
        for skill in resume_skills
    }

    required_skill_map = {
        skill.lower().strip(): skill
        for skill in required_skills
    }

    resume_skill_set = set(resume_skill_map.keys())
    required_skill_set = set(required_skill_map.keys())

    matched_skill_keys = (
        resume_skill_set.intersection(required_skill_set)
    )

    missing_skill_keys = (
        required_skill_set.difference(resume_skill_set)
    )

    # Preserve the original standard names
    matched_skills = sorted(
        resume_skill_map[key]
        for key in matched_skill_keys
    )

    missing_skills = sorted(
        required_skill_map[key]
        for key in missing_skill_keys
    )

    if len(required_skill_set) == 0:
        skill_score = 0.0
    else:
        skill_score = (
            len(matched_skill_keys)
            / len(required_skill_set)
        ) * 100

    return {
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "skill_match_score": round(skill_score, 2)
    }


def calculate_final_score(
    skill_match_score: float,
    semantic_similarity: float
) -> float:
    """
    Combine skill matching and semantic similarity.

    Skill matching contributes 70%.
    Semantic similarity contributes 30%.
    """

    semantic_percentage = semantic_similarity * 100

    final_score = (
        skill_match_score * 0.70
        + semantic_percentage * 0.30
    )

    return round(final_score, 2)
