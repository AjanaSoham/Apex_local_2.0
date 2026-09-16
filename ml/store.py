"""Local persistence and session helpers for the candidate/recruiter workflow."""

import hashlib
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATABASE_PATH = Path(os.getenv("CANDIDATE_MATCH_DB", Path(__file__).with_name("candidate_match.db")))


@contextmanager
def _connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize() -> None:
    with _connection() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('candidate', 'recruiter')), created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS resumes (
                id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, resume_text TEXT NOT NULL,
                language TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY, recruiter_id INTEGER NOT NULL, title TEXT NOT NULL,
                description TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(recruiter_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL, candidate_id INTEGER NOT NULL, resume_id INTEGER NOT NULL,
                analysis_json TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(job_id, candidate_id),
                FOREIGN KEY(job_id) REFERENCES jobs(id), FOREIGN KEY(candidate_id) REFERENCES users(id),
                FOREIGN KEY(resume_id) REFERENCES resumes(id)
            );
        """)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    salt_hex, _ = stored.split("$", 1)
    return secrets.compare_digest(_hash_password(password, bytes.fromhex(salt_hex)), stored)


def register(email: str, password: str, role: str) -> dict:
    try:
        with _connection() as db:
            cursor = db.execute("INSERT INTO users(email, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                                (email.lower().strip(), _hash_password(password), role, _now()))
            return {"id": cursor.lastrowid, "email": email.lower().strip(), "role": role}
    except sqlite3.IntegrityError as error:
        raise ValueError("An account with that email already exists.") from error


def login(email: str, password: str) -> dict:
    with _connection() as db:
        user = db.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),)).fetchone()
        if user is None or not _verify_password(password, user["password_hash"]):
            raise PermissionError("Invalid email or password.")
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(hours=12)
        db.execute("INSERT INTO sessions(token_hash, user_id, expires_at) VALUES (?, ?, ?)",
                   (hashlib.sha256(token.encode()).hexdigest(), user["id"], expires.isoformat()))
        return {"access_token": token, "token_type": "bearer", "user": {"id": user["id"], "email": user["email"], "role": user["role"]}}


def current_user(token: str) -> dict:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with _connection() as db:
        row = db.execute("""SELECT users.id, users.email, users.role FROM sessions JOIN users ON users.id = sessions.user_id
                            WHERE sessions.token_hash = ? AND sessions.expires_at > ?""", (token_hash, _now())).fetchone()
    if row is None:
        raise PermissionError("Session is invalid or expired.")
    return dict(row)


def add_resume(user_id: int, text: str, language: str) -> int:
    with _connection() as db:
        return db.execute("INSERT INTO resumes(user_id, resume_text, language, created_at) VALUES (?, ?, ?, ?)",
                          (user_id, text, language, _now())).lastrowid


def add_job(recruiter_id: int, title: str, description: str) -> int:
    with _connection() as db:
        return db.execute("INSERT INTO jobs(recruiter_id, title, description, created_at) VALUES (?, ?, ?, ?)",
                          (recruiter_id, title, description, _now())).lastrowid


def get_job(job_id: int) -> dict | None:
    with _connection() as db:
        row = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return dict(row) if row else None


def get_resume(resume_id: int, user_id: int) -> dict | None:
    with _connection() as db:
        row = db.execute("SELECT * FROM resumes WHERE id = ? AND user_id = ?", (resume_id, user_id)).fetchone()
    return dict(row) if row else None


def add_application(job_id: int, candidate_id: int, resume_id: int, analysis: dict) -> int:
    try:
        with _connection() as db:
            return db.execute("INSERT INTO applications(job_id, candidate_id, resume_id, analysis_json, created_at) VALUES (?, ?, ?, ?, ?)",
                              (job_id, candidate_id, resume_id, json.dumps(analysis), _now())).lastrowid
    except sqlite3.IntegrityError as error:
        raise ValueError("You have already applied to this job.") from error


def jobs_for_recruiter(recruiter_id: int) -> list[dict]:
    with _connection() as db:
        return [dict(row) for row in db.execute("SELECT * FROM jobs WHERE recruiter_id = ? ORDER BY id DESC", (recruiter_id,))]


def candidates_for_job(job_id: int) -> list[dict]:
    with _connection() as db:
        rows = db.execute("""SELECT applications.id AS application_id, users.email AS candidate_email, resumes.language, applications.analysis_json
                             FROM applications JOIN users ON users.id = applications.candidate_id
                             JOIN resumes ON resumes.id = applications.resume_id WHERE applications.job_id = ?""", (job_id,)).fetchall()
    results = [{**dict(row), "analysis": json.loads(row["analysis_json"])} for row in rows]
    return sorted(results, key=lambda item: item["analysis"]["scores"]["overall"], reverse=True)
