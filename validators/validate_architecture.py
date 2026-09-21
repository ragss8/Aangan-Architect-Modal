"""Validate Architecture JSON, printing readable errors for each input file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__:
    from .validate_layout import validate_layout
else:
    from validate_layout import validate_layout


def validate_architecture(document: Any) -> list[str]:
    """Return readable errors, using the canonical structured validator."""
    return [violation["message"] for violation in validate_layout(document)["violations"]]


def _reject_nonstandard_constant(value: str) -> None:
    raise ValueError(f"nonstandard JSON number: {value}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", type=Path, nargs="+", help="Architecture JSON files to validate")
    args = parser.parse_args()

    failed = False
    for path in args.files:
        try:
            document = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_nonstandard_constant)
            errors = validate_architecture(document)
        except (OSError, ValueError) as exc:
            errors = [str(exc)]

        if errors:
            failed = True
            for error in errors:
                print(f"{path}: {error}", file=sys.stderr)
        else:
            print(f"{path}: valid")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
