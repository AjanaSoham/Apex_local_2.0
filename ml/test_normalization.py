from skill_extractor import normalize_skill


test_skills = [
    "python",
    "PYTHON",
    "python 3",
    "nodejs",
    "node.js",
    "ml",
    "machine-learning",
    "sklearn"
]


for skill in test_skills:
    print(skill, "→", normalize_skill(skill))