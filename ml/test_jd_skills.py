from jd_skill_extractor import extract_jd_skills


job_description = """
We are looking for a Python developer.

Required skills:
Python, Machine Learning, SQL, Git and Docker.

The candidate should also understand data analysis
and REST API development.
"""


skills = extract_jd_skills(job_description)


print("========== JOB DESCRIPTION SKILLS ==========")

for skill in skills:
    print("-", skill)