# Resume Matcher AI Service

This repository is the internal Python/FastAPI intelligence service for the AI Resume Screener and Job Matcher. It implements English resume parsing, skill extraction and normalization, embeddings, matching, evidence scoring, explanations, recommendations, and interview questions. Supported resume files are PDF, DOCX, JPG, JPEG, and TXT.

The Spring Boot application is the public API gateway and owns users, authentication, authorization, PostgreSQL/pgvector, jobs, applications, file storage, and all candidate/recruiter screens. The frontend must not call this service directly.

## Run locally

```powershell
.\venv\Scripts\python.exe -m uvicorn app:app --app-dir ml --reload
```

Open `http://127.0.0.1:8000/docs` to inspect and test the internal OpenAPI contract. The AI API base path is `/ai/v1`; endpoint details are in [AI_API_CONTRACT.md](ml/AI_API_CONTRACT.md).

## Validate

```powershell
.\venv\Scripts\python.exe ml\evaluate.py
```

This validates the fixed match-score evaluation set. The endpoint smoke test was also run for resume parsing, JD analysis, embedding generation, matching, and interview question generation.

## Environment

Copy `.env.example` to `.env` and supply only local/deployment configuration. Never commit `.env`, credentials, or API keys.

## Evidence boundary

Evidence scoring measures textual support in the supplied resume: mention, action context, and measurable outcome. It does not establish whether a claim is true. The Spring Boot gateway must arrange any authorized external verification, such as credential checks, work samples, or references.
