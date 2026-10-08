"""Business rules for accepting records and skipping invalid ones."""

import unittest
from datetime import UTC, timedelta

from job_records.models import JobAttempt, Status
from job_records.validation import (
    InvalidRecordError,
    validate_record,
    validate_records,
)
from tests.helpers import START, raw_record


def rejected_records(errors):
    """Return the 'record N (job X)' part of each error, without the reason."""
    return [error.split(": ")[0] for error in errors]


class ValidateRecordTests(unittest.TestCase):
    def assert_rejected_for(self, field, raw):
        """Assert the record is rejected because of this field, not another one."""
        with self.assertRaisesRegex(InvalidRecordError, rf"^{field}:"):
            validate_record(raw)

    def test_accepts_valid_record(self):
        self.assertEqual(
            validate_record(raw_record(attempt=3)),
            JobAttempt("A", Status.SUCCESS, START, START + timedelta(seconds=10), 3),
        )

    def test_accepts_running_record_without_a_finish_time(self):
        self.assertEqual(
            validate_record(raw_record(status="running", finished_at=None)),
            JobAttempt("A", Status.RUNNING, START, None, 1),
        )

    def test_converts_timestamps_to_utc(self):
        attempt = validate_record(
            raw_record(
                started_at="2026-10-06T13:00:00+01:00",
                finished_at="2026-10-06T07:00:10-05:00",
            )
        )
        self.assertEqual(attempt.started_at, START)
        self.assertIs(attempt.started_at.tzinfo, UTC)
        self.assertEqual(attempt.duration_seconds, 10.0)

    def test_ignores_extra_fields(self):
        self.assertEqual(
            validate_record(raw_record(extra="ignored")), validate_record(raw_record())
        )

    def test_rejects_missing_fields(self):
        for field in raw_record():
            with self.subTest(field=field):
                raw = raw_record()
                del raw[field]
                self.assert_rejected_for(field, raw)

    def test_rejects_values_that_are_not_objects(self):
        for raw in ([], "record"):
            with self.subTest(raw=raw), self.assertRaises(InvalidRecordError):
                validate_record(raw)

    def test_rejects_invalid_job_ids(self):
        for job_id in (12, "", " A", "A "):
            with self.subTest(job_id=job_id):
                self.assert_rejected_for("job_id", raw_record(job_id=job_id))

    def test_rejects_invalid_statuses(self):
        for status in ("SUCCESS", "complete"):
            with self.subTest(status=status):
                self.assert_rejected_for("status", raw_record(status=status))

    def test_rejects_attempts_that_are_not_positive_integers(self):
        # 0 is rejected by JobAttempt; validation reports it like the others.
        for attempt in (True, "2", 1.0, 0, -1):
            with self.subTest(attempt=attempt):
                self.assert_rejected_for("attempt", raw_record(attempt=attempt))

    def test_rejects_invalid_timestamps(self):
        invalid = [
            0,
            "yesterday",
            # Valid ISO 8601, but converting to UTC moves before year 1.
            "0001-01-01T00:00:00+01:00",
        ]
        for field in ("started_at", "finished_at"):
            for value in invalid:
                with self.subTest(field=field, value=value):
                    self.assert_rejected_for(field, raw_record(**{field: value}))

    def test_rejects_timestamps_without_a_time_zone(self):
        for field in ("started_at", "finished_at"):
            with self.subTest(field=field):
                raw = raw_record(**{field: "2026-10-06T12:00:00"})
                self.assert_rejected_for(field, raw)

    def test_rejects_records_that_break_finish_time_rules(self):
        # The rules live in JobAttempt; validation reports them like any field error.
        cases = [
            ("finishing before it started", "success", "2026-10-06T11:59:59Z"),
            ("running with a finish time", "running", "2026-10-06T12:00:10Z"),
            ("running with an empty finish time", "running", ""),
        ]
        for name, status, finished_at in cases:
            with self.subTest(name):
                raw = raw_record(status=status, finished_at=finished_at)
                self.assert_rejected_for("finished_at", raw)


class ValidateRecordsTests(unittest.TestCase):
    def test_skips_invalid_records_and_keeps_the_rest(self):
        validated = validate_records(
            [
                raw_record(),
                raw_record(attempt=2, finished_at="bad"),
                None,
                raw_record(job_id="B"),
            ]
        )
        self.assertEqual(
            [(attempt.job_id, attempt.attempt) for attempt in validated.attempts],
            [("A", 1), ("B", 1)],
        )
        self.assertEqual(
            rejected_records(validated.errors), ["record 2 (job 'A')", "record 3"]
        )

    def test_conflicting_copies_are_all_rejected_whichever_comes_first(self):
        records = [
            raw_record(),
            raw_record(attempt=2),
            raw_record(attempt=2, status="failed"),
        ]
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                validated = validate_records(records[::-1] if reverse else records)
                # Attempt 1 is kept; both copies of attempt 2 are rejected.
                self.assertEqual(
                    [attempt.attempt for attempt in validated.attempts], [1]
                )
                expected = [1, 2] if reverse else [2, 3]
                self.assertEqual(
                    rejected_records(validated.errors),
                    [f"record {index} (job 'A')" for index in expected],
                )

    def test_identical_copies_of_an_attempt_are_kept_once(self):
        redelivered = raw_record(attempt=2, finished_at="2026-10-06T12:00:20Z")
        validated = validate_records(
            [raw_record(), redelivered, redelivered, redelivered]
        )
        self.assertEqual([attempt.attempt for attempt in validated.attempts], [1, 2])
        self.assertEqual(validated.errors, ())

    def test_invalid_record_does_not_count_as_a_copy(self):
        records = [raw_record(), raw_record(status="bad")]
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                validated = validate_records(records[::-1] if reverse else records)
                self.assertEqual(
                    [attempt.status for attempt in validated.attempts],
                    [Status.SUCCESS],
                )
                self.assertEqual(len(validated.errors), 1)


if __name__ == "__main__":
    unittest.main()
