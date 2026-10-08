"""Rejecting files that cannot be used as a JSON array of records."""

import tempfile
import unittest
from pathlib import Path

from job_records.loader import InputFileError, load_records


class LoadRecordsTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def load(self, content):
        path = self.directory / "jobs.json"
        path.write_bytes(content)
        return load_records(path)

    def test_returns_records_without_validating_them(self):
        self.assertEqual(self.load(b'[{"job_id": "A"}, 5]'), [{"job_id": "A"}, 5])

    def test_rejects_unusable_file_contents(self):
        # One case per path in load_records; JSON parsing itself is Python's job.
        cases = [
            ("not JSON", b"not json"),
            ("invalid UTF-8", b'["\xff"]'),
            ("valid JSON, but not an array", b"{}"),
        ]
        for name, content in cases:
            with self.subTest(name), self.assertRaises(InputFileError):
                self.load(content)

    def test_rejects_missing_file(self):
        with self.assertRaises(InputFileError):
            load_records(self.directory / "missing.json")


if __name__ == "__main__":
    unittest.main()
