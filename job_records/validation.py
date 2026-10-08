"""Validate raw job records and convert the valid ones into JobAttempt objects."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from job_records.models import JobAttempt, Status


class InvalidRecordError(ValueError):
    """An input record violates the documented contract."""


@dataclass(frozen=True)
class ValidationResult:
    attempts: tuple[JobAttempt, ...]
    errors: tuple[str, ...]


def validate_records(raw_records: Iterable[object]) -> ValidationResult:
    """Keep valid records and report each skipped record's original input index.

    Invalid records are skipped, and the rest of the input is still used.

    Identical copies of a (job_id, attempt) pair, such as a redelivered record,
    are kept once. If the copies differ, every copy is rejected, so the result
    never depends on which copy appears first.
    """
    parsed: list[tuple[int, JobAttempt]] = []
    errors: list[str | None] = []
    for index, raw in enumerate(raw_records, start=1):
        # One diagnostic slot per input row preserves order without sorting.
        errors.append(None)
        try:
            parsed.append((index, validate_record(raw)))
        except InvalidRecordError as exc:
            errors[-1] = f"record {index}{_job_label(raw)}: {exc}"

    copies: defaultdict[tuple[str, int], set[JobAttempt]] = defaultdict(set)
    for _, record in parsed:
        copies[record.job_id, record.attempt].add(record)

    attempts: list[JobAttempt] = []
    kept: set[tuple[str, int]] = set()
    for index, record in parsed:
        key = (record.job_id, record.attempt)
        if len(copies[key]) > 1:
            errors[index - 1] = (
                f"record {index} (job {record.job_id!r}): "
                f"attempt {record.attempt} has conflicting copies"
            )
        elif key not in kept:
            kept.add(key)
            attempts.append(record)
    return ValidationResult(
        tuple(attempts), tuple(message for message in errors if message is not None)
    )


def validate_record(raw: object) -> JobAttempt:
    """Validate one decoded JSON value, reporting its first invalid field.

    This checks the raw shape and types; JobAttempt itself checks the value rules
    (attempt of 1 or more, finish time present and not before the start).
    """
    if not isinstance(raw, dict):
        raise InvalidRecordError("expected an object")
    for field in ("job_id", "status", "started_at", "finished_at", "attempt"):
        if field not in raw:
            raise InvalidRecordError(f"{field}: required field is missing")

    job_id = raw["job_id"]
    if not _is_valid_job_id(job_id):
        raise InvalidRecordError(
            "job_id: expected a nonempty string without surrounding whitespace"
        )
    try:
        status = Status(raw["status"])
    except ValueError as exc:
        raise InvalidRecordError(
            "status: expected success, failed, or running"
        ) from exc
    attempt = raw["attempt"]
    # bool is an int subclass; accepting True would silently create attempt 1.
    if type(attempt) is not int:
        raise InvalidRecordError("attempt: expected an integer of 1 or more")

    started_at = _parse_timestamp(raw["started_at"], "started_at")
    finished_at = (
        None
        if raw["finished_at"] is None
        else _parse_timestamp(raw["finished_at"], "finished_at")
    )
    try:
        return JobAttempt(job_id, status, started_at, finished_at, attempt)
    except ValueError as exc:
        raise InvalidRecordError(str(exc)) from exc


def _is_valid_job_id(value: object) -> bool:
    return isinstance(value, str) and bool(value) and value == value.strip()


def _parse_timestamp(value: object, field: str) -> datetime:
    """Parse an ISO 8601 timestamp, as accepted by datetime.fromisoformat, into UTC.

    A missing time zone is rejected rather than guessed.
    """
    if not isinstance(value, str):
        raise InvalidRecordError(f"{field}: expected a timestamp string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise InvalidRecordError(f"{field}: invalid ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise InvalidRecordError(
            f"{field}: a time zone is required, such as Z or +02:00"
        )
    try:
        return parsed.astimezone(UTC)
    except (ValueError, OverflowError) as exc:
        raise InvalidRecordError(
            f"{field}: timestamp is outside the supported UTC range"
        ) from exc


def _job_label(raw: object) -> str:
    if isinstance(raw, dict) and _is_valid_job_id(raw.get("job_id")):
        return f" (job {raw['job_id']!r})"
    return ""
