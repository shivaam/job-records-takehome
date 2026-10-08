"""Read the input file and return its records as decoded JSON, not yet validated."""

import json
from pathlib import Path


class InputFileError(Exception):
    """The input file cannot be used as a JSON array of records."""


def load_records(path: Path) -> list[object]:
    """Read a UTF-8 JSON file whose top-level value is an array."""
    try:
        with path.open(encoding="utf-8") as source:
            document = json.load(source)
    except (OSError, ValueError, RecursionError) as exc:
        # ValueError covers JSONDecodeError, UnicodeError, and integer limits.
        # Some Python versions also limit JSON nesting depth.
        raise InputFileError(f"Cannot read JSON input: {exc}") from exc
    if not isinstance(document, list):
        raise InputFileError("JSON document must be an array of records")
    return document
