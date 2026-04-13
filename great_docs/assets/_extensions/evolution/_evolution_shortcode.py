from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _bool_arg(value: str) -> bool:
    return value.lower() not in ("false", "no", "0")


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
        if args.json_file:
            # Render from a JSON file instead of live git history
            from great_docs._api_diff import render_evolution_table_from_dict

            json_path = Path(args.json_file)
            if not json_path.is_absolute():
                # Resolve relative to cwd (Quarto runs from great-docs/)
                json_path = Path(".").resolve() / json_path
            data = json.loads(json_path.read_text(encoding="utf-8"))
            html = render_evolution_table_from_dict(
                data,
                disclosure=_bool_arg(args.disclosure),
                summary_text=args.summary,
                include_css=_bool_arg(args.css),
            )
        else:
            # Live git history mode
            from great_docs._api_diff import render_evolution_table

            # Quarto runs from the project directory (great-docs/), the git root
            # is one level up.
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
        print(html)
    except Exception as exc:
        print(
            f"<!-- evolution shortcode error for {args.symbol}: {exc} -->",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
