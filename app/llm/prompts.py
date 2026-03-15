"""Prompt templates for all five LLM phases."""
from __future__ import annotations

# ── Phase 1: Job Research ────────────────────────────────────────────────

RESEARCH_SYSTEM = """\
You are an expert technical recruiter and interview coach. \
You analyze job listings and predict interview content with high accuracy."""

RESEARCH_PROMPT = """\
Research this job listing and analyze it thoroughly.

Job URL: {url}

Visit the URL and analyze the job listing. Then research the company.

Return a JSON object with this exact structure:
{{
  "company": {{
    "name": "string",
    "industry": "string",
    "size": "string (e.g. startup, mid-size, large)",
    "culture_notes": "string",
    "tech_stack": ["string"]
  }},
  "role": {{
    "title": "string",
    "level": "string (e.g. junior, mid, senior, staff)",
    "team": "string",
    "responsibilities": ["string"],
    "required_skills": ["string"],
    "preferred_skills": ["string"]
  }},
  "interview_focus": {{
    "topics": [
      {{
        "topic": "string (e.g. Data Structures, System Design)",
        "weight": 0.0 to 1.0,
        "subtopics": ["string"],
        "expected_difficulty": "easy|medium|hard"
      }}
    ],
    "estimated_rounds": 3,
    "format_notes": "string"
  }},
  "clarifying_questions": [
    {{
      "id": "q1",
      "question": "string — question for the candidate to personalize their prep",
      "context": "string — why this matters"
    }}
  ]
}}

Generate 4-6 clarifying questions to understand the candidate's background (experience level, \
strongest/weakest areas, preferred language, etc.).

Return ONLY the JSON object, no extra text."""


# ── Phase 2: Profile Finalization ────────────────────────────────────────

FINALIZE_SYSTEM = """\
You are an expert interview coach finalizing a candidate profile. \
Adjust interview focus based on the candidate's background."""

FINALIZE_PROMPT = """\
Here is the partial job profile from research:
{profile_json}

The candidate answered these clarifying questions:
{answers_json}

Update the profile based on their answers. Adjust topic weights — increase weight for \
areas the candidate says they're weak in, decrease for strengths. Update the user_context section.

Return the complete updated profile as a JSON object with this structure:
{{
  "company": {{ ... same as input ... }},
  "role": {{ ... same as input ... }},
  "interview_focus": {{
    "topics": [
      {{
        "topic": "string",
        "weight": 0.0 to 1.0 (ADJUSTED based on candidate answers),
        "subtopics": ["string"],
        "expected_difficulty": "easy|medium|hard"
      }}
    ],
    "estimated_rounds": int,
    "format_notes": "string"
  }},
  "user_context": {{
    "years_experience": int or null,
    "strongest_languages": ["string"],
    "weakest_areas": ["string"],
    "target_level": "string",
    "additional_context": "string"
  }}
}}

Return ONLY the JSON object."""


# ── Phase 3: Question Generation ─────────────────────────────────────────

QUESTION_GEN_SYSTEM = """\
You are a senior technical interviewer. Generate challenging but fair interview questions \
tailored to the candidate's target role and current skill level. Focus on weak areas."""

QUESTION_GEN_PROMPT = """\
Generate interview questions for this candidate.

JOB PROFILE:
{profile_json}

{progress_section}

Generate exactly {num_questions} questions. Mix types based on the job profile topics and weights.
{guidance_section}

For coding questions, include test cases with input/output pairs.
For all questions, include expected answer key points and a sample solution.

Return a JSON object:
{{
  "questions": [
    {{
      "id": 1,
      "topic": "string",
      "subtopic": "string",
      "difficulty": "easy|medium|hard",
      "type": "coding|conceptual|system_design|behavioral",
      "title": "short title",
      "body": "full question text with examples",
      "hints": ["hint1", "hint2"],
      "test_cases": [
        {{
          "input": "string representation of input",
          "expected_output": "string representation of expected output",
          "is_hidden": false,
          "description": "what this tests"
        }}
      ],
      "expected_answer": {{
        "key_points": ["point1", "point2"],
        "sample_solution": "complete solution code or text",
        "time_complexity": "O(n) etc",
        "space_complexity": "O(n) etc",
        "follow_up_questions": ["follow-up 1"]
      }},
      "time_limit_minutes": 15
    }}
  ]
}}

Return ONLY the JSON object."""


# ── Phase 5: Evaluation ──────────────────────────────────────────────────

EVALUATION_SYSTEM = """\
You are a senior technical interviewer evaluating candidate answers. \
Be fair but thorough. Identify both strengths and areas for improvement."""

EVALUATION_PROMPT = """\
Evaluate this interview round.

JOB PROFILE:
{profile_json}

CURRENT PROGRESS (cumulative):
{progress_json}

QUESTIONS AND ANSWERS:
{qa_json}

For each question, compare the candidate's answer against the expected answer. Score 0-10.

Return a JSON object:
{{
  "evaluations": [
    {{
      "question_id": int,
      "topic": "string",
      "subtopic": "string",
      "score": 0-10,
      "max_score": 10,
      "correctness": 0.0-1.0,
      "completeness": 0.0-1.0,
      "code_quality": 0.0-1.0 or null,
      "strengths": ["what they did well"],
      "weaknesses": ["what they missed or got wrong"],
      "feedback": "detailed constructive feedback paragraph",
      "missed_key_points": ["key points they missed"]
    }}
  ],
  "summary": {{
    "overall_score": 0-10,
    "total_questions": int,
    "questions_passed": int (score >= 6),
    "strongest_topic": "string",
    "weakest_topic": "string",
    "key_takeaways": ["takeaway1", "takeaway2"],
    "improvement_suggestions": ["suggestion1", "suggestion2"]
  }},
  "updated_progress": {{
    "overall_score": 0-10 (weighted average across all rounds),
    "topic_mastery": [
      {{
        "topic": "string",
        "subtopic": "string",
        "score": 0-10,
        "attempts": int,
        "trend": "improving|declining|stable"
      }}
    ],
    "persistent_weaknesses": [
      {{
        "area": "string",
        "description": "specific pattern observed",
        "severity": "low|medium|high",
        "first_seen_round": int,
        "still_active": true
      }}
    ],
    "demonstrated_strengths": [
      {{
        "area": "string",
        "description": "what they consistently do well",
        "confidence": "low|medium|high"
      }}
    ],
    "next_round_guidance": {{
      "topic_distribution": {{"topic": weight}},
      "difficulty_adjustment": "easier|maintain|harder",
      "priority_areas": ["area1"],
      "avoid_topics": ["mastered_topic"],
      "specific_instructions": "what to focus on next"
    }},
    "score_history": [list of all round scores including this one]
  }}
}}

Return ONLY the JSON object."""


def build_progress_section(progress_json: str | None) -> str:
    if not progress_json:
        return "PROGRESS: This is the first round — no prior data."
    return f"CUMULATIVE PROGRESS FROM PREVIOUS ROUNDS:\n{progress_json}"


def build_guidance_section(progress_json: str | None) -> str:
    if not progress_json:
        return "This is the first round. Cover a broad range of the job's key topics."
    return (
        "IMPORTANT: Follow the next_round_guidance from the progress report. "
        "Emphasize weak areas and adjust difficulty as recommended."
    )
