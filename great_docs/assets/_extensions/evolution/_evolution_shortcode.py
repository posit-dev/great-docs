from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import NoReturn


def _bool_arg(value: str) -> bool:
    return value.lower() not in ("false", "no", "0")


def _fail(symbol: str, error: Exception) -> NoReturn:
    """Print an HTML error comment to standard error and exit with status 1"""
    print(f"<!-- evolution shortcode error for {symbol}: {error} -->", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render an evolution table.")
    parser.add_argument("symbol", help="Symbol name to track")
    parser.add_argument("--package", default=None)
    parser.add_argument("--old_version", default=None)
    parser.add_argument("--new_version", default=None)
    parser.add_argument("--changes_only", default="true")
    parser.add_argument("--disclosure", default="false")
    parser.add_argument("--summary", default=None)
    parser.add_argument("--css", default="true")
    parser.add_argument("--json_file", default=None, help="Path to a JSON file to render from")

    args = parser.parse_args()

    try:
        from great_docs._api_evolution.markers import EVOLUTION_ERRORS
        from great_docs._api_evolution.render import (
            render_evolution_table,
            render_evolution_table_from_dict,
        )
    except ImportError as exc:
        _fail(args.symbol, exc)

    try:
        if args.json_file:
            json_path = Path(args.json_file)
            if not json_path.is_absolute():
                # Quarto runs from `great-docs/`, so relative paths use that directory.
                json_path = Path(".").resolve() / json_path
            data = json.loads(json_path.read_text(encoding="utf-8"))
            html = render_evolution_table_from_dict(
                data,
                disclosure=_bool_arg(args.disclosure),
                summary_text=args.summary,
                include_css=_bool_arg(args.css),
            )
        else:
            # Quarto runs from `great-docs/`, one level below the Git root.
            project_root = Path(".").resolve().parent

            html = render_evolution_table(
                project_root,
                args.symbol,
                package=args.package,
                old_version=args.old_version,
                new_version=args.new_version,
                changes_only=_bool_arg(args.changes_only),
                disclosure=_bool_arg(args.disclosure),
                summary_text=args.summary,
                include_css=_bool_arg(args.css),
            )
    except (*EVOLUTION_ERRORS, json.JSONDecodeError, UnicodeDecodeError) as exc:
        _fail(args.symbol, exc)
    print(html)


if __name__ == "__main__":
    main()
