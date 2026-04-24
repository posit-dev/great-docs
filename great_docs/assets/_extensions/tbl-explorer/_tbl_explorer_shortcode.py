#!/usr/bin/env python3
"""CLI helper for the tbl-explorer Quarto shortcode."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


def _load_tbl_explorer():
    """Import tbl_explorer without triggering great_docs.__init__."""
    try:
        from great_docs._tbl_explorer import tbl_explorer

        return tbl_explorer
    except (ImportError, ModuleNotFoundError):
        here = Path(__file__).resolve().parent
        p = here
        while p != p.parent:
            candidate = p / "great_docs" / "_tbl_explorer.py"
            if candidate.exists():
                spec = importlib.util.spec_from_file_location("_tbl_explorer", candidate)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod.tbl_explorer
            p = p.parent
        raise ImportError("Cannot find _tbl_explorer.py")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render an interactive table explorer.")
    parser.add_argument(
        "file", help="Path to data file (CSV, TSV, JSONL, Parquet, Feather, Arrow IPC)"
    )
    parser.add_argument("--columns", default=None, help="Comma-separated column names")
    parser.add_argument("--page_size", type=int, default=20)
    parser.add_argument("--sortable", default="true")
    parser.add_argument("--filterable", default="true")
    parser.add_argument("--column_toggle", default="true")
    parser.add_argument("--copyable", default="true")
    parser.add_argument("--downloadable", default="true")
    parser.add_argument("--resizable", default="false")
    parser.add_argument("--sticky_header", default="true")
    parser.add_argument("--search_highlight", default="true")
    parser.add_argument("--show_row_numbers", default="true")
    parser.add_argument("--show_dtypes", default="true")
    parser.add_argument("--show_dimensions", default="true")
    parser.add_argument("--max_col_width", type=int, default=250)
    parser.add_argument("--min_tbl_width", type=int, default=500)
    parser.add_argument("--caption", default=None)
    parser.add_argument("--highlight_missing", default="true")
    args = parser.parse_args()

    tbl_explorer = _load_tbl_explorer()

    columns = [c.strip() for c in args.columns.split(",")] if args.columns else None

    def _to_bool(s: str) -> bool:
        return s.lower() in ("true", "1", "yes")

    result = tbl_explorer(
        data=args.file,
        columns=columns,
        page_size=args.page_size,
        sortable=_to_bool(args.sortable),
        filterable=_to_bool(args.filterable),
        column_toggle=_to_bool(args.column_toggle),
        copyable=_to_bool(args.copyable),
        downloadable=_to_bool(args.downloadable),
        resizable=_to_bool(args.resizable),
        sticky_header=_to_bool(args.sticky_header),
        search_highlight=_to_bool(args.search_highlight),
        show_row_numbers=_to_bool(args.show_row_numbers),
        show_dtypes=_to_bool(args.show_dtypes),
        show_dimensions=_to_bool(args.show_dimensions),
        max_col_width=args.max_col_width,
        min_tbl_width=args.min_tbl_width,
        caption=args.caption,
        highlight_missing=_to_bool(args.highlight_missing),
    )

    sys.stdout.write(result.as_html())


if __name__ == "__main__":
    main()
