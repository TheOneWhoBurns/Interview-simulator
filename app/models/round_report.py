from __future__ import annotations

from pydantic import BaseModel, Field


class QuestionEvaluation(BaseModel):
    question_id: int
    topic: str
    subtopic: str = ""
    score: float = Field(ge=0, le=10)
    max_score: float = 10.0
    correctness: float = Field(ge=0, le=1)
    completeness: float = Field(ge=0, le=1)
    code_quality: float | None = None
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    feedback: str = ""
    missed_key_points: list[str] = Field(default_factory=list)


class RoundSummary(BaseModel):
    overall_score: float = Field(ge=0, le=10)
    total_questions: int = 0
    questions_passed: int = 0
    strongest_topic: str = ""
    weakest_topic: str = ""
    key_takeaways: list[str] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)


class RoundReport(BaseModel):
    job_id: str
    round_number: int
    evaluations: list[QuestionEvaluation] = Field(default_factory=list)
    summary: RoundSummary = Field(default_factory=RoundSummary)
