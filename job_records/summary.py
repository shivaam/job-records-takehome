"""Calculate the job summary from validated attempts.

Each job is judged by its latest attempt.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from statistics import fmean

from job_records.models import JobAttempt, Status


@dataclass(frozen=True)
class JobSummary:
    total_jobs: int
    successful_jobs: int
    failed_jobs: int
    average_successful_job_duration_seconds: float | None
    jobs_requiring_retries: int


def summarize(attempts: Iterable[JobAttempt]) -> JobSummary:
    """Summarize validated attempts, judging each job by its latest attempt.

    The latest attempt (highest attempt number) decides whether a job counts as
    successful, failed, or running, and every metric uses only that attempt.
    For example, if attempt 1 failed and attempt 2 succeeded, the job is
    successful, and only attempt 2's duration counts toward the average.

    Expects at most one record per job and attempt number.
    """
    latest = _latest_attempts(attempts)
    # Running jobs count toward the total but are neither successful nor failed.
    successful = [record for record in latest if record.status is Status.SUCCESS]
    failed = [record for record in latest if record.status is Status.FAILED]
    # A job required retries if its latest attempt is greater than 1, even if
    # earlier attempts are missing from the input.
    retried = [record for record in latest if record.attempt > 1]
    # Only each job's latest successful attempt counts toward the average.
    durations = [
        record.duration_seconds
        for record in successful
        # Always true for a completed attempt; the check satisfies the type checker.
        if record.duration_seconds is not None
    ]

    return JobSummary(
        total_jobs=len(latest),
        successful_jobs=len(successful),
        failed_jobs=len(failed),
        # Rounded to milliseconds. No successful jobs means no average (None), not 0.
        average_successful_job_duration_seconds=(
            round(fmean(durations), 3) if durations else None
        ),
        jobs_requiring_retries=len(retried),
    )


def _latest_attempts(attempts: Iterable[JobAttempt]) -> list[JobAttempt]:
    """Return each job's attempt with the highest attempt number, in any input order."""
    latest: dict[str, JobAttempt] = {}
    for record in attempts:
        current = latest.get(record.job_id)
        if current is None or record.attempt > current.attempt:
            latest[record.job_id] = record
    return list(latest.values())
