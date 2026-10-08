# Job Records Summary

A small command-line application that reads job execution records from a JSON
file, skips invalid records with a warning, and prints a summary: total jobs,
successful jobs, failed jobs, average successful-job duration, and jobs that
required retries.

## Problem statement

Build a small Python application that processes job execution records containing
`job_id`, `status`, `started_at`, `finished_at`, and `attempt`.

The application should:

- Read records from a JSON file and handle malformed records gracefully.
- Calculate execution duration for completed jobs.
- Report total jobs, successful jobs, failed jobs, average successful-job
  duration, and jobs that required retries.
- Use a modular, production-style structure rather than one monolithic script.
- Include automated tests for important behavior and a short README covering
  execution, testing, assumptions, and design decisions.

Standard Python libraries and reasonable third-party packages are allowed. The
expected effort is 60–90 minutes. No sample input or definitive counting or
ordering rules were provided; the assumptions below define this implementation's
interpretation.

## Quick start

Requires Python 3.11 or newer. There are no runtime or test dependencies.
Run the commands below from the directory containing this README.

```sh
python3 -m job_records summarize examples/jobs.json
```

`examples/jobs.json` has three jobs: A fails and then succeeds on a retry, B fails,
and C is still running. The summary is printed to stdout:

```json
{
  "summary": {
    "total_jobs": 3,
    "successful_jobs": 1,
    "failed_jobs": 1,
    "average_successful_job_duration_seconds": 10.0,
    "jobs_requiring_retries": 1
  }
}
```

`examples/jobs_error.json` adds invalid input. The invalid entries are skipped
with a warning each on stderr, and the summary of the valid records is still
printed:

```sh
python3 -m job_records summarize examples/jobs_error.json
```

```text
WARNING: record 7 (job 'E'): attempt 2 has conflicting copies
WARNING: record 8 (job 'E'): attempt 2 has conflicting copies
WARNING: record 9 (job 'F'): started_at: invalid ISO timestamp
WARNING: record 10: expected an object
```

The summary counts 5 jobs: 3 successful, 1 failed, 20.0 seconds average, and 1
retried. Job F is left out because its only record is invalid, and job E is
judged by its valid attempt 1.

Run the tests:

```sh
python3 -m unittest discover -s tests
```

## How it works

1. **Load** the file and check that it is a JSON array.
2. **Validate** each record. Invalid records are skipped with a warning.
3. **Pick each job's latest attempt** (highest attempt number).
4. **Calculate** the five metrics from those latest attempts.
5. **Print** the summary as JSON.

| Module | Responsibility |
| --- | --- |
| `job_records/loader.py` | Reads the input file into raw, not yet validated records. |
| `job_records/models.py` | Shared data types: `Status`, and `JobAttempt`, which enforces its own value rules. |
| `job_records/validation.py` | Validates raw records into `JobAttempt`s and explains each rejection. |
| `job_records/summary.py` | Picks each job's latest attempt and calculates the `JobSummary`. |
| `job_records/cli.py` | The `summarize` command: logging, JSON output, and exit status. |

## Assumptions

- **One job per `job_id`.** The total counts distinct jobs, not records.
- **The latest attempt decides a job's outcome.** The latest attempt is the highest
  attempt number, in any input order. For example, if attempt 1 failed and
  attempt 2 succeeded, the job is successful.
- **Completed means `success` or `failed`.** Duration is `finished_at` minus
  `started_at`; running attempts have no duration.
- **Running jobs count toward the total** (and retries), but not as successful or
  failed.
- **A job required retries** if its latest attempt number is greater than 1, even
  when earlier attempts are missing from the input.
- **The average uses each job's latest attempt, only if it succeeded.**
- **Invalid records are skipped with a warning.** The rest still count, so a job is
  judged by its latest *valid* attempt: if attempt 2 is invalid, attempt 1 decides.
- **Identical copies of an attempt count once; conflicting copies are all
  rejected,** so input order never matters. This includes an attempt recorded as
  `running` and later as `success`.
- **Timestamps must include a time zone** and are converted to UTC. A missing time
  zone is rejected rather than guessed.

## Output and exit codes

stdout contains only the JSON summary; warnings and debug logs go to stderr, so
the output can be piped to another command. The average is in seconds, rounded
to 3 decimal places (milliseconds), and is `null` when there are no successful
jobs. Only the average duration is reported, not each job's duration.

Each warning names the record's position (counting from 1), its job ID when
valid, and the reason. For debug logs, add `--verbose` after the command:
`python3 -m job_records summarize --verbose examples/jobs.json`.

| Exit code | Meaning |
| --- | --- |
| `0` | A summary was printed. Invalid records, if any, were skipped with warnings. |
| `1` | The input file could not be used: missing, unreadable, not valid JSON (including numbers too large to read), or not an array. |
| `2` | Invalid command-line usage. |

## Input rules

The input is a UTF-8 JSON array of records. Every record needs all five fields;
extra fields are ignored.

| Field | Accepted values |
| --- | --- |
| `job_id` | Nonempty string without leading or trailing whitespace; case-sensitive |
| `status` | `success`, `failed`, or `running` (lowercase) |
| `started_at` | ISO 8601 timestamp with a time zone, such as `2026-10-06T12:00:00Z`, as accepted by Python's `datetime.fromisoformat` |
| `finished_at` | Same format, not before `started_at`; `null` for `running` |
| `attempt` | Integer of 1 or more (`true`/`false` are rejected) |

## Design decisions

- **Separate layers.** Loading, validation, the summary, and the CLI are separate
  modules. Only `loader` and `cli` read files or write output, so validation and
  the summary are pure functions that are easy to test and reuse.
- **Checks at three levels, each rule in one place.** `loader` checks the file
  (exit 1 if unusable), `validation` checks each record's fields and types, and
  `JobAttempt` enforces the value rules (attempt of 1 or more, finish time present
  and not before the start). Bad records become warnings either way.
- **Subcommands.** The CLI uses subcommands (currently only `summarize`) so new
  commands can reuse the loader and validation without changing existing ones.
- **Flat modules.** Each layer is one file for now; a layer becomes a subpackage
  when it grows.
- **Standard library only**, including `unittest`, so nothing needs installing to
  run the application or its tests.
- **Skipped records are warnings, not failures.** The summary of the valid records
  is still useful, so the run exits with 0.
- **Separate test inputs.** CLI tests read `tests/fixtures/`, so the user examples
  in `examples/` can change without affecting tests.

## Testing

Tests are grouped by business rule: counting jobs, retries, the average duration,
record validation, file input, and end-to-end CLI runs. Most test files match one
module; `test_validation_and_summary.py` checks how skipped records affect the
summary. The CLI tests also check which records are warned about, and the error
fixture mixes jobs together so the result cannot depend on order.

Optional lint, formatting, and strict type checks (macOS/Linux with Make):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
make check
```

After installation, `.venv/bin/job-records summarize examples/jobs.json` is also
available; it behaves the same as
`python3 -m job_records summarize examples/jobs.json`.

`make check` runs ruff, mypy, and the tests, and does not modify source files. To
apply formatting: `.venv/bin/python -m ruff format job_records tests`.

## Possible improvements

- **Scale.** The whole file is loaded at once, and validation keeps every parsed
  record plus a set of copies per attempt, so memory grows with the input several
  times over. Streaming records one at a time would help, but per-job state is
  still needed: a job's latest attempt can arrive last, and a later conflicting
  copy can invalidate it.
- **Data-quality rules.** Treat an attempt recorded as `running` and later as
  `success` as an update rather than a conflict; report jobs whose latest record
  was invalid as uncertain instead of falling back to an earlier attempt; and
  reject duplicate keys inside a record (Python's JSON parser keeps the last one
  silently).
- **Error reporting.** Structured errors (record, job, field, reason) for a JSON
  error report, and a `--strict` flag that exits non-zero when any record is
  skipped, for pipelines that must treat partial input as a failure.
- **More commands and inputs.** A `validate` command that checks records without
  summarizing, and other input formats such as CSV.
- **Production readiness.** CI/CD (for example GitHub Actions running `make check`
  on every supported Python version), pre-commit hooks, and packaged releases.
