from __future__ import annotations

import uuid
from pathlib import Path

from app.config import settings
from app.models.profile import JobProfile
from app.models.progress import ProgressReport
from app.models.question import QuizState
from app.models.round_report import RoundReport


import re

_JOB_ID_RE = re.compile(r"^[a-f0-9]{12}$")


def _validate_job_id(job_id: str) -> None:
    if not _JOB_ID_RE.match(job_id):
        raise ValueError(f"Invalid job_id: {job_id!r}")


def _job_dir(job_id: str) -> Path:
    _validate_job_id(job_id)
    return settings.jobs_dir / job_id


def _rounds_dir(job_id: str, *, create: bool = False) -> Path:
    d = _job_dir(job_id) / "rounds"
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def new_job_id() -> str:
    return uuid.uuid4().hex[:12]


# ── Profile ─────────────────────────────────────────────────────────────

def save_profile(profile: JobProfile) -> Path:
    d = _job_dir(profile.job_id)
    d.mkdir(parents=True, exist_ok=True)
    p = d / "profile.json"
    p.write_text(profile.model_dump_json(indent=2))
    return p


def load_profile(job_id: str) -> JobProfile | None:
    p = _job_dir(job_id) / "profile.json"
    if not p.exists():
        return None
    return JobProfile.model_validate_json(p.read_text())


# ── Progress ─────────────────────────────────────────────────────────────

def save_progress(progress: ProgressReport) -> Path:
    d = _job_dir(progress.job_id)
    d.mkdir(parents=True, exist_ok=True)
    p = d / "progress.json"
    p.write_text(progress.model_dump_json(indent=2))
    return p


def load_progress(job_id: str) -> ProgressReport | None:
    p = _job_dir(job_id) / "progress.json"
    if not p.exists():
        return None
    return ProgressReport.model_validate_json(p.read_text())


# ── Round Reports ────────────────────────────────────────────────────────

def save_round_report(report: RoundReport) -> Path:
    d = _rounds_dir(report.job_id, create=True)
    p = d / f"round_{report.round_number:03d}.json"
    p.write_text(report.model_dump_json(indent=2))
    return p


def load_round_report(job_id: str, round_number: int) -> RoundReport | None:
    p = _job_dir(job_id) / "rounds" / f"round_{round_number:03d}.json"
    if not p.exists():
        return None
    return RoundReport.model_validate_json(p.read_text())


def get_latest_round_number(job_id: str) -> int:
    d = _job_dir(job_id) / "rounds"
    if not d.exists():
        return 0
    files = sorted(d.glob("round_*.json"))
    if not files:
        return 0
    return int(files[-1].stem.split("_")[1])


# ── Quiz State (temporary, active round) ─────────────────────────────────

def save_quiz_state(state: QuizState) -> Path:
    d = _job_dir(state.job_id)
    d.mkdir(parents=True, exist_ok=True)
    p = d / "active_quiz.json"
    p.write_text(state.model_dump_json(indent=2))
    return p


def load_quiz_state(job_id: str) -> QuizState | None:
    p = _job_dir(job_id) / "active_quiz.json"
    if not p.exists():
        return None
    return QuizState.model_validate_json(p.read_text())


def delete_quiz_state(job_id: str) -> None:
    p = _job_dir(job_id) / "active_quiz.json"
    p.unlink(missing_ok=True)


# ── Job listing ──────────────────────────────────────────────────────────

def list_jobs() -> list[dict]:
    settings.ensure_dirs()
    jobs = []
    for d in sorted(settings.jobs_dir.iterdir()):
        if d.is_dir():
            profile = load_profile(d.name)
            if profile:
                jobs.append({
                    "job_id": profile.job_id,
                    "company": profile.company.name,
                    "role": profile.role.title,
                    "finalized": profile.finalized,
                    "rounds": get_latest_round_number(d.name),
                })
    return jobs
