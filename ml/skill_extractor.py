import re
import unicodedata


SKILL_ALIASES = {
    "python": "Python",
    "python 3": "Python",

    "java": "Java",
    "java 8": "Java",

    "c++": "C++",
    "cpp": "C++",

    "c": "C",

    "javascript": "JavaScript",
    "js": "JavaScript",

    "typescript": "TypeScript",
    "ts": "TypeScript",

    "html": "HTML",
    "css": "CSS",

    "react": "React",
    "reactjs": "React",

    "angular": "Angular",

    "node.js": "Node.js",
    "nodejs": "Node.js",
    "node js": "Node.js",

    "spring boot": "Spring Boot",

    "sql": "SQL",
    "mysql": "MySQL",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",

    "mongodb": "MongoDB",

    "machine learning": "Machine Learning",
    "machine-learning": "Machine Learning",
    "ml": "Machine Learning",

    "deep learning": "Deep Learning",
    "deep-learning": "Deep Learning",
    "dl": "Deep Learning",

    "artificial intelligence": "Artificial Intelligence",
    "ai": "Artificial Intelligence",

    "natural language processing": "Natural Language Processing",
    "nlp": "Natural Language Processing",

    "computer vision": "Computer Vision",

    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",

    "git": "Git",
    "github": "GitHub",

    "docker": "Docker",
    "kubernetes": "Kubernetes",

    "aws": "AWS",
    "azure": "Azure",
    "google cloud": "Google Cloud",

    "data analysis": "Data Analysis",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "scikit-learn": "Scikit-learn",
    "sklearn": "Scikit-learn",

    "rest api": "REST API",
    "restful api": "REST API",

    "fastapi": "FastAPI",
    "linux": "Linux",

    "communication": "Communication",
    "problem solving": "Problem Solving",
}


def normalize_skill(skill: str) -> str:
    """
    Convert a skill variation into its standard name.
    """

    cleaned_skill = skill.lower().strip()

    return SKILL_ALIASES.get(
        cleaned_skill,
        skill.strip()
    )


def extract_skills(text: str) -> list:
    """
    Extract and normalize known skills from text.
    """

    text_lower = unicodedata.normalize("NFKC", text.lower())
    found_skills = set()

    # Check longer skills first.
    # This helps detect 'machine learning' before 'ml'.
    skill_patterns = sorted(
        SKILL_ALIASES.keys(),
        key=len,
        reverse=True
    )

    for skill_pattern in skill_patterns:

        # Avoid substring matches (for example, "c" in "communication" or
        # "ml" in "email") while still supporting technical punctuation.
        if re.search(r"(?<![a-z0-9])" + re.escape(skill_pattern) + r"(?![a-z0-9])", text_lower):

            standard_name = normalize_skill(skill_pattern)

            found_skills.add(standard_name)

    return sorted(found_skills)
