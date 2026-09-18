import json
import os
import re
from typing import Any

import requests
from dotenv import load_dotenv

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DEFAULT_BASE_URL = "http://127.0.0.1:1234/v1/models"
DEFAULT_MODEL = "google/gemma-4-e4b"


def _json_from_content(content: str) -> dict[str, Any]:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
        content = re.sub(r"\s*```$", "", content)

    decoder = json.JSONDecoder()
    try:
        value, _ = decoder.raw_decode(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise ValueError("LM Studio returned no JSON object.")
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError as error:
            raise ValueError(
                f"LM Studio returned malformed JSON at line {error.lineno}, "
                f"column {error.colno}: {error.msg}"
            ) from error

    if not isinstance(value, dict):
        raise ValueError("LM Studio returned JSON with an invalid root type.")
    return value


def _string(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _list_of_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_string(item) for item in value if _string(item)]


def _normalize_skill(value: object) -> dict[str, Any] | None:
    if isinstance(value, str):
        name = value.strip()
        confidence = 0.8
    elif isinstance(value, dict):
        name = _string(value.get("name") or value.get("skill"))
        confidence = value.get("confidence", 0.8)
    else:
        return None
    if not name:
        return None
    try:
        confidence = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        confidence = 0.8
    return {
        "name": name,
        "normalizedName": re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"),
        "confidence": confidence,
    }


def _normalize_education(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    entries = []
    for item in value:
        if not isinstance(item, dict):
            continue
        entries.append({
            "degree": _string(item.get("degree") or item.get("qualification")),
            "institution": _string(item.get("institution") or item.get("school")),
            "end_year": _string(item.get("end_year") or item.get("year") or item.get("graduation_year")),
            "grade": _string(item.get("grade") or item.get("cgpa") or item.get("percentage")),
        })
    return [entry for entry in entries if any(entry.values())]


def _normalize_experience(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    entries = []
    for item in value:
        if not isinstance(item, dict):
            continue
        entry = {
            "company": _string(item.get("company") or item.get("employer")),
            "job_title": _string(item.get("job_title") or item.get("title") or item.get("role")),
            "location": _string(item.get("location")),
            "responsibilities": _list_of_strings(item.get("responsibilities") or item.get("duties")),
            "technologies": _list_of_strings(item.get("technologies") or item.get("tools")),
            "additional_information": _list_of_strings(item.get("additional_information")),
        }
        for key in ("start_date", "end_date"):
            value = _string(item.get(key))
            if value:
                entry[key] = value
        if any(entry[key] for key in ("company", "job_title", "location", "responsibilities")):
            entries.append(entry)
    return entries


def _normalize_projects(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    projects = []
    for item in value:
        if isinstance(item, str):
            if item.strip():
                projects.append({"name": item.strip(), "description": ""})
        elif isinstance(item, dict):
            name = _string(item.get("name") or item.get("title"))
            description = _string(item.get("description") or item.get("details"))
            if name or description:
                projects.append({"name": name, "description": description})
    return projects


def normalize_resume(value: dict[str, Any]) -> dict[str, Any]:
    resume = value.get("resume") if isinstance(value.get("resume"), dict) else value
    skills = []
    for item in resume.get("skills", []):
        normalized = _normalize_skill(item)
        if normalized and normalized["normalizedName"] != "spring":
            skills.append(normalized)

    return {
        "name": _string(resume.get("name") or resume.get("candidate_name")),
        "email": _string(resume.get("email")),
        "phone": _string(resume.get("phone")),
        "skills": skills,
        "education": _normalize_education(resume.get("education")),
        "experience": _normalize_experience(resume.get("experience")),
        "years_of_experience": resume.get("years_of_experience", 0),
        "projects": _normalize_projects(resume.get("projects")),
        "certifications": _string(resume.get("certifications")),
        "links": resume.get("links") if isinstance(resume.get("links"), dict) else {},
    }


def parse_resume_with_lm_studio(text: str) -> dict[str, Any]:
    if not text.strip():
        raise ValueError("Cannot send empty resume text to LM Studio.")

    base_url = os.getenv("LM_STUDIO_BASE_URL", DEFAULT_BASE_URL).strip()
    url = os.getenv("LM_STUDIO_URL", "").strip()
    if not url:
        url = re.sub(r"/models/?$", "/chat/completions", base_url)
    model = os.getenv("LM_STUDIO_MODEL", DEFAULT_MODEL).strip()
    timeout = float(os.getenv("LM_STUDIO_TIMEOUT", "90"))
    schema = {
        "name": "",
        "email": "",
        "phone": "",
        "skills": [{"name": "", "confidence": 0.0}],
        "education": [{"degree": "", "institution": "", "end_year": "", "grade": ""}],
        "experience": [{
            "company": "", "job_title": "", "location": "",
            "responsibilities": [], "technologies": [],
            "start_date": "", "end_date": "",
        }],
        "years_of_experience": 0,
        "projects": [{"name": "", "description": ""}],
        "certifications": "",
        "links": {},
    }
    prompt = (
        "Extract structured information from this resume. Return ONLY one valid JSON object "
        "matching the schema below. Do not infer employment from an objective or project. "
        "Do not put employers in education. Education must contain only real degrees/schools; "
        "use end_year only, never start_year. Preserve missing values as empty strings/lists. "
        "Ignore standalone Spring unless the resume explicitly says Spring Boot. "
        "Keep responsibilities concise: maximum 8 items per job, maximum 180 characters each. "
        "Keep technologies to the 20 most relevant items. Do not copy the entire resume into JSON.\n\n"
        f"SCHEMA:\n{json.dumps(schema, ensure_ascii=True)}\n\n"
        f"RESUME TEXT:\n{text[:40000]}"
    )
    response = None
    try:
        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a precise resume information extraction service."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
                "max_tokens": 6000,
                "chat_template_kwargs": {"enable_thinking": False},
                # LM Studio supports "text" and "json_schema" here, but not the
                # OpenAI-only "json_object" value. The prompt still requires a
                # single JSON object, which _json_from_content validates.
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "resume_extraction",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "name": {"type": "string"},
                                "email": {"type": "string"},
                                "phone": {"type": "string"},
                                "skills": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "name": {"type": "string"},
                                            "confidence": {"type": "number"},
                                        },
                                        "required": ["name", "confidence"],
                                    },
                                },
                                "education": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "degree": {"type": "string"},
                                            "institution": {"type": "string"},
                                            "end_year": {"type": "string"},
                                            "grade": {"type": "string"},
                                        },
                                        "required": ["degree", "institution", "end_year", "grade"],
                                    },
                                },
                                "experience": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "company": {"type": "string"},
                                            "job_title": {"type": "string"},
                                            "location": {"type": "string"},
                                            "responsibilities": {"type": "array", "items": {"type": "string"}},
                                            "technologies": {"type": "array", "items": {"type": "string"}},
                                            "additional_information": {"type": "array", "items": {"type": "string"}},
                                            "start_date": {"type": "string"},
                                            "end_date": {"type": "string"},
                                        },
                                        "required": [
                                            "company", "job_title", "location", "responsibilities",
                                            "technologies", "additional_information", "start_date", "end_date",
                                        ],
                                    },
                                },
                                "years_of_experience": {"type": "number"},
                                "projects": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "name": {"type": "string"},
                                            "description": {"type": "string"},
                                        },
                                        "required": ["name", "description"],
                                    },
                                },
                                "certifications": {"type": "string"},
                                "links": {"type": "object"},
                            },
                            "required": [
                                "name", "email", "phone", "skills", "education", "experience",
                                "years_of_experience", "projects", "certifications", "links",
                            ],
                        },
                    },
                },
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        message = payload["choices"][0]["message"]
        content = message.get("content") or ""
        if not content.strip():
            raise ValueError("LM Studio returned no answer content.")
        if payload["choices"][0].get("finish_reason") == "length":
            raise ValueError(
                "LM Studio truncated the JSON response; reduce resume size or increase max_tokens."
            )
    except requests.RequestException as error:
        detail = response.text[:300].strip() if response is not None else str(error)
        raise RuntimeError(f"LM Studio connection/request failed: {detail}") from error
    except (ValueError, KeyError, IndexError, TypeError) as error:
        detail = response.text[:300].strip() if response is not None else str(error)
        raise RuntimeError(f"LM Studio returned an invalid response: {detail}") from error
    try:
        return normalize_resume(_json_from_content(content))
    except ValueError as error:
        raise RuntimeError(f"LM Studio returned invalid resume JSON: {error}") from error


def parse_resume_from_image_with_lm_studio(
    image_bytes: bytes | list[bytes],
    mime_type: str = "image/jpeg",
) -> dict[str, Any]:
    """Send a resume image (or list of page images) directly to LM Studio's vision API.

    Accepts a single ``bytes`` object (JPG upload) or a ``list[bytes]`` (scanned PDF pages).
    No OCR step is involved — the LLM reads the images natively.
    """
    import base64

    pages: list[bytes] = [image_bytes] if isinstance(image_bytes, bytes) else image_bytes
    if not pages or not any(pages):
        raise ValueError("Cannot send empty image to LM Studio.")

    base_url = os.getenv("LM_STUDIO_BASE_URL", DEFAULT_BASE_URL).strip()
    url = os.getenv("LM_STUDIO_URL", "").strip()
    if not url:
        url = re.sub(r"/models/?$", "/chat/completions", base_url)
    model = os.getenv("LM_STUDIO_MODEL", DEFAULT_MODEL).strip()
    timeout = float(os.getenv("LM_STUDIO_TIMEOUT", "90"))

    schema = {
        "detected_language": "en",
        "name": "",
        "email": "",
        "phone": "",
        "skills": [{"name": "", "confidence": 0.0}],
        "education": [{"degree": "", "institution": "", "end_year": "", "grade": ""}],
        "experience": [{
            "company": "", "job_title": "", "location": "",
            "responsibilities": [], "technologies": [],
            "start_date": "", "end_date": "",
        }],
        "years_of_experience": 0,
        "projects": [{"name": "", "description": ""}],
        "certifications": "",
        "links": {},
    }
    prompt = (
        "Extract structured information from the resume shown in this image. "
        "Return ONLY one valid JSON object matching the schema below. "
        "Set detected_language to the BCP-47 code of the language the resume is written in "
        "(e.g. \"en\" for English, \"fr\" for French, \"es\" for Spanish, \"de\" for German). "
        "Do not infer employment from an objective or project. "
        "Do not put employers in education. Education must contain only real degrees/schools; "
        "use end_year only, never start_year. Preserve missing values as empty strings/lists. "
        "Ignore standalone Spring unless the resume explicitly says Spring Boot. "
        "Keep responsibilities concise: maximum 8 items per job, maximum 180 characters each. "
        "Keep technologies to the 20 most relevant items. Do not copy the entire resume into JSON.\n\n"
        f"SCHEMA:\n{json.dumps(schema, ensure_ascii=True)}"
    )

    image_content = [
        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64.b64encode(page).decode()}"}}
        for page in pages
    ]
    response = None
    try:
        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a precise resume information extraction service."},
                    {
                        "role": "user",
                        "content": [
                            *image_content,
                            {"type": "text", "text": prompt},
                        ],
                    },
                ],
                "temperature": 0,
                "max_tokens": 6000,
                "chat_template_kwargs": {"enable_thinking": False},
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "resume_extraction",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "detected_language": {"type": "string"},
                                "name": {"type": "string"},
                                "email": {"type": "string"},
                                "phone": {"type": "string"},
                                "skills": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "name": {"type": "string"},
                                            "confidence": {"type": "number"},
                                        },
                                        "required": ["name", "confidence"],
                                    },
                                },
                                "education": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "degree": {"type": "string"},
                                            "institution": {"type": "string"},
                                            "end_year": {"type": "string"},
                                            "grade": {"type": "string"},
                                        },
                                        "required": ["degree", "institution", "end_year", "grade"],
                                    },
                                },
                                "experience": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "company": {"type": "string"},
                                            "job_title": {"type": "string"},
                                            "location": {"type": "string"},
                                            "responsibilities": {"type": "array", "items": {"type": "string"}},
                                            "technologies": {"type": "array", "items": {"type": "string"}},
                                            "additional_information": {"type": "array", "items": {"type": "string"}},
                                            "start_date": {"type": "string"},
                                            "end_date": {"type": "string"},
                                        },
                                        "required": [
                                            "company", "job_title", "location", "responsibilities",
                                            "technologies", "additional_information", "start_date", "end_date",
                                        ],
                                    },
                                },
                                "years_of_experience": {"type": "number"},
                                "projects": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "name": {"type": "string"},
                                            "description": {"type": "string"},
                                        },
                                        "required": ["name", "description"],
                                    },
                                },
                                "certifications": {"type": "string"},
                                "links": {"type": "object"},
                            },
                            "required": [
                                "detected_language", "name", "email", "phone", "skills", "education", "experience",
                                "years_of_experience", "projects", "certifications", "links",
                            ],
                        },
                    },
                },
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        message = payload["choices"][0]["message"]
        content = message.get("content") or ""
        if not content.strip():
            raise ValueError("LM Studio returned no answer content.")
        if payload["choices"][0].get("finish_reason") == "length":
            raise ValueError(
                "LM Studio truncated the JSON response; reduce image size or increase max_tokens."
            )
    except requests.RequestException as error:
        detail = response.text[:300].strip() if response is not None else str(error)
        raise RuntimeError(f"LM Studio connection/request failed: {detail}") from error
    except (ValueError, KeyError, IndexError, TypeError) as error:
        detail = response.text[:300].strip() if response is not None else str(error)
        raise RuntimeError(f"LM Studio returned an invalid response: {detail}") from error
    try:
        raw = _json_from_content(content)
        detected_language = raw.get("detected_language", "en") or "en"
        normalized = normalize_resume(raw)
        normalized["detected_language"] = detected_language
        return normalized
    except ValueError as error:
        raise RuntimeError(f"LM Studio returned invalid resume JSON: {error}") from error


# ---------------------------------------------------------------------------
# JD Skill Extractor
# ---------------------------------------------------------------------------

def _normalize_jd(value: dict[str, Any]) -> dict[str, Any]:
    """Validate and clean the raw LLM output for a JD analysis."""
    jd = value.get("jd") if isinstance(value.get("jd"), dict) else value

    def _importance(v: object) -> str:
        s = _string(v).upper()
        return s if s in {"HIGH", "MEDIUM", "LOW"} else "MEDIUM"

    def _category(v: object) -> str:
        s = _string(v).lower()
        return s if s in {"technical", "tool", "soft", "domain"} else "technical"

    skills = []
    for item in jd.get("skills", []):
        if not isinstance(item, dict):
            continue
        name = _string(item.get("name"))
        if not name:
            continue
        skills.append({
            "name": name,
            "normalizedName": re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"),
            "importance": _importance(item.get("importance")),
            "category": _category(item.get("category")),
        })

    return {
        "jobTitle": _string(jd.get("jobTitle") or jd.get("job_title")),
        "experienceRequired": _string(jd.get("experienceRequired") or jd.get("experience_required")),
        "educationRequired": _string(jd.get("educationRequired") or jd.get("education_required")),
        "skills": skills,
    }


def extract_jd_skills_with_lm_studio(text: str) -> dict[str, Any]:
    """Extract required skills and job metadata from raw job description text.

    Returns a dict with jobTitle, experienceRequired, educationRequired,
    and skills (list of name / normalizedName / importance / category).
    """
    if not text.strip():
        raise ValueError("Cannot send empty job description to LM Studio.")

    base_url = os.getenv("LM_STUDIO_BASE_URL", DEFAULT_BASE_URL).strip()
    url = os.getenv("LM_STUDIO_URL", "").strip()
    if not url:
        url = re.sub(r"/models/?$", "/chat/completions", base_url)
    model = os.getenv("LM_STUDIO_MODEL", DEFAULT_MODEL).strip()
    timeout = float(os.getenv("LM_STUDIO_TIMEOUT", "90"))

    schema = {
        "jobTitle": "",
        "experienceRequired": "",
        "educationRequired": "",
        "skills": [
            {
                "name": "",
                "importance": "HIGH | MEDIUM | LOW",
                "category": "technical | tool | soft | domain",
            }
        ],
    }

    prompt = (
        "Extract structured hiring requirements from the job description below. "
        "Return ONLY one valid JSON object matching the schema. Rules:\n"
        "- jobTitle: the role being hired for (e.g. 'Backend Developer').\n"
        "- experienceRequired: total years expected (e.g. '3+ years'), empty string if not stated.\n"
        "- educationRequired: minimum degree/field if mentioned, empty string if not stated.\n"
        "- skills: every distinct skill, technology, tool, or competency mentioned.\n"
        "  - importance: HIGH if the JD says required/must/mandatory, "
        "LOW if preferred/nice-to-have/bonus, MEDIUM otherwise.\n"
        "  - category: 'technical' for languages/frameworks/databases, "
        "'tool' for specific software/platforms, "
        "'soft' for interpersonal/communication skills, "
        "'domain' for industry/business knowledge.\n"
        "Do not invent skills not present in the text. Do not duplicate skills.\n\n"
        f"SCHEMA:\n{json.dumps(schema, ensure_ascii=True)}\n\n"
        f"JOB DESCRIPTION:\n{text[:20000]}"
    )

    response = None
    try:
        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a precise job description analysis service."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
                "max_tokens": 3000,
                "chat_template_kwargs": {"enable_thinking": False},
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "jd_extraction",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "jobTitle": {"type": "string"},
                                "experienceRequired": {"type": "string"},
                                "educationRequired": {"type": "string"},
                                "skills": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "name": {"type": "string"},
                                            "importance": {
                                                "type": "string",
                                                "enum": ["HIGH", "MEDIUM", "LOW"],
                                            },
                                            "category": {
                                                "type": "string",
                                                "enum": ["technical", "tool", "soft", "domain"],
                                            },
                                        },
                                        "required": ["name", "importance", "category"],
                                    },
                                },
                            },
                            "required": ["jobTitle", "experienceRequired", "educationRequired", "skills"],
                        },
                    },
                },
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        message = payload["choices"][0]["message"]
        content = message.get("content") or ""
        if not content.strip():
            raise ValueError("LM Studio returned no answer content.")
        if payload["choices"][0].get("finish_reason") == "length":
            raise ValueError(
                "LM Studio truncated the JSON response; reduce JD size or increase max_tokens."
            )
    except requests.RequestException as error:
        detail = response.text[:300].strip() if response is not None else str(error)
        raise RuntimeError(f"LM Studio connection/request failed: {detail}") from error
    except (ValueError, KeyError, IndexError, TypeError) as error:
        detail = response.text[:300].strip() if response is not None else str(error)
        raise RuntimeError(f"LM Studio returned an invalid response: {detail}") from error
    try:
        return _normalize_jd(_json_from_content(content))
    except ValueError as error:
        raise RuntimeError(f"LM Studio returned invalid JD JSON: {error}") from error


# ---------------------------------------------------------------------------
# Candidate–Job Matcher
# ---------------------------------------------------------------------------

def _normalize_match(value: dict[str, Any]) -> dict[str, Any]:
    """Validate and clean the raw LLM match output. Enforces the experience hard gate."""

    def _importance(v: object) -> str:
        s = _string(v).upper()
        return s if s in {"HIGH", "MEDIUM", "LOW"} else "MEDIUM"

    experience_met: bool = bool(value.get("experienceMet", True))
    education_met: bool = bool(value.get("educationMet", True))

    # Hard gate: if experience is not met, force score to 0.
    raw_score = value.get("overallScore", 0)
    try:
        overall_score = max(0, min(100, int(round(float(raw_score)))))
    except (TypeError, ValueError):
        overall_score = 0
    if not experience_met:
        overall_score = 0

    matched_skills = []
    for item in value.get("matchedSkills", []):
        if not isinstance(item, dict):
            continue
        name = _string(item.get("name"))
        if not name:
            continue
        try:
            confidence = max(0.0, min(1.0, float(item.get("candidateConfidence", 0.8))))
        except (TypeError, ValueError):
            confidence = 0.8
        matched_skills.append({
            "name": name,
            "normalizedName": re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"),
            "importance": _importance(item.get("importance")),
            "candidateConfidence": confidence,
        })

    missing_skills = []
    for item in value.get("missingSkills", []):
        if not isinstance(item, dict):
            continue
        name = _string(item.get("name"))
        if not name:
            continue
        missing_skills.append({
            "name": name,
            "normalizedName": re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"),
            "importance": _importance(item.get("importance")),
        })

    return {
        "overallScore": overall_score,
        "experienceMet": experience_met,
        "educationMet": education_met,
        "matchedSkills": matched_skills,
        "missingSkills": missing_skills,
        "summary": _string(value.get("summary")),
    }


def match_candidate_with_lm_studio(
    candidate: dict[str, Any],
    job_requirements: dict[str, Any],
) -> dict[str, Any]:
    """Score a candidate against job requirements using the LLM.

    ``candidate``        — the ``resume`` object returned by the parser.
    ``job_requirements`` — the full response from ``extract_jd_skills_with_lm_studio``.

    Returns overallScore (0–100), experienceMet, educationMet,
    matchedSkills, missingSkills, and a plain-English summary.
    Experience is a hard gate: if not met, overallScore is forced to 0.
    """
    base_url = os.getenv("LM_STUDIO_BASE_URL", DEFAULT_BASE_URL).strip()
    url = os.getenv("LM_STUDIO_URL", "").strip()
    if not url:
        url = re.sub(r"/models/?$", "/chat/completions", base_url)
    model = os.getenv("LM_STUDIO_MODEL", DEFAULT_MODEL).strip()
    timeout = float(os.getenv("LM_STUDIO_TIMEOUT", "90"))

    # Build compact summaries so we don't blast the context window.
    candidate_summary = {
        "name": candidate.get("name", ""),
        "yearsOfExperience": candidate.get("years_of_experience", 0),
        "education": [
            {"degree": e.get("degree", ""), "institution": e.get("institution", "")}
            for e in candidate.get("education", [])
        ],
        "skills": [
            {"name": s.get("name", ""), "confidence": s.get("confidence", 0.8)}
            for s in candidate.get("skills", [])
        ],
    }

    job_summary = {
        "jobTitle": job_requirements.get("jobTitle", ""),
        "experienceRequired": job_requirements.get("experienceRequired", ""),
        "educationRequired": job_requirements.get("educationRequired", ""),
        "skills": [
            {
                "name": s.get("name", ""),
                "importance": s.get("importance", "MEDIUM"),
                "category": s.get("category", "technical"),
            }
            for s in job_requirements.get("skills", [])
        ],
    }

    output_schema = {
        "experienceMet": True,
        "educationMet": True,
        "overallScore": 0,
        "matchedSkills": [
            {"name": "", "importance": "HIGH | MEDIUM | LOW", "candidateConfidence": 0.0}
        ],
        "missingSkills": [
            {"name": "", "importance": "HIGH | MEDIUM | LOW"}
        ],
        "summary": "",
    }

    prompt = (
        "You are a hiring intelligence system. Score how well the CANDIDATE matches the JOB REQUIREMENTS.\n\n"
        "SCORING RULES:\n"
        "1. Experience gate (hard rule): if the candidate's yearsOfExperience is LESS than the minimum "
        "required years, set experienceMet=false and overallScore=0. No further scoring needed.\n"
        "2. If experience IS met, compute overallScore (0–100) as follows:\n"
        "   - Skills (70%): for each required skill, check if it appears in the candidate's skills. "
        "Weight matched skills by their importance (HIGH=3, MEDIUM=2, LOW=1) and multiply by the "
        "candidate's confidence for that skill. Divide by the maximum possible weighted score.\n"
        "   - Education (15%): full marks if candidate meets educationRequired, partial if related, 0 if unrelated or not stated.\n"
        "   - Experience surplus (15%): proportional bonus for exceeding the minimum experience requirement.\n"
        "3. matchedSkills: required skills the candidate has (include candidateConfidence from their profile).\n"
        "4. missingSkills: required skills the candidate is missing entirely.\n"
        "5. summary: one concise sentence explaining the result (mention experience gap if not met).\n\n"
        f"CANDIDATE:\n{json.dumps(candidate_summary, ensure_ascii=True)}\n\n"
        f"JOB REQUIREMENTS:\n{json.dumps(job_summary, ensure_ascii=True)}\n\n"
        f"Return ONLY a JSON object matching this schema:\n{json.dumps(output_schema, ensure_ascii=True)}"
    )

    response = None
    try:
        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a precise candidate evaluation service."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
                "max_tokens": 3000,
                "chat_template_kwargs": {"enable_thinking": False},
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "match_result",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "experienceMet": {"type": "boolean"},
                                "educationMet": {"type": "boolean"},
                                "overallScore": {"type": "number"},
                                "matchedSkills": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "name": {"type": "string"},
                                            "importance": {
                                                "type": "string",
                                                "enum": ["HIGH", "MEDIUM", "LOW"],
                                            },
                                            "candidateConfidence": {"type": "number"},
                                        },
                                        "required": ["name", "importance", "candidateConfidence"],
                                    },
                                },
                                "missingSkills": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "name": {"type": "string"},
                                            "importance": {
                                                "type": "string",
                                                "enum": ["HIGH", "MEDIUM", "LOW"],
                                            },
                                        },
                                        "required": ["name", "importance"],
                                    },
                                },
                                "summary": {"type": "string"},
                            },
                            "required": [
                                "experienceMet", "educationMet", "overallScore",
                                "matchedSkills", "missingSkills", "summary",
                            ],
                        },
                    },
                },
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        message = payload["choices"][0]["message"]
        content = message.get("content") or ""
        if not content.strip():
            raise ValueError("LM Studio returned no answer content.")
        if payload["choices"][0].get("finish_reason") == "length":
            raise ValueError(
                "LM Studio truncated the match JSON; increase max_tokens."
            )
    except requests.RequestException as error:
        detail = response.text[:300].strip() if response is not None else str(error)
        raise RuntimeError(f"LM Studio connection/request failed: {detail}") from error
    except (ValueError, KeyError, IndexError, TypeError) as error:
        detail = response.text[:300].strip() if response is not None else str(error)
        raise RuntimeError(f"LM Studio returned an invalid response: {detail}") from error
    try:
        return _normalize_match(_json_from_content(content))
    except ValueError as error:
        raise RuntimeError(f"LM Studio returned invalid match JSON: {error}") from error
