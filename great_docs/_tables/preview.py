from __future__ import annotations

import html as _html_mod
import secrets
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Public result class
# ---------------------------------------------------------------------------


class TblPreview:
    """Rendered table preview with `_repr_html_()` support."""

    def __init__(self, html: str) -> None:
        self._html = html

    def _repr_html_(self) -> str:
        return self._html

    def as_html(self) -> str:
        """Return the raw HTML string."""
        return self._html

    def save(self, path: str | Path) -> None:
        """Write the HTML to a file."""
        Path(path).write_text(self._html, encoding="utf-8")

    def __repr__(self) -> str:
        return f"TblPreview({len(self._html)} chars)"


# ---------------------------------------------------------------------------
# Table-type badge colors (subset of Pointblank's TABLE_TYPE_STYLES)
# ---------------------------------------------------------------------------

_TABLE_TYPE_STYLES: dict[str, dict[str, str]] = {
    "polars": {"bg": "#0075FF", "fg": "#FFFFFF", "label": "Polars"},
    "pandas": {"bg": "#150458", "fg": "#FFFFFF", "label": "Pandas"},
    "csv": {"bg": "#FFF8E1", "fg": "#7A6200", "label": "CSV"},
    "tsv": {"bg": "#E8F5E9", "fg": "#2E7D32", "label": "TSV"},
    "jsonl": {"bg": "#E3F2FD", "fg": "#1565C0", "label": "JSONL"},
    "arrow": {"bg": "#E8EAF6", "fg": "#283593", "label": "Arrow"},
    "parquet": {"bg": "#F3E5F5", "fg": "#6A1B9A", "label": "Parquet"},
    "feather": {"bg": "#FFF3E0", "fg": "#E65100", "label": "Feather"},
    "dict": {"bg": "#F0F0F0", "fg": "#333333", "label": "Table"},
}

# ---------------------------------------------------------------------------
# Short dtype labels
# ---------------------------------------------------------------------------

_POLARS_DTYPE_SHORT: dict[str, str] = {
    "Int8": "i8",
    "Int16": "i16",
    "Int32": "i32",
    "Int64": "i64",
    "UInt8": "u8",
    "UInt16": "u16",
    "UInt32": "u32",
    "UInt64": "u64",
    "Float32": "f32",
    "Float64": "f64",
    "Boolean": "bool",
    "String": "str",
    "Utf8": "str",
    "Date": "date",
    "Datetime": "dtime",
    "Time": "time",
    "Duration": "dur",
    "Categorical": "cat",
    "Enum": "enum",
    "Binary": "bin",
    "Null": "null",
    "Object": "obj",
    "Decimal": "dec",
}

_PANDAS_DTYPE_SHORT: dict[str, str] = {
    "int8": "i8",
    "int16": "i16",
    "int32": "i32",
    "int64": "i64",
    "uint8": "u8",
    "uint16": "u16",
    "uint32": "u32",
    "uint64": "u64",
    "float16": "f16",
    "float32": "f32",
    "float64": "f64",
    "bool": "bool",
    "object": "str",
    "string": "str",
    "category": "cat",
    "datetime64[ns]": "dtime",
    "timedelta64[ns]": "dur",
}

_ARROW_DTYPE_SHORT: dict[str, str] = {
    "int8": "i8",
    "int16": "i16",
    "int32": "i32",
    "int64": "i64",
    "uint8": "u8",
    "uint16": "u16",
    "uint32": "u32",
    "uint64": "u64",
    "float": "f32",
    "halffloat": "f16",
    "float16": "f16",
    "float32": "f32",
    "double": "f64",
    "float64": "f64",
    "bool": "bool",
    "string": "str",
    "utf8": "str",
    "large_string": "str",
    "large_utf8": "str",
    "binary": "bin",
    "date32": "date",
    "date32[day]": "date",
    "date64": "date",
    "timestamp[ns]": "dtime",
    "timestamp[us]": "dtime",
    "timestamp[ms]": "dtime",
    "timestamp[s]": "dtime",
    "time32[ms]": "time",
    "time64[us]": "time",
    "duration[ns]": "dur",
    "duration[us]": "dur",
    "null": "null",
    "dictionary": "cat",
    "decimal128": "dec",
}


def _arrow_dtype_short(dtype_str: str) -> str:
    """Convert a PyArrow dtype string to a short label."""
    # Try exact match first, then strip parameterized parts
    if dtype_str in _ARROW_DTYPE_SHORT:
        return _ARROW_DTYPE_SHORT[dtype_str]
    base = dtype_str.split("[")[0].split("(")[0].strip()
    return _ARROW_DTYPE_SHORT.get(base, base[:4])


# Character width approximation for IBM Plex Mono at 12px
_CHAR_PX = 7.2
_LABEL_CHAR_PX = 7.8
_COL_PADDING_PX = 16
_MIN_COL_WIDTH = 50

# ---------------------------------------------------------------------------
# Data normalization
# ---------------------------------------------------------------------------


def _is_polars(data: Any) -> bool:
    t = type(data).__module__
    return t.startswith("polars")


def _is_pandas(data: Any) -> bool:
    t = type(data).__module__
    return t.startswith("pandas")


def _is_arrow(data: Any) -> bool:
    t = type(data).__module__
    return t.startswith("pyarrow")


def _normalize_data(
    data: Any,
) -> tuple[list[str], list[str], list[list[Any]], int, str]:
    """Normalize input data to a common internal representation.

    Returns
    -------
    tuple
        (col_names, col_dtypes_short, all_rows, total_row_count, tbl_type) where `all_rows` is a
        list of rows, each row a list of cell values.
    """
    if isinstance(data, (str, Path)):
        return _from_file(data)
    if isinstance(data, dict):
        return _from_dict(data)
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return _from_list_of_dicts(data)
    if _is_polars(data):
        return _from_polars(data)
    if _is_pandas(data):
        return _from_pandas(data)
    if _is_arrow(data):
        return _from_arrow(data)
    raise TypeError(
        f"Unsupported data type: {type(data).__name__}. "
        "Pass a Polars/Pandas DataFrame, PyArrow Table, file path, dict, "
        "or list of dicts."
    )


def _from_polars(
    df: Any,
) -> tuple[list[str], list[str], list[list[Any]], int, str]:
    col_names = df.columns
    col_dtypes = [_polars_dtype_short(str(df[c].dtype)) for c in col_names]
    n_rows = df.height if hasattr(df, "height") else len(df)
    rows = df.rows()  # list of tuples
    return col_names, col_dtypes, [list(r) for r in rows], n_rows, "polars"


def _from_pandas(
    df: Any,
) -> tuple[list[str], list[str], list[list[Any]], int, str]:
    col_names = list(df.columns)
    col_dtypes = [_pandas_dtype_short(str(df[c].dtype)) for c in col_names]
    n_rows = len(df)
    rows = df.values.tolist()
    return col_names, col_dtypes, rows, n_rows, "pandas"


_FILE_EXT_MAP: dict[str, str] = {
    ".csv": "csv",
    ".tsv": "tsv",
    ".tab": "tsv",
    ".jsonl": "jsonl",
    ".ndjson": "jsonl",
    ".parquet": "parquet",
    ".pq": "parquet",
    ".feather": "feather",
    ".arrow": "arrow",
    ".ipc": "arrow",
}


def _from_file(
    path: str | Path,
) -> tuple[list[str], list[str], list[list[Any]], int, str]:
    """Dispatch to the correct reader based on file extension."""
    p = Path(path)
    ext = p.suffix.lower()
    fmt = _FILE_EXT_MAP.get(ext, "csv")  # default to CSV for unknown extensions
    if fmt == "csv":
        return _from_csv(p)
    if fmt == "tsv":
        return _from_tsv(p)
    if fmt == "jsonl":
        return _from_jsonl(p)
    if fmt == "parquet":
        return _from_parquet(p)
    if fmt in ("feather", "arrow"):
        return _from_feather(p, fmt)
    return _from_csv(p)  # pragma: no cover


def _from_csv(
    path: str | Path,
) -> tuple[list[str], list[str], list[list[Any]], int, str]:
    path = str(path)
    try:
        import polars as pl

        df = pl.read_csv(path)
        names, dtypes, rows, n, _ = _from_polars(df)
        return names, dtypes, rows, n, "csv"
    except ImportError:
        pass
    try:
        import pandas as pd

        df = pd.read_csv(path)
        names, dtypes, rows, n, _ = _from_pandas(df)
        return names, dtypes, rows, n, "csv"
    except ImportError:
        pass
    raise ImportError(
        "Reading CSV files requires either Polars or Pandas. "
        "Install one with: pip install polars  (or)  pip install pandas"
    )


def _from_tsv(
    path: str | Path,
) -> tuple[list[str], list[str], list[list[Any]], int, str]:
    path = str(path)
    try:
        import polars as pl

        df = pl.read_csv(path, separator="\t")
        names, dtypes, rows, n, _ = _from_polars(df)
        return names, dtypes, rows, n, "tsv"
    except ImportError:
        pass
    try:
        import pandas as pd

        df = pd.read_csv(path, sep="\t")
        names, dtypes, rows, n, _ = _from_pandas(df)
        return names, dtypes, rows, n, "tsv"
    except ImportError:
        pass
    raise ImportError(
        "Reading TSV files requires either Polars or Pandas. "
        "Install one with: pip install polars  (or)  pip install pandas"
    )


def _from_jsonl(
    path: str | Path,
) -> tuple[list[str], list[str], list[list[Any]], int, str]:
    path = str(path)
    try:
        import polars as pl

        df = pl.read_ndjson(path)
        names, dtypes, rows, n, _ = _from_polars(df)
        return names, dtypes, rows, n, "jsonl"
    except ImportError:
        pass
    try:
        import pandas as pd

        df = pd.read_json(path, lines=True)
        names, dtypes, rows, n, _ = _from_pandas(df)
        return names, dtypes, rows, n, "jsonl"
    except ImportError:
        pass
    raise ImportError(
        "Reading JSONL files requires either Polars or Pandas. "
        "Install one with: pip install polars  (or)  pip install pandas"
    )


def _from_parquet(
    path: str | Path,
) -> tuple[list[str], list[str], list[list[Any]], int, str]:
    path = str(path)
    try:
        import polars as pl

        df = pl.read_parquet(path)
        names, dtypes, rows, n, _ = _from_polars(df)
        return names, dtypes, rows, n, "parquet"
    except ImportError:
        pass
    try:
        import pandas as pd

        df = pd.read_parquet(path)
        names, dtypes, rows, n, _ = _from_pandas(df)
        return names, dtypes, rows, n, "parquet"
    except ImportError:
        pass
    raise ImportError(
        "Reading Parquet files requires Polars, Pandas+pyarrow, or "
        "Pandas+fastparquet. Install one with: pip install polars  (or)  "
        "pip install pandas pyarrow"
    )


def _from_feather(
    path: str | Path,
    fmt: str = "feather",
) -> tuple[list[str], list[str], list[list[Any]], int, str]:
    path = str(path)
    try:
        import polars as pl

        df = pl.read_ipc(path)
        names, dtypes, rows, n, _ = _from_polars(df)
        return names, dtypes, rows, n, fmt
    except ImportError:
        pass
    try:
        import pandas as pd

        df = pd.read_feather(path)
        names, dtypes, rows, n, _ = _from_pandas(df)
        return names, dtypes, rows, n, fmt
    except ImportError:
        pass
    raise ImportError(
        "Reading Feather/Arrow IPC files requires Polars or Pandas+pyarrow. "
        "Install one with: pip install polars  (or)  pip install pandas pyarrow"
    )


def _from_arrow(
    tbl: Any,
) -> tuple[list[str], list[str], list[list[Any]], int, str]:
    """Convert a PyArrow Table to the internal representation."""
    col_names = tbl.column_names
    col_dtypes = [_arrow_dtype_short(str(tbl.field(c).type)) for c in col_names]
    n_rows = tbl.num_rows
    rows = [list(row.values()) for row in tbl.to_pylist()]
    return col_names, col_dtypes, rows, n_rows, "arrow"


def _from_dict(
    d: dict[str, list],
) -> tuple[list[str], list[str], list[list[Any]], int, str]:
    col_names = list(d.keys())
    if not col_names:
        return [], [], [], 0, "dict"
    n_rows = len(d[col_names[0]])
    col_dtypes = [_infer_dtype(d[c]) for c in col_names]
    rows = [[d[c][i] if i < len(d[c]) else None for c in col_names] for i in range(n_rows)]
    return col_names, col_dtypes, rows, n_rows, "dict"


def _from_list_of_dicts(
    lst: list[dict],
) -> tuple[list[str], list[str], list[list[Any]], int, str]:
    col_names = list(dict.fromkeys(k for row in lst for k in row))
    n_rows = len(lst)
    rows = [[row.get(c) for c in col_names] for row in lst]
    col_dtypes = [_infer_dtype([row[i] for row in rows]) for i, _ in enumerate(col_names)]
    return col_names, col_dtypes, rows, n_rows, "dict"


def _polars_dtype_short(dtype_str: str) -> str:
    """Convert a Polars dtype string to a short label."""
    # Strip parameterized parts: Datetime(time_unit='us', ...) → Datetime
    base = dtype_str.split("(")[0].strip()
    return _POLARS_DTYPE_SHORT.get(base, base.lower()[:4])


def _pandas_dtype_short(dtype_str: str) -> str:
    """Convert a Pandas dtype string to a short label."""
    return _PANDAS_DTYPE_SHORT.get(dtype_str, dtype_str[:4])


def _infer_dtype(values: list) -> str:
    """Infer a short dtype label from a list of Python values."""
    types = {type(v) for v in values if v is not None}
    if not types:
        return "null"
    if types == {int}:
        return "i64"
    if types <= {int, float}:
        return "f64"
    if types == {float}:  # pragma: no cover
        return "f64"  # pragma: no cover
    if types == {bool}:
        return "bool"
    return "str"


# ---------------------------------------------------------------------------
# Column subsetting
# ---------------------------------------------------------------------------


def _apply_column_subset(
    col_names: list[str],
    col_dtypes: list[str],
    rows: list[list],
    columns: list[str] | None,
) -> tuple[list[str], list[str], list[list]]:
    if columns is None:
        return col_names, col_dtypes, rows
    indices = []
    for c in columns:
        if c not in col_names:
            raise ValueError(f"Column {c!r} not found. Available: {col_names}")
        indices.append(col_names.index(c))
    new_names = [col_names[i] for i in indices]
    new_dtypes = [col_dtypes[i] for i in indices]
    new_rows = [[row[i] for i in indices] for row in rows]
    return new_names, new_dtypes, new_rows


# ---------------------------------------------------------------------------
# Head/tail split
# ---------------------------------------------------------------------------


def _compute_head_tail(
    rows: list[list],
    total_rows: int,
    n_head: int,
    n_tail: int,
    show_all: bool,
    row_index_offset: int = 0,
) -> tuple[list[list], list[int], bool]:
    """Select head and tail rows, compute row numbers.

    Parameters
    ----------
    row_index_offset
        Starting number for row indices (default 0).

    Returns
    -------
    tuple
        (display_rows, row_numbers, is_full_dataset)
    """
    if show_all or n_head + n_tail >= total_rows:
        row_numbers = list(range(row_index_offset, row_index_offset + total_rows))
        return rows, row_numbers, True

    head_rows = rows[:n_head]
    tail_rows = rows[-n_tail:] if n_tail > 0 else []
    display_rows = head_rows + tail_rows

    head_nums = list(range(row_index_offset, row_index_offset + n_head))
    tail_start = row_index_offset + total_rows - n_tail
    tail_nums = list(range(tail_start, row_index_offset + total_rows)) if n_tail > 0 else []
    row_numbers = head_nums + tail_nums

    return display_rows, row_numbers, False


# ---------------------------------------------------------------------------
# Missing value detection
# ---------------------------------------------------------------------------

_MISSING_REPRS = {"None", "nan", "NaN", "NA", "NaT", "<NA>", ""}


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        import math

        if isinstance(value, float) and math.isnan(value):
            return True
    except (TypeError, ValueError):  # pragma: no cover
        pass  # pragma: no cover
    return False


# ---------------------------------------------------------------------------
# Alignment detection
# ---------------------------------------------------------------------------


def _detect_alignments(col_dtypes: list[str]) -> list[str]:
    """Return 'right' for numeric columns, 'left' for everything else."""
    numeric = {"i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64", "f16", "f32", "f64", "dec"}
    return ["right" if d in numeric else "left" for d in col_dtypes]


# ---------------------------------------------------------------------------
# Column width calculation
# ---------------------------------------------------------------------------


def _compute_col_widths(
    col_names: list[str],
    col_dtypes: list[str],
    rows: list[list],
    max_col_width: int,
    min_tbl_width: int,
    show_row_numbers: bool,
    row_numbers: list[int],
) -> tuple[list[int], int]:
    """Compute pixel widths for each column.

    Returns
    -------
    tuple
        (col_widths, rownum_width) where rownum_width is 0 if hidden.
    """
    widths: list[int] = []
    for i, name in enumerate(col_names):
        # Width from column name
        name_w = _LABEL_CHAR_PX * len(name) + _COL_PADDING_PX
        # Width from dtype label
        dtype_w = _LABEL_CHAR_PX * len(col_dtypes[i]) + _COL_PADDING_PX
        # Width from content (sample all displayed rows)
        max_content_len = 0
        for row in rows:
            val = row[i]
            cell_str = _format_cell(val)
            max_content_len = max(max_content_len, len(cell_str))
        content_w = _CHAR_PX * max_content_len + _COL_PADDING_PX

        w = int(round(min(max(name_w, dtype_w, content_w, _MIN_COL_WIDTH), max_col_width)))
        widths.append(w)

    # Row number column width
    rownum_width = 0
    if show_row_numbers and row_numbers:
        max_num = max(row_numbers)
        rownum_width = int(round(len(str(max_num)) * _CHAR_PX + 10))
        rownum_width = max(rownum_width, 35)

    # Scale up to min_tbl_width
    total = sum(widths) + rownum_width
    if total < min_tbl_width and widths:
        remaining = min_tbl_width - total
        per_col = remaining // len(widths)
        widths = [w + per_col for w in widths]

    return widths, rownum_width


# ---------------------------------------------------------------------------
# Cell formatting
# ---------------------------------------------------------------------------


def _format_cell(value: Any) -> str:
    """Format a cell value as a display string."""
    if value is None:
        return "None"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        import math

        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Inf" if value > 0 else "-Inf"
        # Use 12 significant digits — enough precision for real data
        # while trimming IEEE 754 noise (e.g. 3.3000000000000003 → 3.3)
        return f"{value:.12g}"
    return str(value)


def _escape(text: str) -> str:
    """HTML-escape a string."""
    return _html_mod.escape(text, quote=True)


# ---------------------------------------------------------------------------
# Number formatting
# ---------------------------------------------------------------------------


def _format_number(n: int) -> str:
    """Format an integer with comma separators."""
    return f"{n:,}"


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------


def _render_scoped_css(uid: str) -> str:
    """Generate the scoped CSS block for a table instance."""
    s = f"#gd-tbl-{uid}"
    return f"""<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:ital,wght@0,400;0,600;1,400&family=IBM+Plex+Sans:wght@400;600&display=swap');
{s} .gt_table {{
  display: table;
  border-collapse: collapse;
  table-layout: fixed;
  line-height: normal;
  margin-left: auto;
  margin-right: auto;
  color: #333333;
  font-size: 14px;
  font-weight: normal;
  font-style: normal;
  background-color: #FFFFFF;
  width: auto;
  border-top-style: solid;
  border-top-width: 2px;
  border-top-color: #A8A8A8;
  border-bottom-style: solid;
  border-bottom-width: 2px;
  border-bottom-color: #A8A8A8;
}}
{s} .gt_heading {{
  background-color: #FFFFFF;
  text-align: left;
  border-bottom-color: #FFFFFF;
  border-left-style: none;
  border-right-style: none;
}}
{s} .gt_title {{
  color: #333333;
  font-size: 125%;
  font-weight: initial;
  padding-top: 4px;
  padding-bottom: 4px;
  padding-left: 5px;
  padding-right: 5px;
  border-bottom-color: #FFFFFF;
  border-bottom-width: 0;
}}
{s} .gt_subtitle {{
  color: #333333;
  font-size: 85%;
  font-weight: initial;
  padding-top: 3px;
  padding-bottom: 5px;
  padding-left: 5px;
  padding-right: 5px;
  border-top-color: #FFFFFF;
  border-top-width: 0;
}}
{s} .gt_bottom_border {{
  border-bottom-style: solid;
  border-bottom-width: 2px;
  border-bottom-color: #D3D3D3;
}}
{s} .gt_col_headings {{
  border-top-style: solid;
  border-top-width: 2px;
  border-top-color: #D3D3D3;
  border-bottom-style: solid;
  border-bottom-width: 2px;
  border-bottom-color: #D3D3D3;
  border-left-style: none;
  border-right-style: none;
}}
{s} .gt_col_heading {{
  color: #333333;
  background-color: #FFFFFF;
  font-size: 100%;
  font-weight: normal;
  text-transform: inherit;
  border-left-style: solid;
  border-left-width: 1px;
  border-left-color: #F2F2F2;
  border-right-style: solid;
  border-right-width: 1px;
  border-right-color: #F2F2F2;
  vertical-align: bottom;
  padding-top: 5px;
  padding-bottom: 5px;
  padding-left: 5px;
  padding-right: 5px;
  overflow-x: hidden;
}}
{s} .gt_table_body {{
  border-top-style: solid;
  border-top-width: 2px;
  border-top-color: #D3D3D3;
}}
{s} .gt_row {{
  padding-top: 4px;
  padding-bottom: 4px;
  padding-left: 5px;
  padding-right: 5px;
  margin: 10px;
  border-top-style: solid;
  border-top-width: 1px;
  border-top-color: #E9E9E9;
  border-left-style: solid;
  border-left-width: 1px;
  border-left-color: #E9E9E9;
  border-right-style: solid;
  border-right-width: 1px;
  border-right-color: #E9E9E9;
  vertical-align: middle;
  overflow-x: hidden;
}}
{s} .gt_left {{ text-align: left; }}
{s} .gt_center {{ text-align: center; }}
{s} .gt_right {{ text-align: right; font-variant-numeric: tabular-nums; }}
{s} .gt_font_normal {{ font-weight: normal; }}
{s} .gt_font_bold {{ font-weight: bold; }}
{s} .gt_font_italic {{ font-style: italic; }}
{s} .gt_striped {{ background-color: rgba(128,128,128,0.05); }}
{s} .gt_from_md > :first-child {{ margin-top: 0; }}
{s} .gt_from_md > :last-child {{ margin-bottom: 0; }}
/* Data cell font */
{s} .gt_table_body .gt_row {{
  font-family: 'IBM Plex Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
  color: #333333;
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
  height: 14px;
}}
/* Column label font */
{s} .gt_col_heading {{
  font-family: 'IBM Plex Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
  color: #333333;
}}
/* Row number styling */
{s} .gd-tbl-rownum {{
  color: gray;
  font-family: 'IBM Plex Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 10px;
  border-right: 2px solid rgba(102, 153, 204, 0.5) !important;
  text-align: right;
  padding-right: 6px;
  white-space: nowrap;
}}
/* Head/tail divider */
{s} tr.gd-tbl-divider td,
{s} tr.gd-tbl-divider th {{
  border-bottom: 2px solid rgba(102, 153, 204, 0.5);
}}
/* Missing values */
{s} .gd-tbl-missing {{
  color: #B22222 !important;
  background-color: rgba(255, 193, 193, 0.35);
}}
/* Column label sub-elements */
{s} .gd-tbl-colname {{
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
  padding-bottom: 0;
  margin-bottom: 0;
}}
{s} .gd-tbl-dtype {{
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
  padding-top: 0;
  margin-top: 0;
  color: #666666;
}}
/* Header badge styling */
{s} .gd-tbl-badge {{
  display: inline-block;
  padding: 2px 10px;
  font-family: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: 10px;
  font-weight: bold;
  text-transform: uppercase;
  position: inherit;
}}
{s} .gd-tbl-badge-rows-label {{
  background-color: #eecbff;
  color: #333333;
  border: 1px solid #eecbff;
  margin-left: 5px;
}}
{s} .gd-tbl-badge-rows-value {{
  background-color: transparent;
  color: #333333;
  border: 1px solid #eecbff;
  margin-left: -4px;
  margin-right: 3px;
}}
{s} .gd-tbl-badge-cols-label {{
  background-color: #BDE7B4;
  color: #333333;
  border: 1px solid #BDE7B4;
}}
{s} .gd-tbl-badge-cols-value {{
  background-color: transparent;
  color: #333333;
  border: 1px solid #BDE7B4;
  margin-left: -4px;
}}
/* Dark mode */
body.quarto-dark {s} .gt_table,
html.quarto-dark {s} .gt_table,
:root[data-bs-theme="dark"] {s} .gt_table {{
  background-color: #1a1a2e;
  color: #e0e0e0;
  border-top-color: #555;
  border-bottom-color: #555;
}}
body.quarto-dark {s} .gt_heading,
html.quarto-dark {s} .gt_heading,
:root[data-bs-theme="dark"] {s} .gt_heading {{
  background-color: #1a1a2e;
  border-bottom-color: #1a1a2e;
}}
body.quarto-dark {s} .gt_title,
html.quarto-dark {s} .gt_title,
:root[data-bs-theme="dark"] {s} .gt_title {{
  color: #e0e0e0;
}}
body.quarto-dark {s} .gt_subtitle,
html.quarto-dark {s} .gt_subtitle,
:root[data-bs-theme="dark"] {s} .gt_subtitle {{
  color: #b0b0b0;
}}
body.quarto-dark {s} .gt_col_headings,
html.quarto-dark {s} .gt_col_headings,
:root[data-bs-theme="dark"] {s} .gt_col_headings {{
  border-top-color: #444;
  border-bottom-color: #444;
}}
body.quarto-dark {s} .gt_col_heading,
html.quarto-dark {s} .gt_col_heading,
:root[data-bs-theme="dark"] {s} .gt_col_heading {{
  color: #b0b0b0;
  background-color: #1a1a2e;
  border-left-color: #333;
  border-right-color: #333;
}}
body.quarto-dark {s} .gt_table_body,
html.quarto-dark {s} .gt_table_body,
:root[data-bs-theme="dark"] {s} .gt_table_body {{
  border-top-color: #444;
}}
body.quarto-dark {s} .gt_table_body .gt_row,
html.quarto-dark {s} .gt_table_body .gt_row,
:root[data-bs-theme="dark"] {s} .gt_table_body .gt_row {{
  color: #d0d0d0;
  border-top-color: #4b4b4b;
  border-bottom-color: #4b4b4b;
  border-left-color: #333;
  border-right-color: #333;
}}
body.quarto-dark {s} .gd-tbl-rownum,
html.quarto-dark {s} .gd-tbl-rownum,
:root[data-bs-theme="dark"] {s} .gd-tbl-rownum {{
  color: #888;
  border-right-color: rgba(102, 153, 204, 0.4) !important;
}}
body.quarto-dark {s} .gd-tbl-missing,
html.quarto-dark {s} .gd-tbl-missing,
:root[data-bs-theme="dark"] {s} .gd-tbl-missing {{
  color: #ff6b6b !important;
  background-color: rgba(60, 17, 24, 0.2);
}}
body.quarto-dark {s} .gd-tbl-dtype,
html.quarto-dark {s} .gd-tbl-dtype,
:root[data-bs-theme="dark"] {s} .gd-tbl-dtype {{
  color: #888;
}}
body.quarto-dark {s} .gt_bottom_border,
html.quarto-dark {s} .gt_bottom_border,
:root[data-bs-theme="dark"] {s} .gt_bottom_border {{
  border-bottom-color: #555;
}}
body.quarto-dark {s} .gd-tbl-badge-rows-label,
html.quarto-dark {s} .gd-tbl-badge-rows-label,
:root[data-bs-theme="dark"] {s} .gd-tbl-badge-rows-label {{
  background-color: #3d2a4d;
  border-color: #3d2a4d;
  color: #e0c0ff;
}}
body.quarto-dark {s} .gd-tbl-badge-rows-value,
html.quarto-dark {s} .gd-tbl-badge-rows-value,
:root[data-bs-theme="dark"] {s} .gd-tbl-badge-rows-value {{
  border-color: #3d2a4d;
  color: #d0b0e0;
}}
body.quarto-dark {s} .gd-tbl-badge-cols-label,
html.quarto-dark {s} .gd-tbl-badge-cols-label,
:root[data-bs-theme="dark"] {s} .gd-tbl-badge-cols-label {{
  background-color: #2a4d2a;
  border-color: #2a4d2a;
  color: #b0e0b0;
}}
body.quarto-dark {s} .gd-tbl-badge-cols-value,
html.quarto-dark {s} .gd-tbl-badge-cols-value,
:root[data-bs-theme="dark"] {s} .gd-tbl-badge-cols-value {{
  border-color: #2a4d2a;
  color: #a0d0a0;
}}
</style>"""


def _render_header_html(
    uid: str,
    tbl_type: str,
    n_rows: int,
    n_cols: int,
    caption: str | None,
    show_dimensions: bool,
    total_cols: int,
) -> str:
    """Render the <thead> header rows (banner + optional caption + column labels)."""
    parts: list[str] = []

    if show_dimensions:
        style_info = _TABLE_TYPE_STYLES.get(tbl_type, _TABLE_TYPE_STYLES["dict"])
        type_badge = (
            f'<span class="gd-tbl-badge" style="background-color: {style_info["bg"]}; '
            f"color: {style_info['fg']}; border: 1px solid {style_info['bg']}; "
            f'margin-right: 8px;">{_escape(style_info["label"])}</span>'
        )
        rows_badge = (
            f'<span class="gd-tbl-badge gd-tbl-badge-rows-label">Rows</span>'
            f'<span class="gd-tbl-badge gd-tbl-badge-rows-value">{_format_number(n_rows)}</span>'
        )
        cols_badge = (
            f'<span class="gd-tbl-badge gd-tbl-badge-cols-label">Columns</span>'
            f'<span class="gd-tbl-badge gd-tbl-badge-cols-value">{_format_number(n_cols)}</span>'
        )
        parts.append(
            f'<tr class="gt_heading">'
            f'<td class="gt_heading gt_title gt_font_normal" colspan="{total_cols}">'
            f'<div style="padding-top: 0; padding-bottom: 7px;">'
            f"{type_badge}{rows_badge}{cols_badge}"
            f"</div></td></tr>"
        )

    if caption:
        border_class = " gt_bottom_border" if not show_dimensions else ""
        parts.append(
            f'<tr class="gt_heading">'
            f'<td class="gt_heading gt_subtitle gt_font_normal{border_class}" '
            f'colspan="{total_cols}">{_escape(caption)}</td></tr>'
        )

    return "\n".join(parts)


def _render_colgroup_html(
    col_widths: list[int],
    rownum_width: int,
    show_row_numbers: bool,
) -> str:
    """Render the <colgroup> element."""
    parts = ["<colgroup>"]
    if show_row_numbers:
        parts.append(f'<col style="width: {rownum_width}px"/>')
    for w in col_widths:
        parts.append(f'<col style="width: {w}px"/>')
    parts.append("</colgroup>")
    return "\n".join(parts)


def _render_column_labels_html(
    col_names: list[str],
    col_dtypes: list[str],
    alignments: list[str],
    show_dtypes: bool,
    show_row_numbers: bool,
) -> str:
    """Render the column label <tr>."""
    parts = ['<tr class="gt_col_headings">']

    if show_row_numbers:
        parts.append(
            '<th class="gt_col_heading gt_columns_bottom_border gt_right" '
            'rowspan="1" colspan="1" scope="col"></th>'
        )

    for i, name in enumerate(col_names):
        align_cls = f"gt_{alignments[i]}"
        if show_dtypes:
            label_html = (
                f"<div>"
                f'<div class="gd-tbl-colname">{_escape(name)}</div>'
                f'<div class="gd-tbl-dtype"><em>{_escape(col_dtypes[i])}</em></div>'
                f"</div>"
            )
        else:
            label_html = _escape(name)

        parts.append(
            f'<th class="gt_col_heading gt_columns_bottom_border {align_cls}" '
            f'rowspan="1" colspan="1" scope="col" id="{_escape(name)}">'
            f"{label_html}</th>"
        )

    parts.append("</tr>")
    return "\n".join(parts)


def _render_body_html(
    rows: list[list],
    row_numbers: list[int],
    col_names: list[str],
    alignments: list[str],
    col_widths: list[int],
    n_head: int,
    is_full_dataset: bool,
    show_row_numbers: bool,
    highlight_missing: bool,
) -> str:
    """Render the <tbody> rows."""
    parts = ['<tbody class="gt_table_body">']

    for row_idx, (row, row_num) in enumerate(zip(rows, row_numbers)):
        # Add divider class to the last head row
        divider = ""
        if not is_full_dataset and row_idx == n_head - 1:
            divider = ' class="gd-tbl-divider"'

        parts.append(f"<tr{divider}>")

        if show_row_numbers:
            parts.append(f'<td class="gt_row gt_right gd-tbl-rownum">{row_num}</td>')

        for col_idx, val in enumerate(row):
            align_cls = f"gt_{alignments[col_idx]}"
            cell_str = _format_cell(val)
            cell_html = _escape(cell_str)

            missing_cls = ""
            if highlight_missing and _is_missing(val):
                missing_cls = " gd-tbl-missing"

            w = col_widths[col_idx]
            parts.append(
                f'<td class="gt_row {align_cls}{missing_cls}" '
                f'style="max-width: {w}px;">{cell_html}</td>'
            )

        parts.append("</tr>")

    parts.append("</tbody>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def tbl_preview(
    data: Any,
    columns: list[str] | None = None,
    n_head: int = 5,
    n_tail: int = 5,
    limit: int = 50,
    show_all: bool = False,
    show_row_numbers: bool = True,
    show_dtypes: bool = True,
    show_dimensions: bool = True,
    max_col_width: int = 250,
    min_tbl_width: int = 500,
    caption: str | None = None,
    highlight_missing: bool = True,
    row_index_offset: int = 0,
    id: str | None = None,
) -> TblPreview:
    """
    Generate a self-contained HTML table preview from almost any tabular data source.

    The `tbl_preview()` function gives you a quick, polished look at a dataset without pulling in
    heavy rendering dependencies. Pass it a Polars DataFrame, a Pandas DataFrame, a PyArrow Table,
    a file path to a CSV / TSV / JSONL / Parquet / Feather file, a column-oriented dictionary, or a
    list of row dictionaries—and get back a styled HTML table that renders identically in notebooks,
    Quarto documents, and static HTML pages.

    The preview shows a configurable number of rows from the top and bottom of the table, separated
    by a blue divider line when the full dataset exceeds the requested row count. Each column header
    displays the column name and, beneath it, a compact dtype label (e.g., `i64`, `str`, `f64`). A
    header banner shows a colored badge identifying the data source type (Polars, Pandas, CSV,
    Parquet, etc.) alongside row and column counts. Missing values (`None`, `NaN`, `NA`) are
    highlighted in red so they stand out immediately.

    The output is a :class:`TblPreview` object with `_repr_html_()` support, so it displays
    automatically in Jupyter notebooks and Quarto code cells. All CSS is scoped to a unique id,
    and the table includes full dark-mode support. No JavaScript is required.

    Parameters
    ----------
    data
        The table to preview. This can be a Polars DataFrame, a Pandas DataFrame, a PyArrow Table, a
        file path (as a string or `pathlib.Path` object), a column-oriented dictionary, or a list of
        row dictionaries. When providing a file path, the extension determines the loader: `.csv`,
        `.tsv`, `.jsonl` (or `.ndjson`), `.parquet`, `.feather`, and `.arrow` (Arrow IPC) are all
        supported. Read the *Supported Input Data Types* section for details on each accepted
        format.
    columns
        The columns to display in the preview, by default `None` (all columns are shown). This
        can be a list of column name strings. If any name does not match a column in the table, a
        `KeyError` is raised. This is useful for focusing on a subset of a wide dataset.
    n_head
        The number of rows to show from the start of the table. Set to `5` by default. When the
        table has fewer rows than `n_head + n_tail`, the full table is displayed without a
        divider.
    n_tail
        The number of rows to show from the end of the table. Set to `5` by default.
    limit
        The limit value for the sum of `n_head=` and `n_tail=` (the total number of rows shown).
        If the sum of `n_head=` and `n_tail=` exceeds the limit, a `ValueError` is raised. The
        default value is `50`. Increase this when you need to display more rows.
    show_all
        Should the entire table be displayed? If `True`, all rows are shown regardless of the
        `n_head=` and `n_tail=` settings. By default, this is `False`.
    show_row_numbers
        Should row numbers be shown? The numbers appear in a narrow gutter column on the left side
        of the table, separated from the data columns by a subtle blue vertical line. By default,
        this is set to `True`.
    show_dtypes
        Should data type labels be displayed beneath each column name? The labels use short
        abbreviations (e.g., `i64` for 64-bit integer, `str` for string, `f64` for 64-bit float). By
        default, this is set to `True`.
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
        Useful for labeling a preview with a dataset name or description. By default, no caption is
        shown.
    highlight_missing
        Should missing values (`None`, `NaN`, `NA`) be highlighted? When `True` (the default),
        missing cells are displayed in red text on a light red background so they stand out at a
        glance.
    row_index_offset
        The starting number for row indices. Defaults to `0`, matching the zero-based indexing
        convention of Python, Polars, and Pandas. Set to `1` for one-based numbering (e.g., for
        presentation to audiences unfamiliar with zero-based indexing).
    id
        An HTML `id` attribute for the outer `<div>` container. If `None` (the default), a unique ID
        is auto-generated using `secrets.token_hex(4)`. Providing your own ID is useful when you
        need to target the table with custom CSS or JavaScript.

    Returns
    -------
    TblPreview
        A rendered table preview object. The object has `_repr_html_()` for automatic notebook
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
    The simplest way to preview a table is to pass a Python dictionary:

    ```{python}
    from great_docs import tbl_preview

    tbl_preview({"city": ["Tokyo", "Paris", "New York"], "population": [13960000, 2161000, 8336000]})
    ```

    The result is a styled HTML table with a header banner showing the row and column count, dtype
    labels beneath each column name, and row numbers on the left.

    You can also pass a Polars DataFrame:

    ```{python}
    import polars as pl

    df = pl.DataFrame({
        "product": ["Widget", "Gadget", "Gizmo", "Doohickey", "Thingamajig"],
        "category": ["Electronics", "Tools", "Kitchen", "Garden", "Office"],
        "price": [29.99, 49.50, 12.00, 8.75, 199.99],
        "in_stock": [True, False, True, True, False],
    })

    tbl_preview(df)
    ```

    For large tables, only the first `n_head=` and last `n_tail=` rows are shown, separated by a
    blue divider line. Adjust the counts to show more or fewer rows:

    ```{python}
    tbl_preview(df, n_head=2, n_tail=1)
    ```

    Use `columns=` to focus on specific columns in a wide dataset:

    ```{python}
    tbl_preview(df, columns=["product", "price"])
    ```

    File paths work directly—no need to load the data yourself:

    ```{python}
    #| echo: false
    #| output: false
    import pathlib, json
    _d = pathlib.Path("assets/tbl-preview-data")
    _d.mkdir(parents=True, exist_ok=True)
    (_d / "students.csv").write_text(
        "name,subject,score,grade,passed\\n"
        "Alice,Math,95.5,A,true\\n"
        "Bob,Science,82.0,B,true\\n"
        "Charlie,English,71.3,C,true\\n"
        "Diana,History,60.0,D,true\\n"
        "Eve,Art,55.8,F,false\\n"
        "Frank,Math,88.2,B+,true\\n"
        "Grace,Science,79.9,C+,true\\n"
        "Hank,English,91.0,A-,true\\n"
        "Iris,History,66.4,D+,true\\n"
        "Jack,Art,73.7,C,true\\n"
    )
    ```

    ```{python}
    tbl_preview("assets/tbl-preview-data/students.csv")
    ```

    Add a caption to label the preview:

    ```{python}
    tbl_preview(df, caption="Product Catalog for Q1 2026")
    ```

    For a minimal look, turn off the header banner, dtype labels, and row numbers:

    ```{python}
    tbl_preview(df, show_dimensions=False, show_dtypes=False, show_row_numbers=False)
    ```

    See Also
    --------
    tbl_explorer: Launch an interactive table explorer for deeper data investigation.
    """
    if not show_all and n_head + n_tail > limit:
        raise ValueError(
            f"n_head ({n_head}) + n_tail ({n_tail}) = {n_head + n_tail} "
            f"exceeds limit ({limit}). Increase limit= or set show_all=True."
        )

    # 1. Normalize input data
    col_names, col_dtypes, all_rows, total_rows, tbl_type = _normalize_data(data)
    original_n_cols = len(col_names)

    # 2. Apply column subset
    col_names, col_dtypes, all_rows = _apply_column_subset(col_names, col_dtypes, all_rows, columns)

    # 3. Compute head/tail split
    display_rows, row_numbers, is_full = _compute_head_tail(
        all_rows, total_rows, n_head, n_tail, show_all, row_index_offset
    )

    # 4. Detect alignments
    alignments = _detect_alignments(col_dtypes)

    # 5. Compute column widths
    col_widths, rownum_width = _compute_col_widths(
        col_names,
        col_dtypes,
        display_rows,
        max_col_width,
        min_tbl_width,
        show_row_numbers,
        row_numbers,
    )

    # 6. Generate unique ID
    uid = id or secrets.token_hex(4)

    # Total columns including row number column
    total_cols = len(col_names) + (1 if show_row_numbers else 0)

    # 7. Render HTML components
    css = _render_scoped_css(uid)

    header = _render_header_html(
        uid, tbl_type, total_rows, original_n_cols, caption, show_dimensions, total_cols
    )

    colgroup = _render_colgroup_html(col_widths, rownum_width, show_row_numbers)

    column_labels = _render_column_labels_html(
        col_names, col_dtypes, alignments, show_dtypes, show_row_numbers
    )

    body = _render_body_html(
        display_rows,
        row_numbers,
        col_names,
        alignments,
        col_widths,
        n_head,
        is_full,
        show_row_numbers,
        highlight_missing,
    )

    # 8. Assemble final HTML
    html = (
        f'<div id="gd-tbl-{uid}" class="gd-tbl-preview" '
        f'style="padding-left: 0px; overflow-x: auto; overflow-y: hidden; '
        f'width: 100%; max-width: 100%; margin-bottom: 1em;">\n'
        f"{css}\n"
        f'<table class="gt_table" data-quarto-disable-processing="true" '
        f'data-quarto-bootstrap="false">\n'
        f"{colgroup}\n"
        f"<thead>\n{header}\n{column_labels}\n</thead>\n"
        f"{body}\n"
        f"</table>\n"
        f"</div>"
    )

    return TblPreview(html)
