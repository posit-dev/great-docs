#!/usr/bin/env python3
"""CLI helper for the tbl-preview Quarto shortcode."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


def _load_tbl_preview():
    """Import tbl_preview without triggering great_docs.__init__."""
    try:
        from great_docs._tbl_preview import tbl_preview

        return tbl_preview
    except (ImportError, ModuleNotFoundError):
        # Fall back to loading the module directly by file path.
        # Walk up the directory tree until we find great_docs/_tbl_preview.py.
        here = Path(__file__).resolve().parent
        p = here
        while p != p.parent:
            candidate = p / "great_docs" / "_tbl_preview.py"
            if candidate.exists():
                spec = importlib.util.spec_from_file_location("_tbl_preview", candidate)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod.tbl_preview
            p = p.parent
        raise ImportError("Cannot find _tbl_preview.py")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a table preview from a data file.")
    parser.add_argument(
        "file", help="Path to data file (CSV, TSV, JSONL, Parquet, Feather, Arrow IPC)"
    )
    parser.add_argument("--columns", default=None, help="Comma-separated column names")
    parser.add_argument("--n_head", type=int, default=5)
    parser.add_argument("--n_tail", type=int, default=5)
    parser.add_argument("--show_all", default="false")
    parser.add_argument("--show_row_numbers", default="true")
    parser.add_argument("--show_dtypes", default="true")
    parser.add_argument("--show_dimensions", default="true")
    parser.add_argument("--max_col_width", type=int, default=250)
    parser.add_argument("--min_tbl_width", type=int, default=500)
    parser.add_argument("--caption", default=None)
    parser.add_argument("--row_index_offset", type=int, default=0)
    args = parser.parse_args()

    tbl_preview = _load_tbl_preview()

    columns = [c.strip() for c in args.columns.split(",")] if args.columns else None

    def _to_bool(s: str) -> bool:
        return s.lower() in ("true", "1", "yes")

    result = tbl_preview(
        data=args.file,
        columns=columns,
        n_head=args.n_head,
        n_tail=args.n_tail,
        show_all=_to_bool(args.show_all),
        show_row_numbers=_to_bool(args.show_row_numbers),
        show_dtypes=_to_bool(args.show_dtypes),
        show_dimensions=_to_bool(args.show_dimensions),
        max_col_width=args.max_col_width,
        min_tbl_width=args.min_tbl_width,
        caption=args.caption,
        row_index_offset=args.row_index_offset,
    )

    sys.stdout.write(result.as_html())


if __name__ == "__main__":
    main()
