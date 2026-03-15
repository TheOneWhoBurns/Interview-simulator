from __future__ import annotations

from pydantic import BaseModel, Field


class TopicMastery(BaseModel):
    topic: str
    subtopic: str = ""
    score: float = Field(ge=0, le=10)
    attempts: int = 0
    trend: str = "stable"  # improving, declining, stable


class Weakness(BaseModel):
    area: str
    description: str
    severity: str = "medium"  # low, medium, high
    first_seen_round: int = 1
    still_active: bool = True


class Strength(BaseModel):
    area: str
    description: str
    confidence: str = "medium"  # low, medium, high


class NextRoundGuidance(BaseModel):
    topic_distribution: dict[str, float] = Field(default_factory=dict)
    difficulty_adjustment: str = "maintain"  # easier, maintain, harder
    priority_areas: list[str] = Field(default_factory=list)
    avoid_topics: list[str] = Field(default_factory=list)
    specific_instructions: str = ""


class ProgressReport(BaseModel):
    job_id: str
    total_rounds: int = 0
    overall_score: float = 0.0
    topic_mastery: list[TopicMastery] = Field(default_factory=list)
    persistent_weaknesses: list[Weakness] = Field(default_factory=list)
    demonstrated_strengths: list[Strength] = Field(default_factory=list)
    next_round_guidance: NextRoundGuidance = Field(default_factory=NextRoundGuidance)
    score_history: list[float] = Field(default_factory=list)
