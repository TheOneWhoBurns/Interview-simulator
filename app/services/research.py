"""Phase 1 & 2: Job research and profile finalization."""
from __future__ import annotations

import json

from app.llm.client import call_claude_json
from app.llm.prompts import (
    FINALIZE_PROMPT,
    FINALIZE_SYSTEM,
    RESEARCH_PROMPT,
    RESEARCH_SYSTEM,
)
from app.models.profile import (
    ClarifyingQuestion,
    Company,
    InterviewFocus,
    InterviewTopic,
    JobProfile,
    Role,
    UserContext,
)
from app.storage.documents import new_job_id, save_profile


async def research_job(url: str) -> JobProfile:
    """Phase 1: Research job listing, return partial profile with clarifying questions."""
    prompt = RESEARCH_PROMPT.format(url=url)
    data = await call_claude_json(
        prompt,
        system=RESEARCH_SYSTEM,
        allowed_tools=["WebSearch", "WebFetch"],
        timeout=180,
    )

    job_id = new_job_id()
    profile = JobProfile(
        job_id=job_id,
        url=url,
        company=Company(**(data.get("company", {}))),
        role=Role(**(data.get("role", {}))),
        interview_focus=_parse_focus(data.get("interview_focus", {})),
        clarifying_questions=[
            ClarifyingQuestion(**q)
            for q in data.get("clarifying_questions", [])
        ],
    )
    save_profile(profile)
    return profile


async def finalize_profile(
    profile: JobProfile, answers: dict[str, str]
) -> JobProfile:
    """Phase 2: Incorporate user answers, adjust topic weights, finalize profile."""
    profile.user_context.clarifying_answers = answers

    prompt = FINALIZE_PROMPT.format(
        profile_json=profile.model_dump_json(indent=2),
        answers_json=json.dumps(answers, indent=2),
    )
    data = await call_claude_json(prompt, system=FINALIZE_SYSTEM, timeout=120)

    # Update fields from LLM response
    if "company" in data:
        profile.company = Company(**data["company"])
    if "role" in data:
        profile.role = Role(**data["role"])
    if "interview_focus" in data:
        profile.interview_focus = _parse_focus(data["interview_focus"])
    if "user_context" in data:
        uc = data["user_context"]
        profile.user_context = UserContext(
            years_experience=uc.get("years_experience"),
            strongest_languages=uc.get("strongest_languages", []),
            weakest_areas=uc.get("weakest_areas", []),
            target_level=uc.get("target_level", ""),
            additional_context=uc.get("additional_context", ""),
            clarifying_answers=answers,
        )

    profile.finalized = True
    profile.clarifying_questions = []  # No longer needed
    save_profile(profile)
    return profile


def _parse_focus(data: dict) -> InterviewFocus:
    topics = [InterviewTopic(**t) for t in data.get("topics", [])]
    return InterviewFocus(
        topics=topics,
        estimated_rounds=data.get("estimated_rounds", 3),
        format_notes=data.get("format_notes", ""),
    )
