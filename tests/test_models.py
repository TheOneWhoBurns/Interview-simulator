"""Test Pydantic models serialize/deserialize correctly."""
import json
from pathlib import Path

from app.models.profile import JobProfile
from app.models.progress import ProgressReport
from app.models.question import Question, QuizState, TestCase, UserAnswer
from app.models.round_report import QuestionEvaluation, RoundReport, RoundSummary

FIXTURES = Path(__file__).parent / "fixtures"


def test_profile_roundtrip():
    raw = (FIXTURES / "sample_profile.json").read_text()
    profile = JobProfile.model_validate_json(raw)
    assert profile.job_id == "test123"
    assert profile.company.name == "Acme Corp"
    assert len(profile.interview_focus.topics) == 4
    assert profile.finalized is True
    # Roundtrip
    restored = JobProfile.model_validate_json(profile.model_dump_json())
    assert restored == profile


def test_progress_roundtrip():
    raw = (FIXTURES / "sample_progress.json").read_text()
    progress = ProgressReport.model_validate_json(raw)
    assert progress.total_rounds == 1
    assert progress.overall_score == 6.5
    assert len(progress.topic_mastery) == 3
    assert progress.next_round_guidance.difficulty_adjustment == "maintain"
    restored = ProgressReport.model_validate_json(progress.model_dump_json())
    assert restored == progress


def test_question_model():
    q = Question(
        id=1,
        topic="Algorithms",
        subtopic="Sorting",
        difficulty="medium",
        type="coding",
        title="Merge Sort",
        body="Implement merge sort",
        test_cases=[
            TestCase(input="[3,1,2]", expected_output="[1,2,3]", description="basic"),
        ],
    )
    data = json.loads(q.model_dump_json())
    assert data["id"] == 1
    assert len(data["test_cases"]) == 1


def test_quiz_state():
    state = QuizState(
        job_id="test123",
        round_number=1,
        questions=[
            Question(id=1, topic="T", title="Q1", body="Body"),
            Question(id=2, topic="T", title="Q2", body="Body"),
        ],
        answers=[UserAnswer(question_id=1, code="def f(): pass")],
        current_question_index=1,
        started=True,
    )
    assert len(state.questions) == 2
    assert state.answers[0].code == "def f(): pass"


def test_round_report():
    report = RoundReport(
        job_id="test123",
        round_number=1,
        evaluations=[
            QuestionEvaluation(
                question_id=1, topic="Algo", score=7.5,
                correctness=0.8, completeness=0.7,
                strengths=["Clean code"], weaknesses=["Missing edge case"],
                feedback="Good attempt.",
            ),
        ],
        summary=RoundSummary(
            overall_score=7.5, total_questions=1, questions_passed=1,
            strongest_topic="Algo", weakest_topic="",
        ),
    )
    data = json.loads(report.model_dump_json())
    assert data["evaluations"][0]["score"] == 7.5
