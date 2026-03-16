"""Phase 3: Generate interview questions based on profile and progress."""
from __future__ import annotations

from app.llm.client import call_claude_json
from app.llm.prompts import (
    QUESTION_GEN_PROMPT,
    QUESTION_GEN_SYSTEM,
    build_guidance_section,
    build_progress_section,
)
from app.models.question import ExpectedAnswer, Question, QuizState, TestCase
from app.storage.documents import (
    get_latest_round_number,
    load_profile,
    load_progress,
    save_quiz_state,
)


async def generate_round(job_id: str, num_questions: int = 4) -> QuizState:
    """Generate questions for a new interview round."""
    profile = load_profile(job_id)
    if not profile:
        raise ValueError(f"No profile found for job {job_id}")
    if not profile.finalized:
        raise ValueError("Profile must be finalized before starting a round")

    progress = load_progress(job_id)
    progress_json = progress.model_dump_json(indent=2) if progress else None

    prompt = QUESTION_GEN_PROMPT.format(
        profile_json=profile.model_dump_json(indent=2),
        progress_section=build_progress_section(progress_json),
        num_questions=num_questions,
        guidance_section=build_guidance_section(progress_json),
    )

    data = await call_claude_json(
        prompt, system=QUESTION_GEN_SYSTEM, timeout=300
    )

    questions = []
    for q_data in data.get("questions", []):
        test_cases = [TestCase(**tc) for tc in q_data.get("test_cases", [])]
        expected = ExpectedAnswer(**q_data.get("expected_answer", {}))
        q = Question(
            id=q_data["id"],
            topic=q_data.get("topic", "General"),
            subtopic=q_data.get("subtopic", ""),
            difficulty=q_data.get("difficulty", "medium"),
            type=q_data.get("type", "coding"),
            title=q_data.get("title", ""),
            body=q_data.get("body", ""),
            hints=q_data.get("hints", []),
            test_cases=test_cases,
            expected_answer=expected,
            time_limit_minutes=q_data.get("time_limit_minutes", 15),
        )
        questions.append(q)

    round_number = get_latest_round_number(job_id) + 1
    state = QuizState(
        job_id=job_id,
        round_number=round_number,
        questions=questions,
        started=True,
    )
    save_quiz_state(state)
    return state
