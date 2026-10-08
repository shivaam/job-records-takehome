"""The data types shared across the package: job statuses and job attempts."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Status(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    RUNNING = "running"


@dataclass(frozen=True)
class JobAttempt:
    """One attempt of a job; a job with retries has one per attempt.

    Fields hold parsed values (UTC datetimes, a Status). The attempt enforces its
    own value rules, so an impossible attempt cannot be built.
    """

    job_id: str
    status: Status
    started_at: datetime
    finished_at: datetime | None
    attempt: int

    def __post_init__(self) -> None:
        """Raise ValueError, naming the field, if a value rule is broken."""
        if self.attempt < 1:
            raise ValueError("attempt: expected an integer of 1 or more")
        # A running attempt hasn't finished yet; a completed one has.
        if self.status is Status.RUNNING:
            if self.finished_at is not None:
                raise ValueError("finished_at: must be null for a running attempt")
        elif self.finished_at is None:
            raise ValueError("finished_at: required for a completed attempt")
        elif self.finished_at < self.started_at:
            raise ValueError("finished_at: must not precede started_at")

    @property
    def duration_seconds(self) -> float | None:
        """Return seconds from start to finish, or None while running.

        Completed attempts (success or failed) always have a duration.
        """
        if self.finished_at is None:
            return None
        return (self.finished_at - self.started_at).total_seconds()
