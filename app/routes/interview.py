from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.evaluator import evaluate_round
from app.services.question_generator import generate_round
from app.services.quiz_runner import get_question_for_user, submit_answer
from app.storage.documents import load_quiz_state, load_round_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs/{job_id}/rounds", tags=["interview"])


class StartRoundRequest(BaseModel):
    num_questions: int = Field(default=4, ge=1, le=10)


class AnswerRequest(BaseModel):
    answer_text: str = ""
    code: str = ""
    language: str = "python"
    time_spent_seconds: int | None = None


def _require_active_round(job_id: str, round_number: int):
    state = load_quiz_state(job_id)
    if not state or state.round_number != round_number:
        raise HTTPException(404, "No active round found")
    return state


@router.get("/active")
async def get_active_round(job_id: str):
    """Check if there's an in-progress round to resume."""
    state = load_quiz_state(job_id)
    if not state:
        return {"active": False}

    # Figure out which question to show next
    answered_ids = {a.question_id for a in state.answers}
    resume_index = state.current_question_index
    # If current question was already answered, it's accurate; otherwise find first unanswered
    for i, q in enumerate(state.questions):
        if q.id not in answered_ids:
            resume_index = i
            break

    q = get_question_for_user(state, resume_index)
    return {
        "active": True,
        "round_number": state.round_number,
        "total_questions": len(state.questions),
        "answered": len(state.answers),
        "completed": state.completed,
        "current_question": q,
    }


@router.post("/start")
async def start_round(job_id: str, req: StartRoundRequest):
    try:
        state = await generate_round(job_id, req.num_questions)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except (TimeoutError, RuntimeError) as e:
        logger.error("LLM error in start_round: %s", e)
        raise HTTPException(502, f"LLM call failed: {e}")

    q = get_question_for_user(state, 0)
    return {
        "round_number": state.round_number,
        "total_questions": len(state.questions),
        "first_question": q,
    }


@router.get("/{round_number}/question/{q_index}")
async def get_question(job_id: str, round_number: int, q_index: int):
    state = _require_active_round(job_id, round_number)
    try:
        return get_question_for_user(state, q_index)
    except IndexError as e:
        raise HTTPException(404, str(e))


@router.post("/{round_number}/answer/{q_index}")
async def post_answer(
    job_id: str, round_number: int, q_index: int, req: AnswerRequest
):
    state = _require_active_round(job_id, round_number)
    try:
        result = await submit_answer(
            state, q_index,
            answer_text=req.answer_text,
            code=req.code,
            language=req.language,
            time_spent=req.time_spent_seconds,
        )
        return result
    except IndexError as e:
        raise HTTPException(404, str(e))


@router.post("/{round_number}/evaluate")
async def evaluate(job_id: str, round_number: int):
    state = _require_active_round(job_id, round_number)
    if not state.completed:
        raise HTTPException(400, "Round not yet completed — answer all questions first")

    try:
        report, progress = await evaluate_round(state)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except (TimeoutError, RuntimeError) as e:
        logger.error("LLM error in evaluate: %s", e)
        raise HTTPException(502, f"LLM call failed: {e}")

    return {
        "report": report.model_dump(),
        "progress": progress.model_dump(),
    }


@router.get("/{round_number}")
async def get_round(job_id: str, round_number: int):
    report = load_round_report(job_id, round_number)
    if not report:
        raise HTTPException(404, "Round report not found")
    return report.model_dump()
