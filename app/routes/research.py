from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.research import finalize_profile, research_job
from app.storage.documents import list_jobs, load_profile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["research"])


class ResearchRequest(BaseModel):
    url: str


class FinalizeRequest(BaseModel):
    answers: dict[str, str]


@router.post("/research")
async def start_research(req: ResearchRequest):
    try:
        profile = await research_job(req.url)
    except (TimeoutError, RuntimeError) as e:
        logger.error("LLM error in research: %s", e)
        raise HTTPException(502, f"Research failed: {e}")

    return {
        "job_id": profile.job_id,
        "company": profile.company.model_dump(),
        "role": profile.role.model_dump(),
        "clarifying_questions": [q.model_dump() for q in profile.clarifying_questions],
    }


@router.post("/{job_id}/finalize")
async def finalize(job_id: str, req: FinalizeRequest):
    profile = load_profile(job_id)
    if not profile:
        raise HTTPException(404, "Job not found")
    if profile.finalized:
        raise HTTPException(400, "Profile already finalized")

    try:
        profile = await finalize_profile(profile, req.answers)
    except (TimeoutError, RuntimeError) as e:
        logger.error("LLM error in finalize: %s", e)
        raise HTTPException(502, f"Finalization failed: {e}")

    return {"job_id": profile.job_id, "finalized": True, "profile": profile.model_dump()}


@router.get("")
async def get_jobs():
    return list_jobs()


@router.get("/{job_id}/profile")
async def get_profile(job_id: str):
    profile = load_profile(job_id)
    if not profile:
        raise HTTPException(404, "Job not found")
    return profile.model_dump()
