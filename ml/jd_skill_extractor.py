from skill_extractor import extract_skills


def extract_jd_skills(job_description: str) -> list:
    """
    Extract required skills from a job description.
    """

    return extract_skills(job_description)