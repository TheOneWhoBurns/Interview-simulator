from __future__ import annotations

from pydantic import BaseModel, Field


class Company(BaseModel):
    name: str = ""
    industry: str = ""
    size: str = ""
    culture_notes: str = ""
    tech_stack: list[str] = Field(default_factory=list)


class Role(BaseModel):
    title: str = ""
    level: str = ""
    team: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)


class InterviewTopic(BaseModel):
    topic: str
    weight: float = Field(ge=0, le=1, description="Relative importance 0-1")
    subtopics: list[str] = Field(default_factory=list)
    expected_difficulty: str = "medium"


class InterviewFocus(BaseModel):
    topics: list[InterviewTopic] = Field(default_factory=list)
    estimated_rounds: int = 3
    format_notes: str = ""


class ClarifyingQuestion(BaseModel):
    id: str
    question: str
    context: str = ""


class UserContext(BaseModel):
    years_experience: int | None = None
    strongest_languages: list[str] = Field(default_factory=list)
    weakest_areas: list[str] = Field(default_factory=list)
    target_level: str = ""
    additional_context: str = ""
    clarifying_answers: dict[str, str] = Field(default_factory=dict)


class JobProfile(BaseModel):
    job_id: str
    url: str = ""
    company: Company = Field(default_factory=Company)
    role: Role = Field(default_factory=Role)
    interview_focus: InterviewFocus = Field(default_factory=InterviewFocus)
    user_context: UserContext = Field(default_factory=UserContext)
    clarifying_questions: list[ClarifyingQuestion] = Field(default_factory=list)
    finalized: bool = False
