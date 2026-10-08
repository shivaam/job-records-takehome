"""Business rules for counting jobs, retries, and the average duration."""

import unittest
from itertools import permutations

from job_records.summary import JobSummary, summarize
from tests.helpers import job_attempt


class CountingTests(unittest.TestCase):
    def test_job_outcome(self):
        cases = [
            (
                "one successful attempt: one successful job",
                [job_attempt()],
                JobSummary(1, 1, 0, 10.0, 0),
            ),
            (
                "one failed attempt: one failed job",
                [job_attempt(status="failed")],
                JobSummary(1, 0, 1, None, 0),
            ),
            (
                "failed, then succeeded: the latest attempt decides, successful",
                [job_attempt(status="failed"), job_attempt(attempt=2, duration=20)],
                JobSummary(1, 1, 0, 20.0, 1),
            ),
            (
                "succeeded, then failed: the latest attempt decides, failed",
                [job_attempt(), job_attempt(attempt=2, status="failed")],
                JobSummary(1, 0, 1, None, 1),
            ),
            (
                "succeeded, then running: the latest attempt decides, total only",
                [job_attempt(), job_attempt(attempt=2, status="running")],
                JobSummary(1, 0, 0, None, 1),
            ),
            (
                "no input: zero counts and a null average",
                [],
                JobSummary(0, 0, 0, None, 0),
            ),
        ]
        for name, attempts, expected in cases:
            with self.subTest(name):
                self.assertEqual(summarize(attempts), expected)

    def test_job_ids_are_case_sensitive(self):
        summary = summarize(
            [job_attempt(job_id="etl"), job_attempt(job_id="ETL", status="failed")]
        )
        self.assertEqual(summary, JobSummary(2, 1, 1, 10.0, 0))

    def test_latest_attempt_decides_each_job_in_any_input_order(self):
        # A: failed, then succeeded in 20s. B: succeeded, then failed. C: running.
        attempts = [
            job_attempt(job_id="A", status="failed"),
            job_attempt(job_id="A", attempt=2, duration=20),
            job_attempt(job_id="B"),
            job_attempt(job_id="B", attempt=2, status="failed"),
            job_attempt(job_id="C", status="running"),
        ]
        expected = JobSummary(3, 1, 1, 20.0, 2)
        for ordering in permutations(attempts):
            labels = [f"{attempt.job_id}{attempt.attempt}" for attempt in ordering]
            with self.subTest(order=" ".join(labels)):
                self.assertEqual(summarize(ordering), expected)


class RetryTests(unittest.TestCase):
    def test_jobs_requiring_retries(self):
        cases = [
            (
                "only first attempts: no retries",
                [job_attempt(), job_attempt(job_id="B", status="failed")],
                0,
            ),
            (
                "several retries of one job count once",
                [
                    job_attempt(status="failed"),
                    job_attempt(attempt=2, status="failed"),
                    job_attempt(attempt=3),
                ],
                1,
            ),
            (
                "counted whatever the latest status",
                [
                    job_attempt(job_id="A", attempt=2),
                    job_attempt(job_id="B", attempt=2, status="failed"),
                    job_attempt(job_id="C", attempt=2, status="running"),
                ],
                3,
            ),
            (
                "counted even when earlier attempts are missing from the input",
                [job_attempt(attempt=3)],
                1,
            ),
        ]
        for name, attempts, expected in cases:
            with self.subTest(name):
                self.assertEqual(summarize(attempts).jobs_requiring_retries, expected)


class AverageDurationTests(unittest.TestCase):
    def test_average_successful_job_duration(self):
        cases = [
            (
                "average of several successful jobs",
                [job_attempt(job_id="A"), job_attempt(job_id="B", duration=20)],
                15.0,
            ),
            (
                "rounded to milliseconds: (0 + 1 + 1) / 3 is 0.667",
                [
                    job_attempt(job_id="A", duration=0),
                    job_attempt(job_id="B", duration=1),
                    job_attempt(job_id="C", duration=1),
                ],
                0.667,
            ),
            (
                "zero duration counts as zero, not missing",
                [job_attempt(duration=0)],
                0.0,
            ),
            (
                "no successful jobs: null average",
                [
                    job_attempt(job_id="A", status="failed"),
                    job_attempt(job_id="B", status="running"),
                ],
                None,
            ),
            (
                "excludes failed jobs",
                [
                    job_attempt(job_id="A"),
                    job_attempt(job_id="B", status="failed", duration=3600),
                ],
                10.0,
            ),
            (
                "excludes running jobs",
                [job_attempt(job_id="A"), job_attempt(job_id="B", status="running")],
                10.0,
            ),
            (
                "excludes an earlier failed attempt of a successful job",
                [job_attempt(status="failed", duration=3600), job_attempt(attempt=2)],
                10.0,
            ),
            (
                "excludes an earlier successful attempt replaced by a later one",
                [job_attempt(), job_attempt(attempt=2, duration=20)],
                20.0,
            ),
        ]
        for name, attempts, expected in cases:
            with self.subTest(name):
                average = summarize(attempts).average_successful_job_duration_seconds
                self.assertEqual(average, expected)


if __name__ == "__main__":
    unittest.main()
