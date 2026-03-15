"""Phase 4: Quiz delivery — pure app logic, no LLM calls."""
from __future__ import annotations

import asyncio

from app.models.question import QuizState, UserAnswer
from app.services.code_executor import run_test_case
from app.storage.documents import save_quiz_state


def get_question_for_user(state: QuizState, question_index: int) -> dict:
    """Return question data safe for the user (no expected answers)."""
    if question_index < 0 or question_index >= len(state.questions):
        raise IndexError(f"Question index {question_index} out of range")

    q = state.questions[question_index]
    visible_tests = [
        {"input": tc.input, "expected_output": tc.expected_output, "description": tc.description}
        for tc in q.test_cases
        if not tc.is_hidden
    ]

    return {
        "id": q.id,
        "index": question_index,
        "topic": q.topic,
        "subtopic": q.subtopic,
        "difficulty": q.difficulty,
        "type": q.type,
        "title": q.title,
        "body": q.body,
        "hints": q.hints,
        "test_cases": visible_tests,
        "time_limit_minutes": q.time_limit_minutes,
        "total_questions": len(state.questions),
    }


async def submit_answer(
    state: QuizState,
    question_index: int,
    answer_text: str = "",
    code: str = "",
    language: str = "python",
    time_spent: int | None = None,
) -> dict:
    """Record answer and run test cases for coding questions."""
    if question_index < 0 or question_index >= len(state.questions):
        raise IndexError(f"Question index {question_index} out of range")

    q = state.questions[question_index]
    test_results = None

    # Run test cases concurrently for coding questions
    if q.type == "coding" and code and q.test_cases:
        results = await asyncio.gather(
            *(run_test_case(code, tc.input, tc.expected_output) for tc in q.test_cases)
        )
        test_results = []
        for tc, result in zip(q.test_cases, results):
            result["is_hidden"] = tc.is_hidden
            test_results.append(result)

    answer = UserAnswer(
        question_id=q.id,
        answer_text=answer_text,
        code=code,
        language=language,
        test_results=test_results,
        time_spent_seconds=time_spent,
    )

    # Replace existing answer or append
    existing_idx = None
    for i, a in enumerate(state.answers):
        if a.question_id == q.id:
            existing_idx = i
            break

    if existing_idx is not None:
        state.answers[existing_idx] = answer
    else:
        state.answers.append(answer)

    # Advance to next question
    if question_index + 1 < len(state.questions):
        state.current_question_index = question_index + 1
    else:
        state.completed = True

    save_quiz_state(state)

    # Return visible test results only
    visible_results = None
    if test_results:
        visible_results = [r for r in test_results if not r.get("is_hidden")]

    return {
        "question_id": q.id,
        "test_results": visible_results,
        "completed": state.completed,
        "next_question_index": state.current_question_index,
    }
