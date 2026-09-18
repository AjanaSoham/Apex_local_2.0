"""Internal AI service contract. Application data belongs to the Spring Boot gateway."""

import re
import base64
import tempfile
import hmac
import os
import requests
from pathlib import Path
from typing import Any
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from candidate_service import analyze_candidate
from candidate_service import chatbot_reply, rank_candidates
from embedding_service import active_model_name, generate_embedding
from jd_skill_extractor import extract_jd_skills
from lm_studio_parser import parse_resume_with_lm_studio
from parsers import extract_text
from resume_extractor import clean_text

app = FastAPI(title="Resume Matcher AI Service", version="1.1.0")





@app.middleware("http")
async def protect_internal_api(request: Request, call_next):
    """Require a gateway-held service key outside local development."""
    expected_key = os.getenv("AI_SERVICE_API_KEY", "")
    if request.url.path.startswith("/ai/v1") and expected_key:
        supplied_key = request.headers.get("X-AI-Service-Key", "")
        if not hmac.compare_digest(supplied_key, expected_key):
            return JSONResponse(status_code=401, content={"detail": "Invalid AI service key."})
    return await call_next(request)


class ResumeParseRequest(BaseModel):
    resume_text: str | None = None
    file_base64: str | None = None
    document_type: str = Field(default="txt", pattern="^(pdf|docx|txt|jpg|jpeg)$")
    file_name: str = ""


class JobAnalysisRequest(BaseModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)


class EmbeddingRequest(BaseModel):
    text: str = Field(min_length=1)


class MatchRequest(BaseModel):
    resume_id: int | None = None
    job_id: int | None = None
    resume_text: str = Field(min_length=1)
    job_description: str = Field(min_length=1)
    candidate_name: str = ""


class AnalysisRequest(BaseModel):
    analysis: dict[str, Any]


class InterviewRequest(BaseModel):
    resume_text: str = Field(min_length=1)
    job_description: str = Field(min_length=1)
    role: str = ""


class CandidateRequest(BaseModel):
    resume_text: str = Field(min_length=1)
    candidate_name: str = ""


class RankRequest(BaseModel):
    candidates: list[CandidateRequest] = Field(min_length=1, max_length=100)
    job_description: str = Field(min_length=1)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    resume_text: str = Field(min_length=1)
    job_description: str = Field(min_length=1)
    candidate_name: str = ""


def _importance(skill: str, description: str) -> str:
    lowered = description.lower()
    if any(marker in lowered for marker in (f"required {skill.lower()}", f"must have {skill.lower()}", f"mandatory {skill.lower()}")):
        return "HIGH"
    if any(marker in lowered for marker in ("preferred", "nice to have", "bonus")):
        return "LOW"
    return "MEDIUM"


def _resume_payload(text: str) -> dict[str, Any]:
    text = clean_text(text)
    if not text:
        raise ValueError("No readable text could be extracted from this resume.")
    parsed = parse_resume_with_lm_studio(text)
    return {"status": "COMPLETED", "language": "en",
            "resume": parsed,
            "warnings": [],
            "parserVersion": "1.3.0-lm-studio"}


def _parse_request_text(request: ResumeParseRequest) -> str:
    if request.resume_text and request.resume_text.strip():
        return request.resume_text
    if not request.file_base64:
        raise ValueError("Provide resume_text or file_base64.")
    try:
        contents = base64.b64decode(request.file_base64, validate=True)
    except ValueError as error:
        raise ValueError("file_base64 must be valid base64 document data.") from error
    suffix = f".{request.document_type}"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
        temporary.write(contents)
        temporary_path = Path(temporary.name)
    try:
        return extract_text(str(temporary_path))
    finally:
        temporary_path.unlink(missing_ok=True)


def _match_payload(request: MatchRequest) -> dict[str, Any]:
    analysis = analyze_candidate(request.resume_text, request.job_description, request.candidate_name)
    scores, skills = analysis["scores"], analysis["skills"]
    return {"resumeId": request.resume_id, "jobId": request.job_id, "overallScore": scores["overall"], "semanticScore": scores["semantic_similarity"], "skillScore": scores["skill_match"], "experienceScore": scores["evidence_score"], "evidenceScore": scores["evidence_score"], "matchedSkills": skills["matched_skills"], "missingSkills": skills["missing_skills"], "evidence": analysis["evidence"], "explanation": analysis["explanation"]["summary"], "modelVersion": analysis["explanation"]["score_model"]}


@app.get("/health")
def health():
    return {"status": "ok", "service": "ai-service", "version": app.version}


@app.post("/ai/v1/parse-resume-file")
async def parse_resume_file(file: UploadFile = File(...)):
    allowed_types = {
        "application/pdf": "pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "text/plain": "txt",
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
    }

    document_type = allowed_types.get(file.content_type or "")
    if document_type is None:
        document_type = {
            ".pdf": "pdf",
            ".docx": "docx",
            ".txt": "txt",
            ".jpg": "jpg",
            ".jpeg": "jpg",
        }.get(Path(file.filename or "").suffix.lower())
    if document_type is None:
        raise HTTPException(
            status_code=415,
            detail="Only PDF, DOCX, JPG, JPEG, and TXT files are supported.",
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=422, detail="The uploaded file is empty.")

    with tempfile.NamedTemporaryFile(
        suffix=f".{document_type}",
        delete=False,
    ) as temporary:
        temporary.write(contents)
        temporary_path = Path(temporary.name)

    try:
        extracted_text = extract_text(str(temporary_path))
        return _resume_payload(extracted_text)
        # return extracted_text
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    finally:
        temporary_path.unlink(missing_ok=True)


@app.post("/ai/v1/analyze-jd")
def analyze_jd(request: JobAnalysisRequest):
    skills = extract_jd_skills(request.description)
    return {"title": request.title, "requiredSkills": [{"name": skill, "normalizedName": skill.lower().replace(" ", "_"), "importance": _importance(skill, request.description)} for skill in skills], "experienceRequired": None, "language": "en", "modelVersion": "skill-taxonomy-v1"}


@app.post("/ai/v1/generate-embedding")
def generate_embedding_endpoint(request: EmbeddingRequest):
    vector = generate_embedding(request.text)
    return {"embedding": vector, "dimension": len(vector), "modelName": active_model_name(), "language": "en"}


@app.post("/ai/v1/match")
def match(request: MatchRequest):
    try:
        return _match_payload(request)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/ai/v1/rank")
def rank(request: RankRequest):
    try:
        candidates = [
            {"resume_text": candidate.resume_text, "candidate_name": candidate.candidate_name}
            for candidate in request.candidates
        ]
        results = rank_candidates(candidates, request.job_description)
        return {"candidates": results, "count": len(results)}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/ai/v1/chat")
def chat(request: ChatRequest):
    try:
        analysis = analyze_candidate(
            request.resume_text,
            request.job_description,
            request.candidate_name,
        )
        return {
            "answer": chatbot_reply(request.question, analysis),
            "candidateName": request.candidate_name,
            "modelVersion": analysis["explanation"]["score_model"],
        }
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/ai/v1/explain-match")
def explain_match(request: AnalysisRequest):
    try:
        if "overallScore" in request.analysis:
            missing = request.analysis.get("missingSkills", [])
            recommendation = "Strong match - recommend structured interview." if request.analysis["overallScore"] >= 75 else "Review missing requirements in a screening call."
            return {"explanation": request.analysis["explanation"], "recommendation": recommendation, "verificationNotice": "Evidence is self-reported until verified by an authorized process."}
        return {"explanation": request.analysis["explanation"], "recommendation": request.analysis["recommendation"], "verificationNotice": "Evidence is self-reported until verified by an authorized process."}
    except KeyError as error:
        raise HTTPException(status_code=422, detail="analysis must be an AI match analysis object") from error


@app.post("/ai/v1/recommend")
def recommend(request: AnalysisRequest):
    try:
        missing = request.analysis.get("missingSkills", request.analysis.get("skills", {}).get("missing_skills", []))
        return {"recommendations": [{"type": "SKILL_GAP", "content": f"Build demonstrable experience with {skill}."} for skill in missing], "modelVersion": "rules-v1"}
    except KeyError as error:
        raise HTTPException(status_code=422, detail="analysis must include skills.missing_skills") from error


@app.post("/ai/v1/interview")
def interview(request: InterviewRequest):
    analysis = analyze_candidate(request.resume_text, request.job_description)
    return {"role": request.role, "questions": analysis["interview_questions"], "modelVersion": "rules-v1"}
