"""FastAPI interface for explainable resume-to-job matching."""

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import BaseModel, Field

from candidate_service import analyze_candidate, chatbot_reply, rank_candidates
from match_model import train_model
from language_service import detect_language
from store import (add_application, add_job, add_resume, candidates_for_job, current_user,
                   get_job, get_resume, initialize, jobs_for_recruiter, login, register)

app = FastAPI(title="Candidate Match API", version="1.0.0")
auth_scheme = HTTPBearer()


@app.on_event("startup")
def startup() -> None:
    initialize()


def authenticated_user(credentials: HTTPAuthorizationCredentials = Depends(auth_scheme)) -> dict:
    try:
        return current_user(credentials.credentials)
    except PermissionError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error


def require_role(role: str, user: dict) -> None:
    if user["role"] != role:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"This action requires the {role} role.")


class MatchRequest(BaseModel):
    resume_text: str = Field(min_length=1)
    job_description: str = Field(min_length=1)
    candidate_name: str = ""


class Candidate(BaseModel):
    resume_text: str = Field(min_length=1)
    candidate_name: str = ""


class RankRequest(BaseModel):
    candidates: list[Candidate] = Field(min_length=1)
    job_description: str = Field(min_length=1)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    analysis: dict


class TrainingExample(BaseModel):
    resume_text: str | None = None
    job_description: str | None = None
    skill_match: float | None = Field(default=None, ge=0, le=100)
    semantic_similarity: float | None = Field(default=None, ge=0, le=100)
    evidence_score: float | None = Field(default=None, ge=0, le=100)
    label: float = Field(ge=0, le=100, description="Human-reviewed match label, not a hiring decision")


class TrainRequest(BaseModel):
    examples: list[TrainingExample] = Field(min_length=8)


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=12)
    role: str = Field(pattern="^(candidate|recruiter)$")


class LoginRequest(BaseModel):
    email: str
    password: str


class ResumeRequest(BaseModel):
    resume_text: str = Field(min_length=1)


class JobRequest(BaseModel):
    title: str = Field(min_length=2)
    description: str = Field(min_length=1)


class ApplyRequest(BaseModel):
    resume_id: int = Field(gt=0)


@app.get("/health")
def health():
    return {"status": "ok", "version": app.version}


@app.get("/", include_in_schema=False)
def landing_page():
    return FileResponse(Path(__file__).with_name("portal.html"))


@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
def create_account(request: RegisterRequest):
    try:
        return register(request.email, request.password, request.role)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/auth/login")
def create_session(request: LoginRequest):
    try:
        return login(request.email, request.password)
    except PermissionError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error


@app.get("/me")
def me(user: dict = Depends(authenticated_user)):
    return user


@app.post("/candidate/resumes", status_code=status.HTTP_201_CREATED)
def upload_resume(request: ResumeRequest, user: dict = Depends(authenticated_user)):
    require_role("candidate", user)
    language = detect_language(request.resume_text)["language"]
    return {"resume_id": add_resume(user["id"], request.resume_text, language), "language": language}


@app.post("/recruiter/jobs", status_code=status.HTTP_201_CREATED)
def create_job(request: JobRequest, user: dict = Depends(authenticated_user)):
    require_role("recruiter", user)
    return {"job_id": add_job(user["id"], request.title, request.description)}


@app.get("/recruiter/jobs")
def recruiter_jobs(user: dict = Depends(authenticated_user)):
    require_role("recruiter", user)
    return {"jobs": jobs_for_recruiter(user["id"])}


@app.post("/candidate/jobs/{job_id}/apply", status_code=status.HTTP_201_CREATED)
def apply(job_id: int, request: ApplyRequest, user: dict = Depends(authenticated_user)):
    require_role("candidate", user)
    job, resume = get_job(job_id), get_resume(request.resume_id, user["id"])
    if job is None or resume is None:
        raise HTTPException(status_code=404, detail="Job or resume was not found.")
    analysis = analyze_candidate(resume["resume_text"], job["description"], user["email"])
    try:
        application_id = add_application(job_id, user["id"], request.resume_id, analysis)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"application_id": application_id, "analysis": analysis}


@app.get("/recruiter/jobs/{job_id}/candidates")
def ranked_candidates(job_id: int, user: dict = Depends(authenticated_user)):
    require_role("recruiter", user)
    job = get_job(job_id)
    if job is None or job["recruiter_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Job was not found.")
    return {"job_id": job_id, "candidates": candidates_for_job(job_id)}


@app.post("/match")
def match(request: MatchRequest):
    try:
        return analyze_candidate(request.resume_text, request.job_description, request.candidate_name)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/rank")
def rank(request: RankRequest):
    return {"candidates": rank_candidates([item.model_dump() for item in request.candidates], request.job_description)}


@app.post("/chat")
def chat(request: ChatRequest):
    try:
        return {"reply": chatbot_reply(request.question, request.analysis)}
    except (KeyError, TypeError) as error:
        raise HTTPException(status_code=422, detail="analysis must be a response from /match") from error


@app.post("/train")
def train(request: TrainRequest):
    """Calibrate the local score model from independently human-labeled examples."""
    try:
        examples = []
        for item in request.examples:
            record = item.model_dump()
            if record["resume_text"] and record["job_description"]:
                analysis = analyze_candidate(record["resume_text"], record["job_description"])
                record.update(analysis["scores"])
            if any(record[key] is None for key in ("skill_match", "semantic_similarity", "evidence_score")):
                raise ValueError("Each example needs resume_text + job_description, or all three precomputed feature scores.")
            examples.append(record)
        return train_model(examples)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
