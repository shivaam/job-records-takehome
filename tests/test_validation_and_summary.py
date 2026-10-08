"""Validation and summary together: how skipped records affect the metrics."""

import unittest

from job_records.summary import JobSummary, summarize
from job_records.validation import validate_records
from tests.helpers import raw_record


def summarize_raw(records):
    validated = validate_records(records)
    return summarize(validated.attempts), validated.errors


class SkippedRecordsEffectTests(unittest.TestCase):
    def test_invalid_latest_attempt_falls_back_to_earlier_valid_attempt(self):
        records = [
            raw_record(),
            raw_record(attempt=2, status="failed", finished_at="bad"),
        ]
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                summary, errors = summarize_raw(records[::-1] if reverse else records)
                self.assertEqual(summary, JobSummary(1, 1, 0, 10.0, 0))
                self.assertEqual(len(errors), 1)


if __name__ == "__main__":
    unittest.main()
