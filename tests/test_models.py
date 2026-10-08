"""Business rules for a single job attempt: its duration and value rules."""

import unittest
from datetime import timedelta

from job_records.models import JobAttempt, Status
from tests.helpers import START, job_attempt


class JobAttemptDurationTests(unittest.TestCase):
    def test_duration_is_finish_minus_start_in_seconds(self):
        attempt = JobAttempt(
            "A", Status.SUCCESS, START, START + timedelta(seconds=90), 1
        )
        self.assertEqual(attempt.duration_seconds, 90.0)

    def test_failed_attempt_also_has_a_duration(self):
        attempt = job_attempt(status="failed", duration=25)
        self.assertEqual(attempt.duration_seconds, 25.0)

    def test_running_attempt_has_no_duration(self):
        self.assertIsNone(job_attempt(status="running").duration_seconds)


class JobAttemptRuleTests(unittest.TestCase):
    def test_impossible_attempts_cannot_be_built(self):
        """Each broken rule raises ValueError naming the field."""
        before_start = START - timedelta(seconds=1)
        cases = [
            ("running with a finish time", Status.RUNNING, START, 1, "finished_at"),
            ("completed without a finish time", Status.FAILED, None, 1, "finished_at"),
            # Both completed statuses, so the rule can't quietly cover only one.
            (
                "success ending before start",
                Status.SUCCESS,
                before_start,
                1,
                "finished_at",
            ),
            (
                "failed ending before start",
                Status.FAILED,
                before_start,
                1,
                "finished_at",
            ),
            ("attempt 0", Status.SUCCESS, START, 0, "attempt"),
        ]
        for name, status, finished_at, attempt, field in cases:
            with self.subTest(name), self.assertRaisesRegex(ValueError, f"^{field}:"):
                JobAttempt("A", status, START, finished_at, attempt)


if __name__ == "__main__":
    unittest.main()
