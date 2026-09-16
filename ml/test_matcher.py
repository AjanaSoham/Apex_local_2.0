from matcher import calculate_semantic_similarity


resume_text = """
Python developer with experience in machine learning,
SQL, data analysis, Git and backend development.
"""


job_description = """
We are looking for a software engineer skilled in Python,
machine learning, databases, data analysis and backend systems.
"""


score = calculate_semantic_similarity(
    resume_text,
    job_description
)


print("========== SEMANTIC MATCHING ==========")
print("Similarity score:", score)
print("Similarity percentage:", round(score * 100, 2), "%")