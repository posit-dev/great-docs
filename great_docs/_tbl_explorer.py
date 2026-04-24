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
/* ── Table scroll wrapper ────────────────────────── */
{s} .gd-tbl-scroll {{
  overflow-x: auto;
  overflow-y: hidden;
  width: 100%;
}}
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
/* ── Filter bar ──────────────────────────────────── */
{s} .gd-tbl-filter-bar {{
  flex: 1 1 200px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  min-height: 30px;
  padding: 3px 6px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #fff;
  position: relative;
}}
{s} .gd-tbl-filter-tokens {{
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}}
{s} .gd-tbl-filter-token {{
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 2px 4px 2px 8px;
  background: #e8f0fe;
  border: 1px solid #c4d9f2;
  border-radius: 12px;
  font-size: 11px;
  color: #1a3a5c;
  white-space: nowrap;
  max-width: 260px;
  line-height: 1.4;
}}
{s} .gd-tbl-filter-token-text {{
  overflow: hidden;
  text-overflow: ellipsis;
}}
{s} .gd-tbl-filter-token-x {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border: none;
  background: #d0dfef;
  color: #4a6a8a;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  border-radius: 50%;
  padding: 0;
  padding-bottom: 2px;
  line-height: 1;
  flex-shrink: 0;
  transition: background 0.1s, color 0.1s;
}}
{s} .gd-tbl-filter-token-x:hover {{
  background: #a0bdd8;
  color: #1a3a5c;
}}
{s} .gd-tbl-filter-token-case {{
  font-size: 9px;
  font-weight: 700;
  color: #4477aa;
  border: 1px solid #a0bdd8;
  border-radius: 3px;
  padding: 0 3px;
  line-height: 1.4;
  flex-shrink: 0;
  font-family: 'IBM Plex Sans', system-ui, sans-serif;
}}
{s} .gd-tbl-filter-add {{
  flex-shrink: 0;
  border: none;
  background: none;
  padding: 3px;
  color: #6699CC;
}}
{s} .gd-tbl-filter-add:hover {{
  background: #eef3fb;
  border-radius: 3px;
}}
/* ── Filter wizard dropdown ──────────────────────── */
{s} .gd-tbl-filter-wizard {{
  position: absolute;
  top: calc(100% + 2px);
  left: 0;
  z-index: 200;
  background: #fff;
  border: 1px solid #ccc;
  border-radius: 6px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
  padding: 8px 0;
  min-width: 200px;
  max-width: 320px;
  max-height: 300px;
  overflow-y: auto;
  font-size: 12px;
}}
{s} .gd-tbl-fw-label {{
  display: block;
  padding: 4px 12px 4px;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #888;
  font-weight: 600;
}}
{s} .gd-tbl-fw-options {{
  display: flex;
  flex-direction: column;
}}
{s} .gd-tbl-fw-option {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 5px 12px;
  border: none;
  background: none;
  text-align: left;
  font-size: 12px;
  font-family: inherit;
  color: #333;
  cursor: pointer;
  transition: background 0.1s;
}}
{s} .gd-tbl-fw-option:hover {{
  background: #f0f4fb;
}}
{s} .gd-tbl-fw-dtype {{
  font-size: 9px;
  color: #999;
  background: #f0f0f0;
  padding: 1px 5px;
  border-radius: 3px;
  margin-left: 8px;
  font-family: 'IBM Plex Mono', ui-monospace, monospace;
}}
{s} .gd-tbl-fw-input {{
  margin: 4px 12px;
  padding: 5px 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 12px;
  font-family: inherit;
  background: #fff;
  color: #333;
  outline: none;
  width: calc(100% - 24px);
  box-sizing: border-box;
}}
{s} .gd-tbl-fw-input:focus {{
  border-color: #6699CC;
  box-shadow: 0 0 0 2px rgba(102,153,204,0.2);
}}
{s} .gd-tbl-fw-between {{
  display: flex;
  align-items: center;
  gap: 0;
  padding: 0 4px;
}}
{s} .gd-tbl-fw-between .gd-tbl-fw-input {{
  flex: 1;
  margin: 4px;
  min-width: 60px;
}}
{s} .gd-tbl-fw-sep {{
  font-size: 11px;
  color: #888;
  flex-shrink: 0;
}}
{s} .gd-tbl-fw-commit {{
  margin: 4px 12px 6px;
  font-size: 11px;
  padding: 4px 14px;
}}
{s} .gd-tbl-fw-input-row {{
  display: flex;
  align-items: center;
  gap: 0;
  padding: 0 8px;
}}
{s} .gd-tbl-fw-input-row .gd-tbl-fw-input {{
  flex: 1;
  margin: 4px 0;
  width: auto;
}}
{s} .gd-tbl-fw-case {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 26px;
  margin-left: 4px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #f8f8f8;
  color: #999;
  font-size: 11px;
  font-weight: 700;
  font-family: 'IBM Plex Sans', system-ui, sans-serif;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.15s;
}}
{s} .gd-tbl-fw-case:hover {{
  border-color: #999;
  color: #666;
}}
{s} .gd-tbl-fw-case.active {{
  background: #e0edff;
  border-color: #6699CC;
  color: #336699;
}}
{s} .gd-tbl-btn {{
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 12px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #f8f8f8;
  color: #333;
  font-size: 12px;
  font-weight: 500;
  font-family: inherit;
  line-height: 14px;
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
body.quarto-dark {s} .gd-tbl-filter-bar,
html.quarto-dark {s} .gd-tbl-filter-bar,
:root[data-bs-theme="dark"] {s} .gd-tbl-filter-bar {{
  background-color: #2a2a3e;
  border-color: #444;
}}
body.quarto-dark {s} .gd-tbl-filter-token,
html.quarto-dark {s} .gd-tbl-filter-token,
:root[data-bs-theme="dark"] {s} .gd-tbl-filter-token {{
  background: #2d3a50;
  border-color: #3d5070;
  color: #b0ccee;
}}
body.quarto-dark {s} .gd-tbl-filter-token-x:hover,
html.quarto-dark {s} .gd-tbl-filter-token-x:hover,
:root[data-bs-theme="dark"] {s} .gd-tbl-filter-token-x:hover {{
  background: #3d5070;
  color: #e0e8f0;
}}
body.quarto-dark {s} .gd-tbl-filter-token-case,
html.quarto-dark {s} .gd-tbl-filter-token-case,
:root[data-bs-theme="dark"] {s} .gd-tbl-filter-token-case {{
  color: #88bbee;
  border-color: #4d6888;
}}
body.quarto-dark {s} .gd-tbl-fw-case,
html.quarto-dark {s} .gd-tbl-fw-case,
:root[data-bs-theme="dark"] {s} .gd-tbl-fw-case {{
  background: #2a2a3e;
  border-color: #555;
  color: #888;
}}
body.quarto-dark {s} .gd-tbl-fw-case:hover,
html.quarto-dark {s} .gd-tbl-fw-case:hover,
:root[data-bs-theme="dark"] {s} .gd-tbl-fw-case:hover {{
  border-color: #888;
  color: #bbb;
}}
body.quarto-dark {s} .gd-tbl-fw-case.active,
html.quarto-dark {s} .gd-tbl-fw-case.active,
:root[data-bs-theme="dark"] {s} .gd-tbl-fw-case.active {{
  background: #2d3a50;
  border-color: #6699CC;
  color: #88bbee;
}}
body.quarto-dark {s} .gd-tbl-filter-add,
html.quarto-dark {s} .gd-tbl-filter-add,
:root[data-bs-theme="dark"] {s} .gd-tbl-filter-add {{
  color: #88bbee;
}}
body.quarto-dark {s} .gd-tbl-filter-add:hover,
html.quarto-dark {s} .gd-tbl-filter-add:hover,
:root[data-bs-theme="dark"] {s} .gd-tbl-filter-add:hover {{
  background: #353550;
}}
body.quarto-dark {s} .gd-tbl-filter-wizard,
html.quarto-dark {s} .gd-tbl-filter-wizard,
:root[data-bs-theme="dark"] {s} .gd-tbl-filter-wizard {{
  background: #1e1e32;
  border-color: #444;
  box-shadow: 0 4px 16px rgba(0,0,0,0.4);
}}
body.quarto-dark {s} .gd-tbl-fw-option,
html.quarto-dark {s} .gd-tbl-fw-option,
:root[data-bs-theme="dark"] {s} .gd-tbl-fw-option {{
  color: #ddd;
}}
body.quarto-dark {s} .gd-tbl-fw-option:hover,
html.quarto-dark {s} .gd-tbl-fw-option:hover,
:root[data-bs-theme="dark"] {s} .gd-tbl-fw-option:hover {{
  background: #2a2a44;
}}
body.quarto-dark {s} .gd-tbl-fw-dtype,
html.quarto-dark {s} .gd-tbl-fw-dtype,
:root[data-bs-theme="dark"] {s} .gd-tbl-fw-dtype {{
  background: #333;
  color: #aaa;
}}
body.quarto-dark {s} .gd-tbl-fw-input,
html.quarto-dark {s} .gd-tbl-fw-input,
:root[data-bs-theme="dark"] {s} .gd-tbl-fw-input {{
  background: #2a2a3e;
  border-color: #555;
  color: #e0e0e0;
}}
body.quarto-dark {s} .gd-tbl-fw-input:focus,
html.quarto-dark {s} .gd-tbl-fw-input:focus,
:root[data-bs-theme="dark"] {s} .gd-tbl-fw-input:focus {{
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
    """
    Generate an interactive table explorer from almost any tabular data source.

    The `tbl_explorer()` function creates a self-contained, interactive HTML table widget from
    tabular data. Pass it a Polars DataFrame, a Pandas DataFrame, a PyArrow Table, a file path to a
    CSV / TSV / JSONL / Parquet / Feather file, a column-oriented dictionary, or a list of row
    dictionaries—and get back an interactive table with sorting, token-based filtering, pagination,
    column toggling, copy-to-clipboard, and CSV download.

    The output uses **progressive enhancement**: the initial HTML contains a fully rendered static
    table (the first page of data) that is readable without JavaScript. When JavaScript is available,
    the static table is enhanced with interactive controls. All row data is embedded as inline JSON
    within the HTML, so the widget is completely self-contained with no external dependencies.

    The interactive toolbar includes a token-based filter bar (with type-aware operators for string,
    numeric, and boolean columns), a column visibility dropdown, copy and download buttons, and a
    reset control. Column headers are clickable for single-column sorting, and shift-click enables
    multi-column sorting. Pagination is enabled by default at 20 rows per page.

    The output is a :class:`TblExplorer` object with `_repr_html_()` support, so it displays
    automatically in Jupyter notebooks and Quarto code cells. All CSS is scoped to a unique id, and
    the table includes full dark-mode support.

    Parameters
    ----------
    data
        The table to explore. This can be a Polars DataFrame, a Pandas DataFrame, a PyArrow Table,
        a file path (as a string or `pathlib.Path` object), a column-oriented dictionary, or a list
        of row dictionaries. When providing a file path, the extension determines the loader:
        `.csv`, `.tsv`, `.jsonl` (or `.ndjson`), `.parquet`, `.feather`, and `.arrow` (Arrow IPC)
        are all supported. Read the *Supported Input Data Types* section for details on each
        accepted format.
    columns
        The columns to display in the explorer, by default `None` (all columns are shown). This
        can be a list of column name strings. If any name does not match a column in the table, a
        `KeyError` is raised. This is useful for focusing on a subset of a wide dataset.
    show_row_numbers
        Should row numbers be shown? The numbers appear in a narrow gutter column on the left side
        of the table, separated from the data columns by a subtle blue vertical line. By default,
        this is set to `True`.
    show_dtypes
        Should data type labels be displayed beneath each column name? The labels use short
        abbreviations (e.g., `i64` for 64-bit integer, `str` for string, `f64` for 64-bit float).
        By default, this is set to `True`.
    show_dimensions
        Should the header banner be shown? The banner displays a colored badge identifying the data
        source type alongside row and column counts in labeled pill badges. By default, this is set
        to `True`.
    max_col_width
        The maximum width of any single column in pixels. Column widths are computed automatically
        to fit their content up to this ceiling, beyond which cell text is truncated with an
        ellipsis. The default value is `250` pixels.
    min_tbl_width
        The minimum total width of the table in pixels. If the sum of the computed column widths is
        less than this value, columns are proportionally widened to fill the available space. The
        default value is `500` pixels.
    caption
        An optional caption string displayed below the header banner and above the column headers.
        Useful for labeling an explorer with a dataset name or description. By default, no caption
        is shown.
    highlight_missing
        Should missing values (`None`, `NaN`, `NA`) be highlighted? When `True` (the default),
        missing cells are displayed in red text on a light red background so they stand out at a
        glance.
    page_size
        The number of rows to display per page. The default value is `20`. Set to `0` to disable
        pagination entirely and display all rows at once. The pagination bar shows the current range
        (e.g., "Showing 1–20 of 150 rows") and page navigation buttons.
    sortable
        Should column sorting be enabled? When `True` (the default), clicking a column header
        cycles through ascending → descending → unsorted. Hold **Shift** and click to add
        multi-column sorting. Sort indicators appear as SVG arrows next to column names.
    filterable
        Should the token-based filter bar be shown? When `True` (the default), a filter bar appears
        in the toolbar with a **+** button to add structured filters. Each filter is a token with a
        column, operator, and optional value. Available operators depend on the column type:
        string columns offer contains, starts with, ends with, etc.; numeric columns offer
        comparison operators including between; boolean columns offer is true/is false. Filters
        support case-sensitive matching via an **Aa** toggle.
    column_toggle
        Should the column visibility dropdown be shown? When `True` (the default), a **Columns**
        button appears in the toolbar. Clicking it opens a dropdown with checkboxes for each
        column. At least one column must remain visible.
    copyable
        Should the copy-to-clipboard button be shown? When `True` (the default), a clipboard icon
        appears in the toolbar. Clicking it copies the currently visible page of data as
        tab-separated values. On success, the icon briefly changes to a green checkmark.
    downloadable
        Should the CSV download button be shown? When `True` (the default), a download icon appears
        in the toolbar. Clicking it downloads the full filtered dataset (all pages) as a CSV file.
    resizable
        Should column drag-resize be enabled? Reserved for future use. Currently has no effect.
        The default value is `False`.
    sticky_header
        Should column headers remain visible when scrolling vertically? When `True` (the default),
        the header row sticks to the top of the table container as the user scrolls through rows.
    search_highlight
        Should matching cell text be highlighted when a "contains" filter is active? When `True`
        (the default), text matching the filter value is highlighted with a colored background. Set
        to `False` to disable highlighting.
    id
        An HTML `id` attribute for the outer `<div>` container. If `None` (the default), a unique
        ID is auto-generated using `secrets.token_hex(4)`. Providing your own ID is useful when you
        need to target the table with custom CSS or JavaScript.

    Returns
    -------
    TblExplorer
        A rendered interactive table object. The object has `_repr_html_()` for automatic notebook
        display.

    Supported Input Data Types
    --------------------------
    The `data` parameter accepts any of the following:

    - **Polars DataFrame** — displays a blue *Polars* badge
    - **Pandas DataFrame** — displays a dark purple *Pandas* badge
    - **PyArrow Table** — displays an indigo *Arrow* badge
    - **CSV file** (`.csv`) — loaded automatically; displays a cream *CSV* badge
    - **TSV file** (`.tsv`) — loaded automatically; displays a green *TSV* badge
    - **JSONL file** (`.jsonl` or `.ndjson`) — loaded line-by-line; displays a blue *JSONL*
      badge
    - **Parquet file** (`.parquet`) — requires `polars`, `pandas`, or `pyarrow`; displays
      a purple *Parquet* badge
    - **Feather / Arrow IPC file** (`.feather` or `.arrow`) — requires `polars`, `pandas`,
      or `pyarrow`; displays an orange *Feather* badge
    - **Dictionary** (column-oriented, `dict[str, list]`) — displays a gray *Table* badge
    - **List of dictionaries** (row-oriented, `list[dict]`) — displays a gray *Table* badge

    For file-based inputs, pass a string or `pathlib.Path` object. The file extension is used to
    determine the format. Polars is preferred for loading when available; Pandas and PyArrow are
    used as fallbacks.

    Examples
    --------
    The simplest way to explore a table is to pass a Python dictionary:

    ```{python}
    from great_docs import tbl_explorer

    tbl_explorer({
        "city": ["Tokyo", "Paris", "New York", "London", "Sydney"],
        "population": [13960000, 2161000, 8336000, 8982000, 5312000],
        "country": ["Japan", "France", "USA", "UK", "Australia"],
    })
    ```

    You can also pass a Polars DataFrame:

    ```{python}
    import polars as pl

    df = pl.DataFrame({
        "product": ["Widget", "Gadget", "Gizmo", "Doohickey", "Thingamajig"],
        "category": ["Electronics", "Tools", "Kitchen", "Garden", "Office"],
        "price": [29.99, 49.50, 12.00, 8.75, 199.99],
        "in_stock": [True, False, True, True, False],
    })

    tbl_explorer(df)
    ```

    Load a CSV file and show only specific columns:

    ```python
    tbl_explorer("data/sales.csv", columns=["product", "revenue", "units"])
    ```

    Disable pagination to show all rows at once:

    ```python
    tbl_explorer(df, page_size=0)
    ```

    Create a minimal, sort-only table with no toolbar controls:

    ```python
    tbl_explorer(
        df,
        sortable=True,
        filterable=False,
        column_toggle=False,
        copyable=False,
        downloadable=False,
        page_size=0,
    )
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
        f'style="padding-left: 0px; overflow: hidden; '
        f'width: 100%; max-width: 100%;">\n'
        f"{base_css}\n"
        f"{explorer_css}\n"
        f'<script type="application/json" class="gd-tbl-data" '
        f'data-table-id="gd-tbl-{uid}">\n{data_json}\n</script>\n'
        f'<div class="gd-tbl-scroll">\n'
        f'<table class="gt_table" data-quarto-disable-processing="true" '
        f'data-quarto-bootstrap="false">\n'
        f"{colgroup}\n"
        f"<thead>\n{header}\n{column_labels}\n</thead>\n"
        f"{body}\n"
        f"</table>\n"
        f"</div>\n"
        f"<script>{js_source}</script>\n"
        f"</div>"
    )

    return TblExplorer(html)
