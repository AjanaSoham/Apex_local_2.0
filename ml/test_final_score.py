from matcher import (
    calculate_semantic_similarity,
    calculate_skill_match,
    calculate_final_score
)


resume_text = """
Rahul Sharma is a software developer with experience in
Python, Java, SQL, Machine Learning and Git.

He has worked on backend development and data analysis.
"""


job_description = """
We are looking for a Python developer with experience in
Machine Learning, SQL, Git and Docker.

The candidate should understand backend development
and data analysis.
"""


resume_skills = [
    "Python",
    "Java",
    "SQL",
    "Machine Learning",
    "Git"
]


required_skills = [
    "Python",
    "SQL",
    "Machine Learning",
    "Docker"
]


# 1. Calculate skill matching
skill_result = calculate_skill_match(
    resume_skills,
    required_skills
)


# 2. Calculate semantic similarity
semantic_score = calculate_semantic_similarity(
    resume_text,
    job_description
)


# 3. Calculate final score
final_score = calculate_final_score(
    skill_result["skill_match_score"],
    semantic_score
)


print("========== FINAL RESUME MATCH ==========")

print("Matched skills:")
for skill in skill_result["matched_skills"]:
    print("-", skill)

print("\nMissing skills:")
for skill in skill_result["missing_skills"]:
    print("-", skill)

print(
    "\nSkill match score:",
    skill_result["skill_match_score"],
    "%"
)

print(
    "Semantic similarity:",
    round(semantic_score * 100, 2),
    "%"
)

print(
    "Final match score:",
    final_score,
    "%"
)