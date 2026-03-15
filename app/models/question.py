from __future__ import annotations

from pydantic import BaseModel, Field


class TestCase(BaseModel):
    input: str
    expected_output: str
    is_hidden: bool = False
    description: str = ""


class ExpectedAnswer(BaseModel):
    key_points: list[str] = Field(default_factory=list)
    sample_solution: str = ""
    time_complexity: str = ""
    space_complexity: str = ""
    follow_up_questions: list[str] = Field(default_factory=list)


class Question(BaseModel):
    id: int
    topic: str
    subtopic: str = ""
    difficulty: str = "medium"
    type: str = "coding"  # coding, conceptual, system_design, behavioral
    title: str
    body: str
    hints: list[str] = Field(default_factory=list)
    test_cases: list[TestCase] = Field(default_factory=list)
    expected_answer: ExpectedAnswer = Field(default_factory=ExpectedAnswer)
    time_limit_minutes: int = 15


class UserAnswer(BaseModel):
    question_id: int
    answer_text: str = ""
    code: str = ""
    language: str = "python"
    test_results: list[dict] | None = None
    time_spent_seconds: int | None = None


class QuizState(BaseModel):
    job_id: str
    round_number: int
    questions: list[Question] = Field(default_factory=list)
    answers: list[UserAnswer] = Field(default_factory=list)
    current_question_index: int = 0
    started: bool = False
    completed: bool = False
