from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any

from ._tbl_preview import (
    _apply_column_subset,
    _compute_col_widths,
    _detect_alignments,
    _normalize_data,
    _render_body_html,
    _render_colgroup_html,
    _render_column_labels_html,
    _render_header_html,
    _render_scoped_css,
)

# ---------------------------------------------------------------------------
# Public result class
# ---------------------------------------------------------------------------


class TblExplorer:
    """Interactive table explorer with `_repr_html_()` support."""

    def __init__(self, html: str) -> None:
        self._html = html

    def _repr_html_(self) -> str:  # noqa: N802
        return self._html

    def as_html(self) -> str:
        """Return the raw HTML string (includes `<script>` tags)."""
        return self._html

    def save(self, path: str | Path) -> None:
        """Write the self-contained HTML to a file."""
        Path(path).write_text(self._html, encoding="utf-8")

    def __repr__(self) -> str:
        return f"TblExplorer({len(self._html)} chars)"


# ---------------------------------------------------------------------------
# JSON serialization
# ---------------------------------------------------------------------------


def _serialize_value(v: Any) -> Any:
    """Convert a Python value to a JSON-safe value, preserving type fidelity."""
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        import math

        if math.isnan(v) or math.isinf(v):
            return None  # JSON has no NaN/Inf
        return v
    return str(v)


def _serialize_data_blob(
    col_names: list[str],
    col_dtypes: list[str],
    alignments: list[str],
    all_rows: list[list[Any]],
    total_rows: int,
    tbl_type: str,
    config: dict[str, Any],
) -> str:
    r"""Serialize the table data + config into a JSON string.

    The JSON is safe for embedding inside `<script type="application/json">`: occurrences of `</`
    are escaped as `<\/` to prevent premature tag closure.
    """
    columns = [
        {"name": n, "dtype": d, "align": a} for n, d, a in zip(col_names, col_dtypes, alignments)
    ]
    rows = [[_serialize_value(v) for v in row] for row in all_rows]

    blob = {
        "columns": columns,
        "rows": rows,
        "totalRows": total_rows,
        "tableType": tbl_type,
        "config": config,
    }

    raw = json.dumps(blob, separators=(",", ":"), ensure_ascii=False)
    # Prevent </script> injection
    return raw.replace("</", r"<\/")


# ---------------------------------------------------------------------------
# Explorer-specific CSS (toolbar + pagination + sort indicators)
# ---------------------------------------------------------------------------


def _render_explorer_css(uid: str) -> str:
    """Return CSS for the interactive toolbar, sort indicators, and pagination."""
    s = f"#gd-tbl-{uid}"
    return f"""<style>
/* ── Toolbar ─────────────────────────────────────── */
{s} .gd-tbl-toolbar {{
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px 0;
  align-items: center;
  font-family: 'IBM Plex Sans', system-ui, -apple-system, sans-serif;
  font-size: 13px;
}}
{s} .gd-tbl-filter {{
  flex: 1 1 200px;
  min-width: 150px;
  padding: 6px 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 13px;
  font-family: inherit;
  background: #fff;
  color: #333;
  outline: none;
  transition: border-color 0.15s;
}}
{s} .gd-tbl-filter:focus {{
  border-color: #6699CC;
  box-shadow: 0 0 0 2px rgba(102,153,204,0.2);
}}
{s} .gd-tbl-btn {{
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #f8f8f8;
  color: #333;
  font-size: 12px;
  font-weight: 500;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
  white-space: nowrap;
}}
{s} .gd-tbl-btn:hover {{
  background: #eee;
  border-color: #aaa;
}}
{s} .gd-tbl-btn:focus-visible {{
  outline: 2px solid #6699CC;
  outline-offset: 1px;
}}
{s} .gd-tbl-btn-active {{
  background: #e0edff;
  border-color: #6699CC;
}}
{s} .gd-tbl-btn-icon {{
  padding: 5px 7px;
  line-height: 0;
}}
{s} .gd-tbl-btn-icon svg {{
  display: block;
}}
/* Copy-success green checkmark state */
{s} .gd-tbl-btn-copied {{
  color: #198754;
  border-color: #198754;
}}
/* ── Button wrapper + tooltip ────────────────────── */
{s} .gd-tbl-btn-wrap {{
  position: relative;
  display: inline-block;
}}
{s} .gd-tbl-tooltip {{
  visibility: hidden;
  opacity: 0;
  position: absolute;
  top: calc(100% + 4px);
  left: 50%;
  transform: translateX(-50%);
  padding: 3px 8px;
  background: #333;
  color: #fff;
  border-radius: 3px;
  font-size: 11px;
  white-space: nowrap;
  pointer-events: none;
  transition: opacity 0.15s;
  z-index: 100;
}}
/* Keep tooltip from overflowing right edge */
{s} .gd-tbl-btn-wrap:last-child .gd-tbl-tooltip {{
  left: auto;
  right: 0;
  transform: none;
}}
{s} .gd-tbl-btn-wrap:hover .gd-tbl-tooltip {{
  visibility: visible;
  opacity: 1;
}}
/* ── Column toggle dropdown ──────────────────────── */
{s} .gd-tbl-col-wrap {{
  position: relative;
  display: inline-block;
}}
{s} .gd-tbl-col-menu {{
  display: none;
  position: absolute;
  top: 100%;
  left: 0;
  z-index: 10;
  min-width: 180px;
  max-height: 300px;
  overflow-y: auto;
  margin-top: 4px;
  padding: 6px 0;
  background: #fff;
  border: 1px solid #ccc;
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}}
{s} .gd-tbl-col-menu.open {{
  display: block;
}}
{s} .gd-tbl-col-option {{
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  cursor: pointer;
  font-size: 12px;
  user-select: none;
}}
{s} .gd-tbl-col-option:hover {{
  background: #f0f0f0;
}}
/* ── Sort indicators ─────────────────────────────── */
{s} .gd-tbl-sortable {{
  cursor: pointer;
  user-select: none;
  position: relative;
}}
{s} .gd-tbl-sort-icon {{
  display: inline-block;
  width: 10px;
  height: 14px;
  margin-left: 4px;
  color: #bbb;
  vertical-align: middle;
}}
{s} .gd-tbl-sort-icon svg {{
  display: block;
  width: 10px;
  height: 14px;
  fill: currentColor;
}}
{s} .gd-tbl-sort-asc .gd-tbl-sort-icon,
{s} .gd-tbl-sort-desc .gd-tbl-sort-icon {{
  color: #6699CC;
}}
/* ── Search highlight ────────────────────────────── */
{s} .gd-tbl-highlight {{
  background-color: #FFEEBA;
  border-radius: 2px;
  padding: 0 1px;
}}
/* ── Pagination ──────────────────────────────────── */
{s} .gd-tbl-pagination {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 0;
  font-family: 'IBM Plex Sans', system-ui, -apple-system, sans-serif;
  font-size: 12px;
  color: #666;
}}
{s} .gd-tbl-page-info {{
  white-space: nowrap;
}}
{s} .gd-tbl-page-nav {{
  display: flex;
  gap: 2px;
  align-items: center;
}}
{s} .gd-tbl-page-btn {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  height: 28px;
  padding: 0 6px;
  border: 1px solid #ddd;
  border-radius: 3px;
  background: #fff;
  color: #333;
  cursor: pointer;
  font-size: 12px;
  font-family: inherit;
  transition: background 0.1s;
}}
{s} .gd-tbl-page-btn:hover {{
  background: #f0f0f0;
}}
{s} .gd-tbl-page-btn.active {{
  background: #6699CC;
  color: #fff;
  border-color: #6699CC;
}}
{s} .gd-tbl-page-btn:disabled {{
  opacity: 0.4;
  cursor: default;
}}
{s} .gd-tbl-page-ellipsis {{
  padding: 0 4px;
  color: #999;
}}
/* ── Dark mode ───────────────────────────────────── */
body.quarto-dark {s} .gd-tbl-filter,
html.quarto-dark {s} .gd-tbl-filter,
:root[data-bs-theme="dark"] {s} .gd-tbl-filter {{
  background-color: #2a2a3e;
  border-color: #444;
  color: #e0e0e0;
}}
body.quarto-dark {s} .gd-tbl-filter:focus,
html.quarto-dark {s} .gd-tbl-filter:focus,
:root[data-bs-theme="dark"] {s} .gd-tbl-filter:focus {{
  border-color: #6699CC;
  box-shadow: 0 0 0 2px rgba(102,153,204,0.3);
}}
body.quarto-dark {s} .gd-tbl-btn,
html.quarto-dark {s} .gd-tbl-btn,
:root[data-bs-theme="dark"] {s} .gd-tbl-btn {{
  background: #2a2a3e;
  border-color: #444;
  color: #ccc;
}}
body.quarto-dark {s} .gd-tbl-btn:hover,
html.quarto-dark {s} .gd-tbl-btn:hover,
:root[data-bs-theme="dark"] {s} .gd-tbl-btn:hover {{
  background: #353550;
  border-color: #666;
}}
body.quarto-dark {s} .gd-tbl-btn-active,
html.quarto-dark {s} .gd-tbl-btn-active,
:root[data-bs-theme="dark"] {s} .gd-tbl-btn-active {{
  background: #2a3a5e;
  border-color: #6699CC;
}}
body.quarto-dark {s} .gd-tbl-col-menu,
html.quarto-dark {s} .gd-tbl-col-menu,
:root[data-bs-theme="dark"] {s} .gd-tbl-col-menu {{
  background: #2a2a3e;
  border-color: #444;
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}}
body.quarto-dark {s} .gd-tbl-col-option:hover,
html.quarto-dark {s} .gd-tbl-col-option:hover,
:root[data-bs-theme="dark"] {s} .gd-tbl-col-option:hover {{
  background: #353550;
}}
body.quarto-dark {s} .gd-tbl-highlight,
html.quarto-dark {s} .gd-tbl-highlight,
:root[data-bs-theme="dark"] {s} .gd-tbl-highlight {{
  background-color: #5C4A1E;
  color: #FFE082;
}}
body.quarto-dark {s} .gd-tbl-page-btn,
html.quarto-dark {s} .gd-tbl-page-btn,
:root[data-bs-theme="dark"] {s} .gd-tbl-page-btn {{
  background: #2a2a3e;
  border-color: #444;
  color: #ccc;
}}
body.quarto-dark {s} .gd-tbl-page-btn:hover,
html.quarto-dark {s} .gd-tbl-page-btn:hover,
:root[data-bs-theme="dark"] {s} .gd-tbl-page-btn:hover {{
  background: #353550;
}}
body.quarto-dark {s} .gd-tbl-page-btn.active,
html.quarto-dark {s} .gd-tbl-page-btn.active,
:root[data-bs-theme="dark"] {s} .gd-tbl-page-btn.active {{
  background: #6699CC;
  border-color: #6699CC;
  color: #fff;
}}
body.quarto-dark {s} .gd-tbl-pagination,
html.quarto-dark {s} .gd-tbl-pagination,
:root[data-bs-theme="dark"] {s} .gd-tbl-pagination {{
  color: #999;
}}
body.quarto-dark {s} .gd-tbl-sort-icon,
html.quarto-dark {s} .gd-tbl-sort-icon,
:root[data-bs-theme="dark"] {s} .gd-tbl-sort-icon {{
  color: #555;
}}
body.quarto-dark {s} .gd-tbl-sort-asc .gd-tbl-sort-icon,
html.quarto-dark {s} .gd-tbl-sort-asc .gd-tbl-sort-icon,
:root[data-bs-theme="dark"] {s} .gd-tbl-sort-asc .gd-tbl-sort-icon,
body.quarto-dark {s} .gd-tbl-sort-desc .gd-tbl-sort-icon,
html.quarto-dark {s} .gd-tbl-sort-desc .gd-tbl-sort-icon,
:root[data-bs-theme="dark"] {s} .gd-tbl-sort-desc .gd-tbl-sort-icon {{
  color: #88bbee;
}}
body.quarto-dark {s} .gd-tbl-tooltip,
html.quarto-dark {s} .gd-tbl-tooltip,
:root[data-bs-theme="dark"] {s} .gd-tbl-tooltip {{
  background: #e0e0e0;
  color: #1a1a2e;
}}
body.quarto-dark {s} .gd-tbl-btn-copied,
html.quarto-dark {s} .gd-tbl-btn-copied,
:root[data-bs-theme="dark"] {s} .gd-tbl-btn-copied {{
  color: #4ade80;
  border-color: #4ade80;
}}
</style>"""


# ---------------------------------------------------------------------------
# Inline JS — reads from the companion asset file or embeds inline
# ---------------------------------------------------------------------------

_JS_ASSET_NAME = "tbl-explorer.js"


def _get_js_source() -> str:
    """Load the tbl-explorer.js source from the assets directory."""
    asset_path = Path(__file__).parent / "assets" / _JS_ASSET_NAME
    if asset_path.exists():
        return asset_path.read_text(encoding="utf-8")
    raise FileNotFoundError(
        f"Cannot find {_JS_ASSET_NAME} at {asset_path}. "
        "Ensure the great_docs/assets/ directory contains the file."
    )


# Cache the JS source after first load
_js_cache: str | None = None


def _get_js_inline() -> str:
    """Return the JS source, cached after first load."""
    global _js_cache  # noqa: PLW0603
    if _js_cache is None:
        _js_cache = _get_js_source()
    return _js_cache


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

# Threshold for emitting a size warning (rows)
_LARGE_DATASET_THRESHOLD = 10_000


def tbl_explorer(
    data: Any,
    columns: list[str] | None = None,
    show_row_numbers: bool = True,
    show_dtypes: bool = True,
    show_dimensions: bool = True,
    max_col_width: int = 250,
    min_tbl_width: int = 500,
    caption: str | None = None,
    highlight_missing: bool = True,
    page_size: int = 20,
    sortable: bool = True,
    filterable: bool = True,
    column_toggle: bool = True,
    copyable: bool = True,
    downloadable: bool = True,
    resizable: bool = False,
    sticky_header: bool = True,
    search_highlight: bool = True,
    id: str | None = None,
) -> TblExplorer:
    """Generate an interactive table explorer from tabular data.

    Produces a self-contained HTML widget with a static table baseline that is progressively
    enhanced by JavaScript to add sorting, filtering, pagination, column toggling,
    copy-to-clipboard, and CSV download.

    Parameters
    ----------
    data
        The table to explore. Accepts the same inputs as `~great_docs.tbl_preview`: Polars/Pandas
        DataFrames, PyArrow Tables, file paths (CSV/TSV/JSONL/Parquet/Feather/Arrow IPC),
        column-oriented dicts, or row-oriented lists of dicts.
    columns
        Subset of columns to show, by default `None` (all columns).
    show_row_numbers
        Display a row-number gutter column on the left.
    show_dtypes
        Display short dtype labels beneath column names.
    show_dimensions
        Display the header banner with source-type badge and row/column counts.
    max_col_width
        Maximum pixel width for any column.
    min_tbl_width
        Minimum total table width in pixels.
    caption
        Optional caption text displayed above the column headers.
    highlight_missing
        Highlight `None`/`NaN`/`NA` values in red.
    page_size
        Number of rows per page. Set to `0` to disable pagination and show all rows at once.
    sortable
        Enable click-to-sort on column headers.
    filterable
        Enable the global filter text input.
    column_toggle
        Enable the column-visibility dropdown.
    copyable
        Enable the copy-to-clipboard button.
    downloadable
        Enable the CSV download button.
    resizable
        Enable column drag-resize (reserved for future use).
    sticky_header
        Make column headers sticky on vertical scroll.
    search_highlight
        Highlight matching cell text when filtering.
    id
        HTML `id` for the container. Auto-generated if `None`.

    Returns
    -------
    TblExplorer
        A rendered interactive table object with `_repr_html_()` support.

    Examples
    --------
    ```{python}
    from great_docs import tbl_explorer

    tbl_explorer({
        "city": ["Tokyo", "Paris", "New York", "London", "Sydney"],
        "population": [13960000, 2161000, 8336000, 8982000, 5312000],
        "country": ["Japan", "France", "USA", "UK", "Australia"],
    })
    ```
    """
    import warnings

    # 1. Normalize input data
    col_names, col_dtypes, all_rows, total_rows, tbl_type = _normalize_data(data)
    original_n_cols = len(col_names)

    if total_rows > _LARGE_DATASET_THRESHOLD:
        warnings.warn(
            f"tbl_explorer() is embedding {total_rows:,} rows as inline JSON. "
            f"For datasets larger than {_LARGE_DATASET_THRESHOLD:,} rows, consider "
            f"using tbl_preview() with n_head/n_tail instead.",
            UserWarning,
            stacklevel=2,
        )

    # 2. Apply column subset
    col_names, col_dtypes, all_rows = _apply_column_subset(col_names, col_dtypes, all_rows, columns)

    # 3. Detect alignments
    alignments = _detect_alignments(col_dtypes)

    # 4. Build the first page of rows for the static fallback table
    if page_size > 0 and total_rows > page_size:
        fallback_rows = all_rows[:page_size]
        fallback_row_numbers = list(range(page_size))
        is_full = False
        n_head_fallback = page_size
    else:
        fallback_rows = all_rows
        fallback_row_numbers = list(range(total_rows))
        is_full = True
        n_head_fallback = total_rows

    # 5. Compute column widths (based on fallback rows for initial render)
    col_widths, rownum_width = _compute_col_widths(
        col_names,
        col_dtypes,
        fallback_rows,
        max_col_width,
        min_tbl_width,
        show_row_numbers,
        fallback_row_numbers,
    )

    # 6. Generate unique ID
    uid = id or secrets.token_hex(4)

    total_cols = len(col_names) + (1 if show_row_numbers else 0)

    # 7. Config dict for the JSON blob
    config = {
        "pageSize": page_size,
        "sortable": sortable,
        "filterable": filterable,
        "columnToggle": column_toggle,
        "copyable": copyable,
        "downloadable": downloadable,
        "resizable": resizable,
        "stickyHeader": sticky_header,
        "searchHighlight": search_highlight,
        "showRowNumbers": show_row_numbers,
        "showDtypes": show_dtypes,
        "highlightMissing": highlight_missing,
    }

    # 8. Serialize full data as JSON
    data_json = _serialize_data_blob(
        col_names, col_dtypes, alignments, all_rows, total_rows, tbl_type, config
    )

    # 9. Render static fallback HTML (same structure as tbl_preview)
    base_css = _render_scoped_css(uid)
    explorer_css = _render_explorer_css(uid)

    header = _render_header_html(
        uid, tbl_type, total_rows, original_n_cols, caption, show_dimensions, total_cols
    )
    colgroup = _render_colgroup_html(col_widths, rownum_width, show_row_numbers)
    column_labels = _render_column_labels_html(
        col_names, col_dtypes, alignments, show_dtypes, show_row_numbers
    )
    body = _render_body_html(
        fallback_rows,
        fallback_row_numbers,
        col_names,
        alignments,
        col_widths,
        n_head_fallback,
        is_full,
        show_row_numbers,
        highlight_missing,
    )

    # 10. Load JS
    js_source = _get_js_inline()

    # 11. Assemble
    html = (
        f'<div id="gd-tbl-{uid}" class="gd-tbl-explorer" '
        f'style="padding-left: 0px; overflow-x: auto; overflow-y: hidden; '
        f'width: 100%; max-width: 100%;">\n'
        f"{base_css}\n"
        f"{explorer_css}\n"
        f'<script type="application/json" class="gd-tbl-data" '
        f'data-table-id="gd-tbl-{uid}">\n{data_json}\n</script>\n'
        f'<table class="gt_table" data-quarto-disable-processing="true" '
        f'data-quarto-bootstrap="false">\n'
        f"{colgroup}\n"
        f"<thead>\n{header}\n{column_labels}\n</thead>\n"
        f"{body}\n"
        f"</table>\n"
        f"<script>{js_source}</script>\n"
        f"</div>"
    )

    return TblExplorer(html)
