# Candidate Match API

An explainable, local-first resume-to-job-description matching service. It supports PDF, DOCX and TXT parsing; normalized skills; semantic and skill scoring; evidence quotes; missing-skill analysis; candidate ranking; interview questions; and a grounded chatbot response.

## Run

From the project root:

```powershell
./venv/Scripts/python.exe -m uvicorn app:app --app-dir ml --reload
```

Open `http://127.0.0.1:8000/docs` for the interactive API. The primary endpoints are `POST /match`, `POST /rank`, and `POST /chat`; `GET /health` confirms the service is available.

For the local candidate/recruiter portal, open `http://127.0.0.1:8000/` after starting the server.

## Persistent candidate and recruiter flow

The API initializes a local `ml/candidate_match.db` automatically. Register a candidate and recruiter using `POST /auth/register`, then use `POST /auth/login` to obtain each account's bearer token. In Swagger, click **Authorize** and enter `Bearer <access_token>`.

1. As a candidate, call `POST /candidate/resumes` with the resume text.
2. As a recruiter, call `POST /recruiter/jobs` with a job title and description.
3. As the candidate, call `POST /candidate/jobs/{job_id}/apply` with the returned resume ID.
4. As the recruiter who created the job, call `GET /recruiter/jobs/{job_id}/candidates` to receive candidates ranked by their stored analysis.

Passwords are stored using scrypt hashes and sessions are short-lived bearer tokens. This local persistence is designed for development; move the schema to managed PostgreSQL, use a secrets manager, HTTPS, migrations, audit logging, and authorized retention controls before production use.

## Validate

```powershell
./venv/Scripts/python.exe ml/evaluate.py
```

The default embedding is a deterministic offline fallback. See `ml/MODEL_CARD.md` for model version, optional transformer configuration, limitations, and responsible-use notes.

`/match` now returns detected languages and an evidence-support report. The evidence score measures how well a resume statement is supported by context and outcomes; it is not proof of truth. Use `POST /train` with at least eight human-labeled resume/JD pairs and a `label` from 0–100 to calibrate a local scoring model. See `ml/training_dataset.example.json` for the request format. Feature records (`skill_match`, `semantic_similarity`, `evidence_score`, `label`) are also supported for controlled experiments.
