"""SSE streaming endpoints for long-running LLM operations."""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.llm.client import call_claude_json_streaming
from app.llm.prompts import (
    EVALUATION_PROMPT,
    EVALUATION_SYSTEM,
    FINALIZE_PROMPT,
    FINALIZE_SYSTEM,
    QUESTION_GEN_PROMPT,
    QUESTION_GEN_SYSTEM,
    RESEARCH_PROMPT,
    RESEARCH_SYSTEM,
    build_guidance_section,
    build_progress_section,
)
from app.config import settings
from app.models.profile import (
    ClarifyingQuestion, Company, InterviewFocus, InterviewTopic,
    JobProfile, Role, UserContext,
)
from app.models.progress import (
    NextRoundGuidance, ProgressReport, Strength, TopicMastery, Weakness,
)
from app.models.question import ExpectedAnswer, Question, QuizState, TestCase
from app.models.round_report import QuestionEvaluation, RoundReport, RoundSummary
from app.services.quiz_runner import get_question_for_user
from app.storage.documents import (
    delete_quiz_state, get_latest_round_number, load_profile,
    load_progress, load_quiz_state, new_job_id, save_profile,
    save_progress, save_quiz_state, save_round_report,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stream", tags=["stream"])


def _sse(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


# ── Research (Phase 1) ──────────────────────────────────────────────────


class StreamResearchRequest(BaseModel):
    url: str


@router.post("/jobs/research")
async def stream_research(req: StreamResearchRequest):
    async def generate():
        yield _sse("status", "Starting job research...")

        prompt = RESEARCH_PROMPT.format(url=req.url)

        result_data = None
        async for etype, msg in call_claude_json_streaming(
            prompt,
            system=RESEARCH_SYSTEM,
            allowed_tools=["WebSearch", "WebFetch"],
            timeout=600,
        ):
            if etype == "error":
                yield _sse("error", msg)
                return
            elif etype == "result":
                result_data = json.loads(msg)
            else:
                yield _sse(etype, msg)

        if not result_data:
            yield _sse("error", "No result from research")
            return

        yield _sse("status", "Building profile...")

        try:
            job_id = new_job_id()
            profile = JobProfile(
                job_id=job_id,
                url=req.url,
                company=Company(**(result_data.get("company", {}))),
                role=Role(**(result_data.get("role", {}))),
                interview_focus=_parse_focus(result_data.get("interview_focus", {})),
                clarifying_questions=[
                    ClarifyingQuestion(**q)
                    for q in result_data.get("clarifying_questions", [])
                ],
            )
            save_profile(profile)

            yield _sse("done", json.dumps({
                "job_id": profile.job_id,
                "company": profile.company.model_dump(),
                "role": profile.role.model_dump(),
                "clarifying_questions": [q.model_dump() for q in profile.clarifying_questions],
            }))
        except Exception as exc:
            logger.error("Failed to build profile: %s", exc)
            yield _sse("error", f"Failed to build profile: {exc}")

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── Finalize (Phase 2) ──────────────────────────────────────────────────


class StreamFinalizeRequest(BaseModel):
    answers: dict[str, str]


@router.post("/jobs/{job_id}/finalize")
async def stream_finalize(job_id: str, req: StreamFinalizeRequest):
    profile = load_profile(job_id)
    if not profile:
        raise HTTPException(404, "Job not found")

    async def generate():
        yield _sse("status", "Personalizing your profile...")

        profile.user_context.clarifying_answers = req.answers
        prompt = FINALIZE_PROMPT.format(
            profile_json=profile.model_dump_json(indent=2),
            answers_json=json.dumps(req.answers, indent=2),
        )

        result_data = None
        async for etype, msg in call_claude_json_streaming(
            prompt, system=FINALIZE_SYSTEM, timeout=300,
        ):
            if etype == "error":
                yield _sse("error", msg)
                return
            elif etype == "result":
                result_data = json.loads(msg)
            else:
                yield _sse(etype, msg)

        if not result_data:
            yield _sse("error", "No result from finalization")
            return

        yield _sse("status", "Saving profile...")

        try:
            if "company" in result_data:
                profile.company = Company(**result_data["company"])
            if "role" in result_data:
                profile.role = Role(**result_data["role"])
            if "interview_focus" in result_data:
                profile.interview_focus = _parse_focus(result_data["interview_focus"])
            if "user_context" in result_data:
                uc = result_data["user_context"]
                profile.user_context = UserContext(
                    years_experience=uc.get("years_experience"),
                    strongest_languages=uc.get("strongest_languages", []),
                    weakest_areas=uc.get("weakest_areas", []),
                    target_level=uc.get("target_level", ""),
                    additional_context=uc.get("additional_context", ""),
                    clarifying_answers=req.answers,
                )
            profile.finalized = True
            profile.clarifying_questions = []
            save_profile(profile)

            yield _sse("done", json.dumps({
                "job_id": profile.job_id,
                "finalized": True,
                "profile": profile.model_dump(),
            }))
        except Exception as exc:
            yield _sse("error", f"Failed to finalize: {exc}")

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── Start Round (Phase 3) ───────────────────────────────────────────────


class StreamStartRoundRequest(BaseModel):
    num_questions: int = Field(default=4, ge=1, le=10)


@router.post("/jobs/{job_id}/rounds/start")
async def stream_start_round(job_id: str, req: StreamStartRoundRequest):
    profile = load_profile(job_id)
    if not profile:
        raise HTTPException(404, "Job not found")
    if not profile.finalized:
        raise HTTPException(400, "Profile must be finalized first")

    async def generate():
        yield _sse("status", "Generating interview questions...")

        progress = load_progress(job_id)
        progress_json = progress.model_dump_json(indent=2) if progress else None

        prompt = QUESTION_GEN_PROMPT.format(
            profile_json=profile.model_dump_json(indent=2),
            progress_section=build_progress_section(progress_json),
            num_questions=req.num_questions,
            guidance_section=build_guidance_section(progress_json),
        )

        result_data = None
        async for etype, msg in call_claude_json_streaming(
            prompt, system=QUESTION_GEN_SYSTEM, timeout=300,
        ):
            if etype == "error":
                yield _sse("error", msg)
                return
            elif etype == "result":
                result_data = json.loads(msg)
            else:
                yield _sse(etype, msg)

        if not result_data:
            yield _sse("error", "No questions generated")
            return

        yield _sse("status", "Preparing quiz...")

        try:
            questions = []
            for q_data in result_data.get("questions", []):
                test_cases = [TestCase(**tc) for tc in q_data.get("test_cases", [])]
                expected = ExpectedAnswer(**q_data.get("expected_answer", {}))
                q = Question(
                    id=q_data.get("id", len(questions) + 1),
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
                job_id=job_id, round_number=round_number,
                questions=questions, started=True,
            )
            save_quiz_state(state)

            first_q = get_question_for_user(state, 0)
            yield _sse("done", json.dumps({
                "round_number": state.round_number,
                "total_questions": len(state.questions),
                "first_question": first_q,
            }))
        except Exception as exc:
            logger.error("Failed to build quiz: %s", exc)
            yield _sse("error", f"Failed to build quiz: {exc}")

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── Evaluate (Phase 5) ──────────────────────────────────────────────────


@router.post("/jobs/{job_id}/rounds/{round_number}/evaluate")
async def stream_evaluate(job_id: str, round_number: int):
    state = load_quiz_state(job_id)
    if not state or state.round_number != round_number:
        raise HTTPException(404, "No active round found")
    if not state.completed:
        raise HTTPException(400, "Round not complete")

    profile = load_profile(state.job_id)
    if not profile:
        raise HTTPException(404, "Job not found")

    async def generate():
        yield _sse("status", "Evaluating your answers...")

        progress = load_progress(state.job_id)
        progress_json = progress.model_dump_json(indent=2) if progress else "{}"

        qa_pairs = []
        for q in state.questions:
            answer = next(
                (a for a in state.answers if a.question_id == q.id), None
            )
            qa_pairs.append({
                "question": {
                    "id": q.id, "topic": q.topic, "subtopic": q.subtopic,
                    "type": q.type, "title": q.title, "body": q.body,
                    "expected_answer": q.expected_answer.model_dump(),
                },
                "user_answer": answer.model_dump() if answer else {
                    "answer_text": "(no answer)", "code": "",
                },
            })

        prompt = EVALUATION_PROMPT.format(
            profile_json=profile.model_dump_json(indent=2),
            progress_json=progress_json,
            qa_json=json.dumps(qa_pairs, indent=2),
        )

        result_data = None
        async for etype, msg in call_claude_json_streaming(
            prompt, system=EVALUATION_SYSTEM,
            model=settings.eval_model, timeout=600,
        ):
            if etype == "error":
                yield _sse("error", msg)
                return
            elif etype == "result":
                result_data = json.loads(msg)
            else:
                yield _sse(etype, msg)

        if not result_data:
            yield _sse("error", "No evaluation received")
            return

        yield _sse("status", "Building report...")

        try:
            evaluations = [
                QuestionEvaluation(**e) for e in result_data.get("evaluations", [])
            ]
            summary_data = result_data.get("summary", {})
            summary = RoundSummary(
                overall_score=summary_data.get("overall_score", 0),
                total_questions=summary_data.get("total_questions", len(state.questions)),
                questions_passed=summary_data.get("questions_passed", 0),
                strongest_topic=summary_data.get("strongest_topic", ""),
                weakest_topic=summary_data.get("weakest_topic", ""),
                key_takeaways=summary_data.get("key_takeaways", []),
                improvement_suggestions=summary_data.get("improvement_suggestions", []),
            )
            report = RoundReport(
                job_id=state.job_id, round_number=state.round_number,
                evaluations=evaluations, summary=summary,
            )
            save_round_report(report)

            up = result_data.get("updated_progress", {})
            new_progress = ProgressReport(
                job_id=state.job_id, total_rounds=state.round_number,
                overall_score=up.get("overall_score", summary.overall_score),
                topic_mastery=[TopicMastery(**t) for t in up.get("topic_mastery", [])],
                persistent_weaknesses=[Weakness(**w) for w in up.get("persistent_weaknesses", [])],
                demonstrated_strengths=[Strength(**s) for s in up.get("demonstrated_strengths", [])],
                next_round_guidance=NextRoundGuidance(**up.get("next_round_guidance", {})),
                score_history=up.get("score_history", [summary.overall_score]),
            )
            save_progress(new_progress)
            delete_quiz_state(state.job_id)

            yield _sse("done", json.dumps({
                "report": report.model_dump(),
                "progress": new_progress.model_dump(),
            }))
        except Exception as exc:
            logger.error("Failed to build report: %s", exc)
            yield _sse("error", f"Failed to build report: {exc}")

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── Shared helpers ───────────────────────────────────────────────────────

def _parse_focus(data: dict) -> InterviewFocus:
    topics = [InterviewTopic(**t) for t in data.get("topics", [])]
    return InterviewFocus(
        topics=topics,
        estimated_rounds=data.get("estimated_rounds", 3),
        format_notes=data.get("format_notes", ""),
    )
