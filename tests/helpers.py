"""Small builders for test inputs, not production code."""

from datetime import UTC, datetime, timedelta

from job_records.models import JobAttempt, Status

# Every builder starts from job A's first attempt: started at noon UTC on
# 2026-10-06 and succeeded after 10 seconds. Tests override only what they need.
START = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)


def raw_record(**changes: object) -> dict[str, object]:
    """Return a raw input record, as decoded from JSON, with the given changes."""
    record: dict[str, object] = {
        "job_id": "A",
        "status": "success",
        "started_at": "2026-10-06T12:00:00Z",
        "finished_at": "2026-10-06T12:00:10Z",
        "attempt": 1,
    }
    record.update(changes)
    return record


def job_attempt(
    job_id: str = "A",
    status: str = "success",
    attempt: int = 1,
    duration: float = 10,
) -> JobAttempt:
    """Return a JobAttempt built directly, without going through validation."""
    parsed_status = Status(status)
    finished_at = (
        None if parsed_status is Status.RUNNING else START + timedelta(seconds=duration)
    )
    return JobAttempt(job_id, parsed_status, START, finished_at, attempt)
