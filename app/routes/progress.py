from fastapi import APIRouter, HTTPException

from app.storage.documents import get_latest_round_number, load_progress, load_round_report

router = APIRouter(prefix="/api/jobs/{job_id}", tags=["progress"])


@router.get("/progress")
async def get_progress(job_id: str):
    progress = load_progress(job_id)
    if not progress:
        raise HTTPException(404, "No progress data yet — complete at least one round")
    return progress.model_dump()


@router.get("/rounds")
async def list_rounds(job_id: str):
    latest = get_latest_round_number(job_id)
    if latest == 0:
        return []
    rounds = []
    for i in range(1, latest + 1):
        report = load_round_report(job_id, i)
        if report:
            rounds.append({
                "round_number": i,
                "overall_score": report.summary.overall_score,
                "total_questions": report.summary.total_questions,
                "questions_passed": report.summary.questions_passed,
            })
    return rounds
