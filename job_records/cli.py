"""Command-line interface: one small handler per subcommand.

Handlers reuse the loader, validation, and summary modules. An unusable input
file is reported once, in main, with exit status 1. Invalid command-line usage
exits with status 2 (argparse's convention).
"""

import argparse
import json
import logging
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict
from pathlib import Path

from job_records.loader import InputFileError, load_records
from job_records.summary import summarize
from job_records.validation import validate_records

logger = logging.getLogger(__name__)

CommandHandler = Callable[[argparse.Namespace], int]


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(args.verbose)
    handler: CommandHandler = args.handler
    try:
        return handler(args)
    except InputFileError as exc:
        logger.error("%s", exc)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="job-records", description="Work with job execution records."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    summarize_command = commands.add_parser(
        "summarize",
        help="summarize the highest valid attempt of each job",
    )
    summarize_command.add_argument(
        "input", type=Path, help="UTF-8 JSON file containing an array of records"
    )
    summarize_command.add_argument(
        "-v", "--verbose", action="store_true", help="include debug logs on stderr"
    )
    summarize_command.set_defaults(handler=run_summarize)
    return parser


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )


def run_summarize(args: argparse.Namespace) -> int:
    """Print the job summary; invalid records are skipped with a warning."""
    logger.debug("Reading input file %s", args.input)
    records = load_records(args.input)

    validated = validate_records(records)
    job_summary = summarize(validated.attempts)
    output = {"summary": asdict(job_summary)}
    print(json.dumps(output, indent=2))
    logger.debug(
        "Summarized %d jobs; skipped %d invalid records",
        job_summary.total_jobs,
        len(validated.errors),
    )
    for error in validated.errors:
        logger.warning("%s", error)
    # Skipped records are warnings, not failures: a summary was still produced.
    return 0
