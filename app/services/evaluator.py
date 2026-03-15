"""Phase 5: Evaluate completed round, produce report and update progress."""
from __future__ import annotations

import json

from app.llm.client import call_claude_json
from app.llm.prompts import EVALUATION_PROMPT, EVALUATION_SYSTEM
from app.models.progress import (
    NextRoundGuidance,
    ProgressReport,
    Strength,
    TopicMastery,
    Weakness,
)
from app.models.question import QuizState
from app.models.round_report import QuestionEvaluation, RoundReport, RoundSummary
from app.config import settings
from app.storage.documents import (
    delete_quiz_state,
    load_profile,
    load_progress,
    save_progress,
    save_round_report,
)


async def evaluate_round(state: QuizState) -> tuple[RoundReport, ProgressReport]:
    """Evaluate a completed round and update progress."""
    if not state.completed:
        raise ValueError("Cannot evaluate an incomplete round")

    profile = load_profile(state.job_id)
    if not profile:
        raise ValueError(f"No profile found for job {state.job_id}")

    progress = load_progress(state.job_id)
    progress_json = progress.model_dump_json(indent=2) if progress else "{}"

    # Build Q&A pairs for evaluation (include expected answers)
    qa_pairs = []
    for q in state.questions:
        answer = next(
            (a for a in state.answers if a.question_id == q.id), None
        )
        qa_pairs.append({
            "question": {
                "id": q.id,
                "topic": q.topic,
                "subtopic": q.subtopic,
                "type": q.type,
                "title": q.title,
                "body": q.body,
                "expected_answer": q.expected_answer.model_dump(),
            },
            "user_answer": answer.model_dump() if answer else {"answer_text": "(no answer)", "code": ""},
        })

    prompt = EVALUATION_PROMPT.format(
        profile_json=profile.model_dump_json(indent=2),
        progress_json=progress_json,
        qa_json=json.dumps(qa_pairs, indent=2),
    )

    data = await call_claude_json(
        prompt,
        system=EVALUATION_SYSTEM,
        model=settings.eval_model,
        timeout=180,
    )

    # Build round report
    evaluations = [
        QuestionEvaluation(**e) for e in data.get("evaluations", [])
    ]
    summary_data = data.get("summary", {})
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
        job_id=state.job_id,
        round_number=state.round_number,
        evaluations=evaluations,
        summary=summary,
    )
    save_round_report(report)

    # Build updated progress
    up = data.get("updated_progress", {})
    new_progress = ProgressReport(
        job_id=state.job_id,
        total_rounds=state.round_number,
        overall_score=up.get("overall_score", summary.overall_score),
        topic_mastery=[TopicMastery(**t) for t in up.get("topic_mastery", [])],
        persistent_weaknesses=[Weakness(**w) for w in up.get("persistent_weaknesses", [])],
        demonstrated_strengths=[Strength(**s) for s in up.get("demonstrated_strengths", [])],
        next_round_guidance=NextRoundGuidance(**up.get("next_round_guidance", {})),
        score_history=up.get("score_history", [summary.overall_score]),
    )
    save_progress(new_progress)

    # Clean up active quiz
    delete_quiz_state(state.job_id)

    return report, new_progress
