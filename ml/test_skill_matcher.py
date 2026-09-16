from matcher import calculate_skill_match


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


result = calculate_skill_match(
    resume_skills,
    required_skills
)


print("========== SKILL MATCHING ==========")
print("Matched skills:", result["matched_skills"])
print("Missing skills:", result["missing_skills"])
print("Skill match score:", result["skill_match_score"], "%")