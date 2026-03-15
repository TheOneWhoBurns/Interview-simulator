"""Test storage and model integration for evaluator flow."""
from unittest.mock import patch

from app.models.profile import JobProfile
from app.models.progress import ProgressReport
from app.models.question import Question, QuizState
from app.storage import documents

# Valid 12-char hex IDs for tests
ID1 = "aabbccddeef1"
ID2 = "aabbccddeef2"
ID3 = "aabbccddeef3"


def test_storage_roundtrip(tmp_path):
    """Test that we can save and load all document types."""
    with patch.object(documents.settings, "jobs_dir", tmp_path):
        # Profile
        profile = JobProfile(job_id=ID1, url="https://x.com", finalized=True)
        documents.save_profile(profile)
        loaded = documents.load_profile(ID1)
        assert loaded is not None
        assert loaded.job_id == ID1

        # Progress
        progress = ProgressReport(job_id=ID1, total_rounds=1, overall_score=7.0)
        documents.save_progress(progress)
        loaded_p = documents.load_progress(ID1)
        assert loaded_p is not None
        assert loaded_p.overall_score == 7.0

        # Quiz state
        state = QuizState(
            job_id=ID1, round_number=1,
            questions=[Question(id=1, topic="T", title="Q", body="B")],
            started=True,
        )
        documents.save_quiz_state(state)
        loaded_s = documents.load_quiz_state(ID1)
        assert loaded_s is not None
        assert loaded_s.round_number == 1

        # Cleanup
        documents.delete_quiz_state(ID1)
        assert documents.load_quiz_state(ID1) is None


def test_round_numbering(tmp_path):
    with patch.object(documents.settings, "jobs_dir", tmp_path):
        assert documents.get_latest_round_number(ID2) == 0

        from app.models.round_report import RoundReport, RoundSummary
        report = RoundReport(
            job_id=ID2, round_number=1,
            summary=RoundSummary(overall_score=6.0, total_questions=2, questions_passed=1),
        )
        documents.save_round_report(report)
        assert documents.get_latest_round_number(ID2) == 1

        report2 = RoundReport(
            job_id=ID2, round_number=2,
            summary=RoundSummary(overall_score=7.5, total_questions=3, questions_passed=2),
        )
        documents.save_round_report(report2)
        assert documents.get_latest_round_number(ID2) == 2


def test_list_jobs(tmp_path):
    with patch.object(documents.settings, "jobs_dir", tmp_path), \
         patch.object(documents.settings, "data_dir", tmp_path):
        profile = JobProfile(job_id=ID3, finalized=True)
        profile.company.name = "TestCo"
        profile.role.title = "SWE"
        documents.save_profile(profile)

        jobs = documents.list_jobs()
        assert len(jobs) == 1
        assert jobs[0]["company"] == "TestCo"


def test_invalid_job_id_rejected():
    """Path traversal attempts should be rejected."""
    import pytest
    with pytest.raises(ValueError, match="Invalid job_id"):
        documents._job_dir("../../etc")
    with pytest.raises(ValueError, match="Invalid job_id"):
        documents._job_dir("hello_world")
