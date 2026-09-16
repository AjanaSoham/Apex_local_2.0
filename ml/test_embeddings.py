from embedding_service import generate_embedding


text = """
Python developer with experience in machine learning,
SQL, data analysis and backend development.
"""


embedding = generate_embedding(text)


print("Embedding generated successfully!")
print("Embedding length:", len(embedding))
print("First 10 values:", embedding[:10])