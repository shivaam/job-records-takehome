"""End-to-end runs of the command: output, warnings, exit status, and arguments."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Test-only inputs. The user examples in examples/ are documentation and can be
# edited without affecting these tests.
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def warned_records(stderr):
    """Return the 'record N (job X)' part of each warning, without the reason."""
    return [
        line.split(": ")[1]
        for line in stderr.splitlines()
        if line.startswith("WARNING: ")
    ]


class CliTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def run_cli(self, *args):
        return subprocess.run(
            # -B: don't write __pycache__ into the package while testing.
            [sys.executable, "-B", "-m", "job_records", *map(str, args)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

    def run_input(self, content):
        path = self.directory / "jobs.json"
        path.write_bytes(content)
        return self.run_cli("summarize", path)

    def test_clean_input_exits_0_with_full_summary_and_no_warnings(self):
        result = self.run_cli("summarize", FIXTURES / "jobs.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            json.loads(result.stdout),
            {
                "summary": {
                    "total_jobs": 3,
                    "successful_jobs": 1,
                    "failed_jobs": 1,
                    "average_successful_job_duration_seconds": 10.0,
                    "jobs_requiring_retries": 1,
                },
            },
        )

    def test_skipped_records_are_warned_about_and_the_rest_summarized(self):
        # Jobs are interleaved and some retries come before their first attempt.
        # A: failed, then succeeded in 10s. B: failed. C: running. D: succeeded
        # in 30s. E: attempt 2 has conflicting copies, so attempt 1 counts (20s).
        # F: only an invalid record. Record 9 is not a record at all.
        result = self.run_cli("summarize", FIXTURES / "jobs_error.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            {
                "summary": {
                    "total_jobs": 5,
                    "successful_jobs": 3,
                    "failed_jobs": 1,
                    "average_successful_job_duration_seconds": 20.0,
                    "jobs_requiring_retries": 1,
                },
            },
        )
        self.assertEqual(
            warned_records(result.stderr),
            [
                "record 4 (job 'E')",
                "record 6 (job 'F')",
                "record 8 (job 'E')",
                "record 9",
            ],
        )

    def test_unusable_file_exits_1_without_a_summary(self):
        result = self.run_input(b"not json")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertTrue(result.stderr.startswith("ERROR: "), result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_decoder_depth_limit_is_reported_without_a_traceback(self):
        content = b"[" * 2000 + b"0" + b"]" * 2000
        try:
            json.loads(content)
        except RecursionError:
            pass
        else:
            self.skipTest("This interpreter can decode this nesting depth")
        result = self.run_input(content)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertTrue(result.stderr.startswith("ERROR: "), result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_verbose_adds_debug_logs_without_changing_the_summary(self):
        path = FIXTURES / "jobs.json"
        default = self.run_cli("summarize", path)
        verbose = self.run_cli("summarize", "--verbose", path)
        self.assertEqual(verbose.returncode, 0, verbose.stderr)
        self.assertEqual(json.loads(verbose.stdout), json.loads(default.stdout))
        self.assertIn("DEBUG: ", verbose.stderr)
        self.assertNotIn("DEBUG: ", default.stderr)

    def test_missing_input_argument_exits_2_with_usage(self):
        result = self.run_cli("summarize")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("usage:", result.stderr)


if __name__ == "__main__":
    unittest.main()
