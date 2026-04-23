"""Tests for the tbl_preview module."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_dict(n_rows: int = 10, n_cols: int = 3) -> dict[str, list]:
    """Create a simple column-oriented dict for testing."""
    data: dict[str, list] = {}
    for c in range(n_cols):
        col_name = f"col_{c}"
        data[col_name] = list(range(n_rows))
    return data


def _make_mixed_dict() -> dict[str, list]:
    """Dict with mixed types including None and NaN."""
    return {
        "name": ["Alice", "Bob", None, "Dave", "Eve"],
        "score": [95.5, float("nan"), 88.0, None, 72.3],
        "active": [True, False, True, None, False],
    }


def _make_list_of_dicts(n: int = 5) -> list[dict]:
    return [{"x": i, "y": f"val_{i}", "z": i * 1.1} for i in range(n)]


# ---------------------------------------------------------------------------
# TblPreview result class
# ---------------------------------------------------------------------------


class TestTblPreviewResult:
    """Tests for the TblPreview wrapper class."""

    def test_repr_html(self):
        from great_docs._tbl_preview import TblPreview

        tp = TblPreview("<div>hello</div>")
        assert tp._repr_html_() == "<div>hello</div>"

    def test_as_html(self):
        from great_docs._tbl_preview import TblPreview

        tp = TblPreview("<p>test</p>")
        assert tp.as_html() == "<p>test</p>"

    def test_save(self, tmp_path: Path):
        from great_docs._tbl_preview import TblPreview

        tp = TblPreview("<table>data</table>")
        out = tmp_path / "out.html"
        tp.save(out)
        assert out.read_text(encoding="utf-8") == "<table>data</table>"

    def test_repr(self):
        from great_docs._tbl_preview import TblPreview

        tp = TblPreview("abcdef")
        assert "6 chars" in repr(tp)


# ---------------------------------------------------------------------------
# Data normalization
# ---------------------------------------------------------------------------


class TestNormalizeData:
    """Tests for data normalization from different sources."""

    def test_dict_input(self):
        from great_docs._tbl_preview import _normalize_data

        data = {"a": [1, 2, 3], "b": ["x", "y", "z"]}
        names, dtypes, rows, n, tbl_type = _normalize_data(data)
        assert names == ["a", "b"]
        assert n == 3
        assert tbl_type == "dict"
        assert len(rows) == 3
        assert rows[0] == [1, "x"]

    def test_list_of_dicts_input(self):
        from great_docs._tbl_preview import _normalize_data

        data = [{"x": 1, "y": "a"}, {"x": 2, "y": "b"}]
        names, dtypes, rows, n, tbl_type = _normalize_data(data)
        assert names == ["x", "y"]
        assert n == 2
        assert tbl_type == "dict"

    def test_empty_dict(self):
        from great_docs._tbl_preview import _normalize_data

        names, dtypes, rows, n, tbl_type = _normalize_data({})
        assert names == []
        assert n == 0

    def test_unsupported_type_raises(self):
        from great_docs._tbl_preview import _normalize_data

        with pytest.raises(TypeError, match="Unsupported data type"):
            _normalize_data(42)

    def test_csv_file(self, tmp_path: Path):
        from great_docs._tbl_preview import _normalize_data

        csv = tmp_path / "test.csv"
        csv.write_text("a,b,c\n1,x,3.0\n2,y,4.0\n")
        names, dtypes, rows, n, tbl_type = _normalize_data(str(csv))
        assert "a" in names
        assert n == 2
        assert tbl_type == "csv"

    def test_csv_path_object(self, tmp_path: Path):
        from great_docs._tbl_preview import _normalize_data

        csv = tmp_path / "test.csv"
        csv.write_text("col1,col2\n10,20\n30,40\n")
        names, _, rows, n, tbl_type = _normalize_data(csv)  # Path object
        assert n == 2
        assert tbl_type == "csv"


class TestPolarsIntegration:
    """Tests with Polars DataFrames (skipped if not installed)."""

    @pytest.fixture(autouse=True)
    def _require_polars(self):
        pytest.importorskip("polars")

    def test_polars_dataframe(self):
        import polars as pl
        from great_docs._tbl_preview import _normalize_data

        df = pl.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        names, dtypes, rows, n, tbl_type = _normalize_data(df)
        assert names == ["a", "b"]
        assert n == 3
        assert tbl_type == "polars"
        assert dtypes[0] in ("i64", "i32")
        assert dtypes[1] == "str"


class TestPandasIntegration:
    """Tests with Pandas DataFrames (skipped if not installed)."""

    @pytest.fixture(autouse=True)
    def _require_pandas(self):
        pytest.importorskip("pandas")

    def test_pandas_dataframe(self):
        import pandas as pd
        from great_docs._tbl_preview import _normalize_data

        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        names, dtypes, rows, n, tbl_type = _normalize_data(df)
        assert names == ["a", "b"]
        assert n == 3
        assert tbl_type == "pandas"


# ---------------------------------------------------------------------------
# Column subsetting
# ---------------------------------------------------------------------------


class TestColumnSubset:
    def test_none_returns_all(self):
        from great_docs._tbl_preview import _apply_column_subset

        names = ["a", "b", "c"]
        dtypes = ["i64", "str", "f64"]
        rows = [[1, "x", 1.0]]
        out_names, out_dtypes, out_rows = _apply_column_subset(names, dtypes, rows, None)
        assert out_names == names

    def test_subset(self):
        from great_docs._tbl_preview import _apply_column_subset

        names = ["a", "b", "c"]
        dtypes = ["i64", "str", "f64"]
        rows = [[1, "x", 1.0], [2, "y", 2.0]]
        out_names, _, out_rows = _apply_column_subset(names, dtypes, rows, ["c", "a"])
        assert out_names == ["c", "a"]
        assert out_rows[0] == [1.0, 1]

    def test_invalid_column_raises(self):
        from great_docs._tbl_preview import _apply_column_subset

        with pytest.raises(ValueError, match="not found"):
            _apply_column_subset(["a", "b"], ["i64", "str"], [[1, "x"]], ["z"])


# ---------------------------------------------------------------------------
# Head / tail split
# ---------------------------------------------------------------------------


class TestHeadTail:
    def test_small_dataset_full(self):
        from great_docs._tbl_preview import _compute_head_tail

        rows = [[i] for i in range(8)]
        display, nums, is_full = _compute_head_tail(rows, 8, 5, 5, False)
        assert is_full is True
        assert len(display) == 8

    def test_large_dataset_split(self):
        from great_docs._tbl_preview import _compute_head_tail

        rows = [[i] for i in range(100)]
        display, nums, is_full = _compute_head_tail(rows, 100, 5, 5, False)
        assert is_full is False
        assert len(display) == 10
        assert nums[:5] == [0, 1, 2, 3, 4]
        assert nums[5:] == [95, 96, 97, 98, 99]

    def test_show_all(self):
        from great_docs._tbl_preview import _compute_head_tail

        rows = [[i] for i in range(100)]
        display, nums, is_full = _compute_head_tail(rows, 100, 5, 5, True)
        assert is_full is True
        assert len(display) == 100

    def test_zero_tail(self):
        from great_docs._tbl_preview import _compute_head_tail

        rows = [[i] for i in range(20)]
        display, nums, is_full = _compute_head_tail(rows, 20, 5, 0, False)
        assert is_full is False
        assert len(display) == 5
        assert nums == [0, 1, 2, 3, 4]


# ---------------------------------------------------------------------------
# Cell formatting and escaping
# ---------------------------------------------------------------------------


class TestFormatting:
    def test_format_none(self):
        from great_docs._tbl_preview import _format_cell

        assert _format_cell(None) == "None"

    def test_format_bool(self):
        from great_docs._tbl_preview import _format_cell

        assert _format_cell(True) == "True"
        assert _format_cell(False) == "False"

    def test_format_nan(self):
        from great_docs._tbl_preview import _format_cell

        assert _format_cell(float("nan")) == "NaN"

    def test_format_inf(self):
        from great_docs._tbl_preview import _format_cell

        assert _format_cell(float("inf")) == "Inf"
        assert _format_cell(float("-inf")) == "-Inf"

    def test_format_float(self):
        from great_docs._tbl_preview import _format_cell

        assert _format_cell(3.14) == "3.14"

    def test_format_float_precision(self):
        from great_docs._tbl_preview import _format_cell

        # IEEE 754 noise should be trimmed
        assert _format_cell(3 * 1.1) == "3.3"
        assert _format_cell(24.200000000000003) == "24.2"

    def test_format_string(self):
        from great_docs._tbl_preview import _format_cell

        assert _format_cell("hello") == "hello"

    def test_escape_html(self):
        from great_docs._tbl_preview import _escape

        assert _escape("<b>bold</b>") == "&lt;b&gt;bold&lt;/b&gt;"
        assert _escape('"quoted"') == "&quot;quoted&quot;"


# ---------------------------------------------------------------------------
# Missing value detection
# ---------------------------------------------------------------------------


class TestMissingDetection:
    def test_none_is_missing(self):
        from great_docs._tbl_preview import _is_missing

        assert _is_missing(None) is True

    def test_nan_is_missing(self):
        from great_docs._tbl_preview import _is_missing

        assert _is_missing(float("nan")) is True

    def test_string_not_missing(self):
        from great_docs._tbl_preview import _is_missing

        assert _is_missing("hello") is False

    def test_zero_not_missing(self):
        from great_docs._tbl_preview import _is_missing

        assert _is_missing(0) is False
        assert _is_missing(0.0) is False


# ---------------------------------------------------------------------------
# Alignment detection
# ---------------------------------------------------------------------------


class TestAlignments:
    def test_numeric_right(self):
        from great_docs._tbl_preview import _detect_alignments

        alignments = _detect_alignments(["i64", "f64", "u32"])
        assert all(a == "right" for a in alignments)

    def test_string_left(self):
        from great_docs._tbl_preview import _detect_alignments

        alignments = _detect_alignments(["str", "cat", "bool"])
        assert all(a == "left" for a in alignments)

    def test_mixed(self):
        from great_docs._tbl_preview import _detect_alignments

        alignments = _detect_alignments(["i64", "str", "f64"])
        assert alignments == ["right", "left", "right"]


# ---------------------------------------------------------------------------
# Dtype inference
# ---------------------------------------------------------------------------


class TestDtypeInference:
    def test_int_list(self):
        from great_docs._tbl_preview import _infer_dtype

        assert _infer_dtype([1, 2, 3]) == "i64"

    def test_float_list(self):
        from great_docs._tbl_preview import _infer_dtype

        assert _infer_dtype([1.0, 2.0]) == "f64"

    def test_mixed_int_float(self):
        from great_docs._tbl_preview import _infer_dtype

        assert _infer_dtype([1, 2.0]) == "f64"

    def test_bool_list(self):
        from great_docs._tbl_preview import _infer_dtype

        assert _infer_dtype([True, False]) == "bool"

    def test_string_list(self):
        from great_docs._tbl_preview import _infer_dtype

        assert _infer_dtype(["a", "b"]) == "str"

    def test_none_only(self):
        from great_docs._tbl_preview import _infer_dtype

        assert _infer_dtype([None, None]) == "null"


# ---------------------------------------------------------------------------
# Number formatting
# ---------------------------------------------------------------------------


class TestNumberFormatting:
    def test_small_number(self):
        from great_docs._tbl_preview import _format_number

        assert _format_number(42) == "42"

    def test_thousands(self):
        from great_docs._tbl_preview import _format_number

        assert _format_number(1234567) == "1,234,567"


# ---------------------------------------------------------------------------
# Full tbl_preview() function
# ---------------------------------------------------------------------------


class TestTblPreviewFunction:
    """Integration tests for the main tbl_preview() entry point."""

    def test_dict_basic(self):
        from great_docs._tbl_preview import tbl_preview

        data = {"a": [1, 2, 3], "b": ["x", "y", "z"]}
        result = tbl_preview(data)
        html = result.as_html()
        assert "gd-tbl-preview" in html
        assert "gt_table" in html
        assert "gt_col_heading" in html

    def test_list_of_dicts(self):
        from great_docs._tbl_preview import tbl_preview

        data = [{"x": 1, "y": "a"}, {"x": 2, "y": "b"}]
        result = tbl_preview(data)
        assert "gt_table" in result.as_html()

    def test_head_tail_with_large_data(self):
        from great_docs._tbl_preview import tbl_preview

        data = {"val": list(range(100))}
        result = tbl_preview(data, n_head=3, n_tail=2)
        html = result.as_html()
        # Should show 5 data rows + divider
        assert "gd-tbl-divider" in html

    def test_show_all(self):
        from great_docs._tbl_preview import tbl_preview

        data = {"val": list(range(20))}
        result = tbl_preview(data, show_all=True)
        html = result.as_html()
        # Divider class should not appear on any <tr> element
        assert 'class="gd-tbl-divider"' not in html

    def test_column_subset(self):
        from great_docs._tbl_preview import tbl_preview

        data = {"a": [1], "b": [2], "c": [3]}
        result = tbl_preview(data, columns=["c", "a"])
        html = result.as_html()
        assert 'id="c"' in html
        assert 'id="a"' in html

    def test_caption(self):
        from great_docs._tbl_preview import tbl_preview

        data = {"a": [1]}
        result = tbl_preview(data, caption="My Table")
        assert "My Table" in result.as_html()

    def test_no_dimensions(self):
        from great_docs._tbl_preview import tbl_preview

        data = {"a": [1]}
        result = tbl_preview(data, show_dimensions=False)
        html = result.as_html()
        # No badge spans should appear in the <thead> (CSS still has the class)
        assert 'class="gd-tbl-badge' not in html

    def test_no_row_numbers(self):
        from great_docs._tbl_preview import tbl_preview

        data = {"a": [1, 2]}
        result = tbl_preview(data, show_row_numbers=False)
        # No <td> with rownum class in the body (CSS still defines the class)
        assert 'class="gt_row gt_right gd-tbl-rownum"' not in result.as_html()

    def test_no_dtypes(self):
        from great_docs._tbl_preview import tbl_preview

        data = {"a": [1]}
        result = tbl_preview(data, show_dtypes=False)
        # No dtype div should appear in column headings (CSS still defines the class)
        assert 'class="gd-tbl-dtype"' not in result.as_html()

    def test_highlight_missing(self):
        from great_docs._tbl_preview import tbl_preview

        data = {"a": [1, None, 3]}
        result = tbl_preview(data, highlight_missing=True)
        assert "gd-tbl-missing" in result.as_html()

    def test_no_highlight_missing(self):
        from great_docs._tbl_preview import tbl_preview

        data = {"a": [1, None, 3]}
        result = tbl_preview(data, highlight_missing=False)
        # No missing class on any <td> (CSS still defines the class)
        assert 'gd-tbl-missing"' not in result.as_html()

    def test_custom_id(self):
        from great_docs._tbl_preview import tbl_preview

        data = {"a": [1]}
        result = tbl_preview(data, id="my-table")
        assert 'id="gd-tbl-my-table"' in result.as_html()

    def test_limit_exceeded_raises(self):
        from great_docs._tbl_preview import tbl_preview

        data = {"a": [1]}
        with pytest.raises(ValueError, match="exceeds limit"):
            tbl_preview(data, n_head=30, n_tail=30, limit=50)

    def test_html_escaping_in_data(self):
        from great_docs._tbl_preview import tbl_preview

        data = {"col": ["<script>alert(1)</script>"]}
        result = tbl_preview(data)
        html = result.as_html()
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_save_roundtrip(self, tmp_path: Path):
        from great_docs._tbl_preview import tbl_preview

        data = {"a": [1, 2]}
        result = tbl_preview(data)
        out = tmp_path / "preview.html"
        result.save(out)
        content = out.read_text(encoding="utf-8")
        assert "gt_table" in content

    def test_repr_html_integration(self):
        from great_docs._tbl_preview import tbl_preview

        data = {"a": [1]}
        result = tbl_preview(data)
        assert result._repr_html_() == result.as_html()

    def test_dark_mode_css_present(self):
        from great_docs._tbl_preview import tbl_preview

        data = {"a": [1]}
        html = tbl_preview(data).as_html()
        assert "quarto-dark" in html

    def test_quarto_disable_processing(self):
        from great_docs._tbl_preview import tbl_preview

        data = {"a": [1]}
        html = tbl_preview(data).as_html()
        assert 'data-quarto-disable-processing="true"' in html

    def test_badge_types(self):
        """Verify badge rendering for different table types."""
        from great_docs._tbl_preview import tbl_preview

        # Dict → shows "Table" badge
        data = {"a": [1]}
        html = tbl_preview(data).as_html()
        assert "Table" in html

    def test_csv_roundtrip(self, tmp_path: Path):
        from great_docs._tbl_preview import tbl_preview

        csv = tmp_path / "data.csv"
        csv.write_text("x,y\n1,a\n2,b\n3,c\n")
        result = tbl_preview(str(csv))
        html = result.as_html()
        assert "CSV" in html
        assert "gt_table" in html


# ---------------------------------------------------------------------------
# Shortcode extension files
# ---------------------------------------------------------------------------


class TestShortcodeExtensionFiles:
    """Verify the tbl-preview shortcode extension ships required files."""

    def _ext_dir(self) -> Path:
        return (
            Path(__file__).parent.parent / "great_docs" / "assets" / "_extensions" / "tbl-preview"
        )

    def test_extension_yml_exists(self):
        assert (self._ext_dir() / "_extension.yml").exists()

    def test_lua_filter_exists(self):
        assert (self._ext_dir() / "tbl-preview.lua").exists()

    def test_python_bridge_exists(self):
        assert (self._ext_dir() / "_tbl_preview_shortcode.py").exists()

    def test_extension_yml_declares_shortcode(self):
        import yaml

        ext_yml = self._ext_dir() / "_extension.yml"
        config = yaml.safe_load(ext_yml.read_text())
        shortcodes = config.get("contributes", {}).get("shortcodes", [])
        assert "tbl-preview.lua" in shortcodes


# ---------------------------------------------------------------------------
# Shortcode CLI helper
# ---------------------------------------------------------------------------


class TestShortcodeCLI:
    """Tests for the _tbl_preview_shortcode.py CLI helper."""

    def test_cli_produces_html(self, tmp_path: Path):
        import subprocess
        import sys

        csv = tmp_path / "data.csv"
        csv.write_text("a,b\n1,x\n2,y\n")

        script = (
            Path(__file__).parent.parent
            / "great_docs"
            / "assets"
            / "_extensions"
            / "tbl-preview"
            / "_tbl_preview_shortcode.py"
        )
        result = subprocess.run(
            [sys.executable, str(script), str(csv)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "gt_table" in result.stdout

    def test_cli_with_options(self, tmp_path: Path):
        import subprocess
        import sys

        csv = tmp_path / "data.csv"
        csv.write_text("a,b\n1,x\n2,y\n3,z\n")

        script = (
            Path(__file__).parent.parent
            / "great_docs"
            / "assets"
            / "_extensions"
            / "tbl-preview"
            / "_tbl_preview_shortcode.py"
        )
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                str(csv),
                "--n_head",
                "1",
                "--n_tail",
                "1",
                "--caption",
                "Test Table",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Test Table" in result.stdout


# ---------------------------------------------------------------------------
# Public API exports
# ---------------------------------------------------------------------------


class TestPublicAPI:
    def test_tbl_preview_importable(self):
        from great_docs import tbl_preview

        assert callable(tbl_preview)

    def test_enable_disable_importable(self):
        from great_docs import enable_tbl_preview, disable_tbl_preview

        assert callable(enable_tbl_preview)
        assert callable(disable_tbl_preview)


# ---------------------------------------------------------------------------
# TSV file support
# ---------------------------------------------------------------------------


class TestTSVSupport:
    """Tests for TSV/tab-delimited file reading."""

    def test_tsv_file(self, tmp_path: Path):
        from great_docs._tbl_preview import _normalize_data

        tsv = tmp_path / "data.tsv"
        tsv.write_text("name\tage\tcity\nAlice\t30\tNYC\nBob\t25\tSF\n")
        names, dtypes, rows, n, tbl_type = _normalize_data(str(tsv))
        assert names == ["name", "age", "city"]
        assert n == 2
        assert tbl_type == "tsv"

    def test_tsv_path_object(self, tmp_path: Path):
        from great_docs._tbl_preview import _normalize_data

        tsv = tmp_path / "test.tsv"
        tsv.write_text("a\tb\n1\t2\n3\t4\n")
        names, _, rows, n, tbl_type = _normalize_data(tsv)
        assert n == 2
        assert tbl_type == "tsv"

    def test_tab_extension(self, tmp_path: Path):
        from great_docs._tbl_preview import _normalize_data

        tab = tmp_path / "data.tab"
        tab.write_text("x\ty\n10\t20\n30\t40\n")
        _, _, _, n, tbl_type = _normalize_data(str(tab))
        assert n == 2
        assert tbl_type == "tsv"

    def test_tsv_full_render(self, tmp_path: Path):
        from great_docs._tbl_preview import tbl_preview

        tsv = tmp_path / "render.tsv"
        tsv.write_text("col_a\tcol_b\n1\thello\n2\tworld\n")
        result = tbl_preview(tsv, show_all=True)
        html = result.as_html()
        assert "TSV" in html
        assert "col_a" in html
        assert "hello" in html


# ---------------------------------------------------------------------------
# JSONL file support
# ---------------------------------------------------------------------------


class TestJSONLSupport:
    """Tests for JSONL/NDJSON file reading."""

    def test_jsonl_file(self, tmp_path: Path):
        from great_docs._tbl_preview import _normalize_data

        jsonl = tmp_path / "data.jsonl"
        jsonl.write_text('{"a": 1, "b": "x"}\n{"a": 2, "b": "y"}\n')
        names, dtypes, rows, n, tbl_type = _normalize_data(str(jsonl))
        assert "a" in names
        assert "b" in names
        assert n == 2
        assert tbl_type == "jsonl"

    def test_ndjson_extension(self, tmp_path: Path):
        from great_docs._tbl_preview import _normalize_data

        ndjson = tmp_path / "data.ndjson"
        ndjson.write_text('{"x": 10}\n{"x": 20}\n{"x": 30}\n')
        names, _, rows, n, tbl_type = _normalize_data(str(ndjson))
        assert names == ["x"]
        assert n == 3
        assert tbl_type == "jsonl"

    def test_jsonl_full_render(self, tmp_path: Path):
        from great_docs._tbl_preview import tbl_preview

        jsonl = tmp_path / "test.jsonl"
        jsonl.write_text('{"name": "Alice", "score": 95}\n{"name": "Bob", "score": 88}\n')
        result = tbl_preview(jsonl, show_all=True)
        html = result.as_html()
        assert "JSONL" in html
        assert "Alice" in html


# ---------------------------------------------------------------------------
# Parquet file support
# ---------------------------------------------------------------------------


class TestParquetSupport:
    """Tests for Parquet file reading."""

    @pytest.fixture(autouse=True)
    def _require_polars(self):
        pytest.importorskip("polars")

    def test_parquet_file(self, tmp_path: Path):
        import polars as pl
        from great_docs._tbl_preview import _normalize_data

        pq = tmp_path / "data.parquet"
        pl.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]}).write_parquet(str(pq))
        names, dtypes, rows, n, tbl_type = _normalize_data(str(pq))
        assert names == ["a", "b"]
        assert n == 3
        assert tbl_type == "parquet"

    def test_parquet_full_render(self, tmp_path: Path):
        import polars as pl
        from great_docs._tbl_preview import tbl_preview

        pq = tmp_path / "data.parquet"
        pl.DataFrame({"id": [1, 2], "value": [3.14, 2.72]}).write_parquet(str(pq))
        result = tbl_preview(pq, show_all=True)
        html = result.as_html()
        assert "Parquet" in html
        assert "3.14" in html


# ---------------------------------------------------------------------------
# Feather / Arrow IPC file support
# ---------------------------------------------------------------------------


class TestFeatherSupport:
    """Tests for Feather and Arrow IPC file reading."""

    @pytest.fixture(autouse=True)
    def _require_polars(self):
        pytest.importorskip("polars")

    def test_feather_file(self, tmp_path: Path):
        import polars as pl
        from great_docs._tbl_preview import _normalize_data

        feather = tmp_path / "data.feather"
        pl.DataFrame({"x": [10, 20], "y": [30, 40]}).write_ipc(str(feather))
        names, _, rows, n, tbl_type = _normalize_data(str(feather))
        assert names == ["x", "y"]
        assert n == 2
        assert tbl_type == "feather"

    def test_arrow_ipc_extension(self, tmp_path: Path):
        import polars as pl
        from great_docs._tbl_preview import _normalize_data

        ipc = tmp_path / "data.ipc"
        pl.DataFrame({"a": [1, 2, 3]}).write_ipc(str(ipc))
        _, _, _, n, tbl_type = _normalize_data(str(ipc))
        assert n == 3
        assert tbl_type == "arrow"

    def test_arrow_extension(self, tmp_path: Path):
        import polars as pl
        from great_docs._tbl_preview import _normalize_data

        arrow_file = tmp_path / "data.arrow"
        pl.DataFrame({"col": [100, 200]}).write_ipc(str(arrow_file))
        _, _, _, n, tbl_type = _normalize_data(str(arrow_file))
        assert n == 2
        assert tbl_type == "arrow"

    def test_feather_full_render(self, tmp_path: Path):
        import polars as pl
        from great_docs._tbl_preview import tbl_preview

        feather = tmp_path / "data.feather"
        pl.DataFrame({"name": ["a", "b"], "val": [1, 2]}).write_ipc(str(feather))
        result = tbl_preview(feather, show_all=True)
        html = result.as_html()
        assert "Feather" in html


# ---------------------------------------------------------------------------
# PyArrow Table support
# ---------------------------------------------------------------------------


class TestArrowTableSupport:
    """Tests for PyArrow Table objects."""

    @pytest.fixture(autouse=True)
    def _require_pyarrow(self):
        pytest.importorskip("pyarrow")

    def test_arrow_table(self):
        import pyarrow as pa
        from great_docs._tbl_preview import _normalize_data

        tbl = pa.table({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        names, dtypes, rows, n, tbl_type = _normalize_data(tbl)
        assert names == ["a", "b"]
        assert n == 3
        assert tbl_type == "arrow"

    def test_arrow_table_dtypes(self):
        from great_docs._tbl_preview import _arrow_dtype_short

        assert _arrow_dtype_short("int64") == "i64"
        assert _arrow_dtype_short("double") == "f64"
        assert _arrow_dtype_short("string") == "str"
        assert _arrow_dtype_short("utf8") == "str"
        assert _arrow_dtype_short("bool") == "bool"
        assert _arrow_dtype_short("timestamp[us]") == "dtime"
        assert _arrow_dtype_short("date32[day]") == "date"

    def test_arrow_table_full_render(self):
        import pyarrow as pa
        from great_docs._tbl_preview import tbl_preview

        tbl = pa.table({"id": [1, 2, 3], "name": ["Alice", "Bob", "Eve"]})
        result = tbl_preview(tbl, show_all=True)
        html = result.as_html()
        assert "Arrow" in html
        assert "Alice" in html
        assert "gt_table" in html


# ---------------------------------------------------------------------------
# File extension mapping
# ---------------------------------------------------------------------------


class TestFileExtensionMap:
    """Tests for the file extension → format dispatch."""

    def test_extension_map_coverage(self):
        from great_docs._tbl_preview import _FILE_EXT_MAP

        assert _FILE_EXT_MAP[".csv"] == "csv"
        assert _FILE_EXT_MAP[".tsv"] == "tsv"
        assert _FILE_EXT_MAP[".tab"] == "tsv"
        assert _FILE_EXT_MAP[".jsonl"] == "jsonl"
        assert _FILE_EXT_MAP[".ndjson"] == "jsonl"
        assert _FILE_EXT_MAP[".parquet"] == "parquet"
        assert _FILE_EXT_MAP[".pq"] == "parquet"
        assert _FILE_EXT_MAP[".feather"] == "feather"
        assert _FILE_EXT_MAP[".arrow"] == "arrow"
        assert _FILE_EXT_MAP[".ipc"] == "arrow"

    def test_badge_styles_for_all_types(self):
        from great_docs._tbl_preview import _TABLE_TYPE_STYLES

        for fmt in (
            "polars",
            "pandas",
            "csv",
            "tsv",
            "jsonl",
            "arrow",
            "parquet",
            "feather",
            "dict",
        ):
            assert fmt in _TABLE_TYPE_STYLES, f"Missing badge style for {fmt}"
            assert "bg" in _TABLE_TYPE_STYLES[fmt]
            assert "label" in _TABLE_TYPE_STYLES[fmt]


# ---------------------------------------------------------------------------
# Snapshot tests — cross-backend consistency
# ---------------------------------------------------------------------------

# Canonical reference data used across all backends.
# Intentionally includes int, float, string, bool.
_CANONICAL_DATA: dict[str, list] = {
    "name": ["Alice", "Bob", "Charlie"],
    "score": [95.5, 82.0, 71.3],
    "rank": [1, 2, 3],
    "passed": [True, True, False],
}

_CANONICAL_NAMES = ["name", "score", "rank", "passed"]
_CANONICAL_ROWS = [
    ["Alice", 95.5, 1, True],
    ["Bob", 82.0, 2, True],
    ["Charlie", 71.3, 3, False],
]


def _strip_id_and_badge(html: str) -> str:
    """Normalize HTML for comparison by replacing the random table ID and
    the badge label/colors, which legitimately differ across backends."""
    import re

    # Replace gd-tbl-XXXXXXXX id with a placeholder
    html = re.sub(r'id="gd-tbl-[a-f0-9]+"', 'id="gd-tbl-XXXX"', html)
    html = re.sub(r"#gd-tbl-[a-f0-9]+", "#gd-tbl-XXXX", html)
    # Replace the badge label (Polars, Pandas, CSV, etc.) with a placeholder
    for label in (
        "Polars",
        "Pandas",
        "CSV",
        "TSV",
        "JSONL",
        "Arrow",
        "Parquet",
        "Feather",
        "Table",
    ):
        html = html.replace(f">{label}<", ">TYPE<")
    # Replace ALL hex color references (badge bg, fg, border colors differ by type)
    html = re.sub(r"#[A-Fa-f0-9]{6}", "#XXXXXX", html)
    return html


class TestCrossBackendSnapshots:
    """Verify that all backends produce identical normalization results
    and identical HTML output (modulo badge label and table ID) for the
    same canonical dataset."""

    # -- Normalization snapshots (column names, dtypes, rows) ---------------

    def test_dict_snapshot(self):
        from great_docs._tbl_preview import _normalize_data

        names, dtypes, rows, n, tbl_type = _normalize_data(_CANONICAL_DATA)
        assert names == _CANONICAL_NAMES
        assert n == 3
        assert tbl_type == "dict"
        assert rows == _CANONICAL_ROWS

    def test_polars_snapshot(self):
        pl = pytest.importorskip("polars")
        from great_docs._tbl_preview import _normalize_data

        df = pl.DataFrame(_CANONICAL_DATA)
        names, dtypes, rows, n, tbl_type = _normalize_data(df)
        assert names == _CANONICAL_NAMES
        assert n == 3
        assert tbl_type == "polars"
        assert rows == _CANONICAL_ROWS
        assert dtypes == ["str", "f64", "i64", "bool"]

    def test_pandas_snapshot(self):
        pd = pytest.importorskip("pandas")
        from great_docs._tbl_preview import _normalize_data

        df = pd.DataFrame(_CANONICAL_DATA)
        names, dtypes, rows, n, tbl_type = _normalize_data(df)
        assert names == _CANONICAL_NAMES
        assert n == 3
        assert tbl_type == "pandas"
        assert rows == _CANONICAL_ROWS

    def test_pyarrow_snapshot(self):
        pa = pytest.importorskip("pyarrow")
        from great_docs._tbl_preview import _normalize_data

        tbl = pa.table(_CANONICAL_DATA)
        names, dtypes, rows, n, tbl_type = _normalize_data(tbl)
        assert names == _CANONICAL_NAMES
        assert n == 3
        assert tbl_type == "arrow"
        assert rows == _CANONICAL_ROWS
        assert dtypes == ["str", "f64", "i64", "bool"]

    def test_csv_snapshot(self, tmp_path: Path):
        from great_docs._tbl_preview import _normalize_data

        csv = tmp_path / "data.csv"
        csv.write_text(
            "name,score,rank,passed\nAlice,95.5,1,true\nBob,82.0,2,true\nCharlie,71.3,3,false\n"
        )
        names, dtypes, rows, n, tbl_type = _normalize_data(str(csv))
        assert names == _CANONICAL_NAMES
        assert n == 3
        assert tbl_type == "csv"
        # CSV reads may coerce types differently — compare stringified values
        for i, ref_row in enumerate(_CANONICAL_ROWS):
            for j, ref_val in enumerate(ref_row):
                assert str(rows[i][j]).lower() == str(ref_val).lower(), (
                    f"Row {i}, col {j}: {rows[i][j]!r} != {ref_val!r}"
                )

    def test_tsv_snapshot(self, tmp_path: Path):
        from great_docs._tbl_preview import _normalize_data

        tsv = tmp_path / "data.tsv"
        tsv.write_text(
            "name\tscore\trank\tpassed\n"
            "Alice\t95.5\t1\ttrue\n"
            "Bob\t82.0\t2\ttrue\n"
            "Charlie\t71.3\t3\tfalse\n"
        )
        names, dtypes, rows, n, tbl_type = _normalize_data(str(tsv))
        assert names == _CANONICAL_NAMES
        assert n == 3
        assert tbl_type == "tsv"
        for i, ref_row in enumerate(_CANONICAL_ROWS):
            for j, ref_val in enumerate(ref_row):
                assert str(rows[i][j]).lower() == str(ref_val).lower(), (
                    f"Row {i}, col {j}: {rows[i][j]!r} != {ref_val!r}"
                )

    def test_jsonl_snapshot(self, tmp_path: Path):
        import json
        from great_docs._tbl_preview import _normalize_data

        jsonl = tmp_path / "data.jsonl"
        lines = []
        for i in range(3):
            row = {k: v[i] for k, v in _CANONICAL_DATA.items()}
            lines.append(json.dumps(row))
        jsonl.write_text("\n".join(lines) + "\n")
        names, dtypes, rows, n, tbl_type = _normalize_data(str(jsonl))
        assert names == _CANONICAL_NAMES
        assert n == 3
        assert tbl_type == "jsonl"
        assert rows == _CANONICAL_ROWS

    def test_parquet_snapshot(self, tmp_path: Path):
        pl = pytest.importorskip("polars")
        from great_docs._tbl_preview import _normalize_data

        pq = tmp_path / "data.parquet"
        pl.DataFrame(_CANONICAL_DATA).write_parquet(str(pq))
        names, dtypes, rows, n, tbl_type = _normalize_data(str(pq))
        assert names == _CANONICAL_NAMES
        assert n == 3
        assert tbl_type == "parquet"
        assert rows == _CANONICAL_ROWS
        assert dtypes == ["str", "f64", "i64", "bool"]

    def test_feather_snapshot(self, tmp_path: Path):
        pl = pytest.importorskip("polars")
        from great_docs._tbl_preview import _normalize_data

        feather = tmp_path / "data.feather"
        pl.DataFrame(_CANONICAL_DATA).write_ipc(str(feather))
        names, dtypes, rows, n, tbl_type = _normalize_data(str(feather))
        assert names == _CANONICAL_NAMES
        assert n == 3
        assert tbl_type == "feather"
        assert rows == _CANONICAL_ROWS
        assert dtypes == ["str", "f64", "i64", "bool"]

    # -- Full HTML markup snapshots -----------------------------------------

    def _render_canonical(self, data: Any) -> str:
        """Render canonical data with fixed options and normalize the HTML."""
        from great_docs._tbl_preview import tbl_preview

        result = tbl_preview(
            data,
            show_all=True,
            show_row_numbers=True,
            show_dtypes=True,
            show_dimensions=True,
            max_col_width=250,
            min_tbl_width=500,
        )
        return _strip_id_and_badge(result.as_html())

    def test_html_dict_vs_polars(self):
        pl = pytest.importorskip("polars")
        html_dict = self._render_canonical(_CANONICAL_DATA)
        html_polars = self._render_canonical(pl.DataFrame(_CANONICAL_DATA))
        assert html_dict == html_polars

    def test_html_dict_vs_pandas(self):
        pd = pytest.importorskip("pandas")
        html_dict = self._render_canonical(_CANONICAL_DATA)
        html_pandas = self._render_canonical(pd.DataFrame(_CANONICAL_DATA))
        assert html_dict == html_pandas

    def test_html_dict_vs_pyarrow(self):
        pa = pytest.importorskip("pyarrow")
        html_dict = self._render_canonical(_CANONICAL_DATA)
        html_arrow = self._render_canonical(pa.table(_CANONICAL_DATA))
        assert html_dict == html_arrow

    def test_html_dict_vs_csv(self, tmp_path: Path):
        csv = tmp_path / "data.csv"
        csv.write_text(
            "name,score,rank,passed\nAlice,95.5,1,true\nBob,82.0,2,true\nCharlie,71.3,3,false\n"
        )
        html_dict = self._render_canonical(_CANONICAL_DATA)
        html_csv = self._render_canonical(str(csv))
        assert html_dict == html_csv

    def test_html_dict_vs_tsv(self, tmp_path: Path):
        tsv = tmp_path / "data.tsv"
        tsv.write_text(
            "name\tscore\trank\tpassed\n"
            "Alice\t95.5\t1\ttrue\n"
            "Bob\t82.0\t2\ttrue\n"
            "Charlie\t71.3\t3\tfalse\n"
        )
        html_dict = self._render_canonical(_CANONICAL_DATA)
        html_tsv = self._render_canonical(str(tsv))
        assert html_dict == html_tsv

    def test_html_dict_vs_jsonl(self, tmp_path: Path):
        import json

        jsonl = tmp_path / "data.jsonl"
        lines = []
        for i in range(3):
            row = {k: v[i] for k, v in _CANONICAL_DATA.items()}
            lines.append(json.dumps(row))
        jsonl.write_text("\n".join(lines) + "\n")
        html_dict = self._render_canonical(_CANONICAL_DATA)
        html_jsonl = self._render_canonical(str(jsonl))
        assert html_dict == html_jsonl

    def test_html_dict_vs_parquet(self, tmp_path: Path):
        pl = pytest.importorskip("polars")
        pq = tmp_path / "data.parquet"
        pl.DataFrame(_CANONICAL_DATA).write_parquet(str(pq))
        html_dict = self._render_canonical(_CANONICAL_DATA)
        html_pq = self._render_canonical(str(pq))
        assert html_dict == html_pq

    def test_html_dict_vs_feather(self, tmp_path: Path):
        pl = pytest.importorskip("polars")
        feather = tmp_path / "data.feather"
        pl.DataFrame(_CANONICAL_DATA).write_ipc(str(feather))
        html_dict = self._render_canonical(_CANONICAL_DATA)
        html_feather = self._render_canonical(str(feather))
        assert html_dict == html_feather

    # -- Structural HTML element snapshots ----------------------------------

    def test_html_has_expected_structure(self):
        """Verify all key HTML elements are present in every render."""
        from great_docs._tbl_preview import tbl_preview

        result = tbl_preview(_CANONICAL_DATA, show_all=True)
        html = result.as_html()

        # Outer container
        assert 'class="gd-tbl-preview"' in html
        # Scoped CSS
        assert "<style>" in html
        # Table element
        assert 'class="gt_table"' in html
        # Colgroup
        assert "<colgroup>" in html
        assert html.count("<col ") == 5  # 4 data cols + 1 rownum col
        # Header banner with badges
        assert "gd-tbl-badge" in html
        assert "Table" in html  # dict badge
        # Column headings (4 data columns + rownum + possible extras in structure)
        assert html.count('class="gt_col_heading') >= 4
        # Dtype labels (inside <em> elements)
        for dtype in ("str", "f64", "i64", "bool"):
            assert f"<em>{dtype}</em>" in html
        # Data rows (3 rows × ≥4 cells each)
        assert html.count('class="gt_row') >= 3 * 4
        # Row numbers
        assert "gd-tbl-rownum" in html
        # Cell values
        for val in (
            "Alice",
            "Bob",
            "Charlie",
            "95.5",
            "82",
            "71.3",
            "1",
            "2",
            "3",
            "True",
            "False",
        ):
            assert val in html

    def test_html_cell_values_exact(self):
        """Snapshot the exact formatted cell values in each row."""
        from great_docs._tbl_preview import _format_cell

        expected = [
            ["Alice", "95.5", "1", "True"],
            ["Bob", "82", "2", "True"],
            ["Charlie", "71.3", "3", "False"],
        ]
        for i, ref_row in enumerate(_CANONICAL_ROWS):
            formatted = [_format_cell(v) for v in ref_row]
            assert formatted == expected[i], f"Row {i}: {formatted} != {expected[i]}"

    def test_head_tail_snapshot(self):
        """Verify head/tail split inserts the divider at the right place."""
        from great_docs._tbl_preview import tbl_preview

        data = {"v": list(range(100))}
        html = tbl_preview(data, n_head=3, n_tail=2).as_html()
        # Should have exactly one divider <tr> element
        assert html.count('class="gd-tbl-divider"') == 1
        # Head rows: 0, 1, 2; Tail rows: 98, 99
        for v in (0, 1, 2, 98, 99):
            assert str(v) in html
        # Middle rows should NOT appear
        for v in (50, 51, 52):
            assert f">{v}<" not in html

    # -- Missing value snapshot across backends -----------------------------

    def test_missing_snapshot_dict(self):
        from great_docs._tbl_preview import _normalize_data

        data = {"a": [1, None, 3], "b": ["x", "y", None]}
        _, _, rows, _, _ = _normalize_data(data)
        assert rows[1][0] is None
        assert rows[2][1] is None

    def test_missing_snapshot_polars(self):
        pl = pytest.importorskip("polars")
        from great_docs._tbl_preview import _normalize_data

        df = pl.DataFrame({"a": [1, None, 3], "b": ["x", "y", None]})
        _, _, rows, _, _ = _normalize_data(df)
        assert rows[1][0] is None
        assert rows[2][1] is None

    def test_missing_snapshot_pandas(self):
        pd = pytest.importorskip("pandas")
        from great_docs._tbl_preview import _normalize_data, _is_missing

        df = pd.DataFrame({"a": [1, None, 3], "b": ["x", "y", None]})
        _, _, rows, _, _ = _normalize_data(df)
        # Pandas converts int-with-None to float NaN
        assert _is_missing(rows[1][0])
        assert _is_missing(rows[2][1])

    def test_missing_snapshot_pyarrow(self):
        pa = pytest.importorskip("pyarrow")
        from great_docs._tbl_preview import _normalize_data

        tbl = pa.table({"a": [1, None, 3], "b": ["x", "y", None]})
        _, _, rows, _, _ = _normalize_data(tbl)
        assert rows[1][0] is None
        assert rows[2][1] is None

    # -- Dtype snapshot across backends ------------------------------------

    def test_dtype_labels_polars(self):
        pl = pytest.importorskip("polars")
        from great_docs._tbl_preview import _normalize_data

        df = pl.DataFrame({"i": [1], "f": [1.0], "s": ["a"], "b": [True]})
        _, dtypes, _, _, _ = _normalize_data(df)
        assert dtypes == ["i64", "f64", "str", "bool"]

    def test_dtype_labels_pandas(self):
        pd = pytest.importorskip("pandas")
        from great_docs._tbl_preview import _normalize_data

        df = pd.DataFrame(
            {
                "i": pd.array([1], dtype="int64"),
                "f": pd.array([1.0], dtype="float64"),
                "s": pd.array(["a"], dtype="object"),
                "b": pd.array([True], dtype="bool"),
            }
        )
        _, dtypes, _, _, _ = _normalize_data(df)
        assert dtypes == ["i64", "f64", "str", "bool"]

    def test_dtype_labels_pyarrow(self):
        pa = pytest.importorskip("pyarrow")
        from great_docs._tbl_preview import _normalize_data

        tbl = pa.table(
            {
                "i": pa.array([1], type=pa.int64()),
                "f": pa.array([1.0], type=pa.float64()),
                "s": pa.array(["a"], type=pa.string()),
                "b": pa.array([True], type=pa.bool_()),
            }
        )
        _, dtypes, _, _, _ = _normalize_data(tbl)
        assert dtypes == ["i64", "f64", "str", "bool"]

    def test_dtype_labels_dict_inferred(self):
        from great_docs._tbl_preview import _normalize_data

        data = {"i": [1], "f": [1.0], "s": ["a"], "b": [True]}
        _, dtypes, _, _, _ = _normalize_data(data)
        assert dtypes == ["i64", "f64", "str", "bool"]


# ---------------------------------------------------------------------------
# Parameter-combo cell-value snapshots
# ---------------------------------------------------------------------------

import re as _re


def _extract_data_cells(html: str) -> list[list[str]]:
    """Extract data-cell text from rendered HTML, grouped by row.

    Skips row-number cells (class contains gd-tbl-rownum).
    Returns a list of rows, each a list of cell text strings.
    """
    # Find <tbody>, then iterate <tr> elements, extracting <td> cells per row
    tbody_match = _re.search(r"<tbody[^>]*>(.*?)</tbody>", html, _re.DOTALL)
    if not tbody_match:
        return []
    tbody = tbody_match.group(1)
    tr_pattern = r"<tr[^>]*>(.*?)</tr>"
    td_pattern = r'<td class="gt_row ([^"]*?)"[^>]*?>(.*?)</td>'
    rows: list[list[str]] = []
    for tr_match in _re.finditer(tr_pattern, tbody, _re.DOTALL):
        tr_html = tr_match.group(1)
        row_cells: list[str] = []
        for cls, content in _re.findall(td_pattern, tr_html, _re.DOTALL):
            if "gd-tbl-rownum" in cls:
                continue
            row_cells.append(content)
        if row_cells:
            rows.append(row_cells)
    return rows


def _extract_column_headers(html: str) -> list[str]:
    """Extract data column names from rendered HTML."""
    pattern = r'scope="col" id="([^"]*)"'
    return _re.findall(pattern, html)


def _extract_row_numbers(html: str) -> list[str]:
    """Extract row-number cell text from rendered HTML."""
    pattern = r'<td class="gt_row [^"]*?gd-tbl-rownum[^"]*?"[^>]*?>(.*?)</td>'
    return _re.findall(pattern, html, _re.DOTALL)


def _has_missing_class(html: str) -> list[bool]:
    """Return a flat list of booleans: True for each data cell that has the
    gd-tbl-missing class."""
    pattern = r'<td class="gt_row ([^"]*)"[^>]*?>(.*?)</td>'
    results = []
    for cls, _ in _re.findall(pattern, html, _re.DOTALL):
        if "gd-tbl-rownum" in cls:
            continue
        results.append("gd-tbl-missing" in cls)
    return results


# Reference dataset for parameter-combo tests.
_PARAM_DATA: dict[str, list] = {
    "name": ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Hank", "Iris", "Jack"],
    "score": [95.5, 82.0, 71.3, 60.0, 55.8, 88.2, 79.9, 91.0, 66.4, 73.7],
    "grade": ["A", "B", "C", "D", "F", "B+", "C+", "A-", "D+", "C"],
}

_PARAM_DATA_MISSING: dict[str, list] = {
    "x": [1, None, 3, 4, None],
    "y": ["a", "b", None, "d", None],
    "z": [1.1, float("nan"), 3.3, None, 5.5],
}


class TestParameterComboSnapshots:
    """Minimal cell-value snapshot tests for different parameter combinations."""

    # -- show_all=True: all rows present -----------------------------------

    def test_show_all_cells(self):
        from great_docs._tbl_preview import tbl_preview

        html = tbl_preview(_PARAM_DATA, show_all=True).as_html()
        cells = _extract_data_cells(html)
        assert len(cells) == 10
        assert cells[0] == ["Alice", "95.5", "A"]
        assert cells[4] == ["Eve", "55.8", "F"]
        assert cells[9] == ["Jack", "73.7", "C"]

    # -- n_head / n_tail: head/tail rows -----------------------------------

    def test_head3_tail2_cells(self):
        from great_docs._tbl_preview import tbl_preview

        html = tbl_preview(_PARAM_DATA, n_head=3, n_tail=2).as_html()
        cells = _extract_data_cells(html)
        assert len(cells) == 5
        # Head rows
        assert cells[0] == ["Alice", "95.5", "A"]
        assert cells[1] == ["Bob", "82", "B"]
        assert cells[2] == ["Charlie", "71.3", "C"]
        # Tail rows
        assert cells[3] == ["Iris", "66.4", "D+"]
        assert cells[4] == ["Jack", "73.7", "C"]

    def test_head_only_cells(self):
        from great_docs._tbl_preview import tbl_preview

        html = tbl_preview(_PARAM_DATA, n_head=4, n_tail=0).as_html()
        cells = _extract_data_cells(html)
        assert len(cells) == 4
        assert cells[0][0] == "Alice"
        assert cells[3][0] == "Diana"

    def test_tail_only_cells(self):
        from great_docs._tbl_preview import tbl_preview

        html = tbl_preview(_PARAM_DATA, n_head=0, n_tail=3).as_html()
        cells = _extract_data_cells(html)
        assert len(cells) == 3
        assert cells[0][0] == "Hank"
        assert cells[2][0] == "Jack"

    # -- column subset -----------------------------------------------------

    def test_column_subset_cells(self):
        from great_docs._tbl_preview import tbl_preview

        html = tbl_preview(_PARAM_DATA, columns=["grade", "name"], show_all=True).as_html()
        headers = _extract_column_headers(html)
        assert headers == ["grade", "name"]
        cells = _extract_data_cells(html)
        assert len(cells) == 10
        assert cells[0] == ["A", "Alice"]
        assert cells[5] == ["B+", "Frank"]

    def test_single_column_cells(self):
        from great_docs._tbl_preview import tbl_preview

        html = tbl_preview(_PARAM_DATA, columns=["score"], show_all=True).as_html()
        headers = _extract_column_headers(html)
        assert headers == ["score"]
        cells = _extract_data_cells(html)
        assert all(len(row) == 1 for row in cells)
        assert cells[0] == ["95.5"]

    # -- show_row_numbers --------------------------------------------------

    def test_row_numbers_present(self):
        from great_docs._tbl_preview import tbl_preview

        html = tbl_preview(_PARAM_DATA, show_all=True, show_row_numbers=True).as_html()
        nums = _extract_row_numbers(html)
        assert nums == [str(i) for i in range(0, 10)]

    def test_row_numbers_absent(self):
        from great_docs._tbl_preview import tbl_preview

        html = tbl_preview(_PARAM_DATA, show_all=True, show_row_numbers=False).as_html()
        nums = _extract_row_numbers(html)
        assert nums == []
        # Data cells still present
        cells = _extract_data_cells(html)
        assert len(cells) == 10

    def test_row_numbers_head_tail(self):
        from great_docs._tbl_preview import tbl_preview

        html = tbl_preview(_PARAM_DATA, n_head=2, n_tail=2).as_html()
        nums = _extract_row_numbers(html)
        assert nums == ["0", "1", "8", "9"]

    def test_row_index_offset_one(self):
        from great_docs._tbl_preview import tbl_preview

        html = tbl_preview(
            _PARAM_DATA, show_all=True, show_row_numbers=True, row_index_offset=1
        ).as_html()
        nums = _extract_row_numbers(html)
        assert nums == [str(i) for i in range(1, 11)]

    def test_row_index_offset_head_tail(self):
        from great_docs._tbl_preview import tbl_preview

        html = tbl_preview(_PARAM_DATA, n_head=2, n_tail=2, row_index_offset=1).as_html()
        nums = _extract_row_numbers(html)
        assert nums == ["1", "2", "9", "10"]

    # -- highlight_missing -------------------------------------------------

    def test_missing_highlighted(self):
        from great_docs._tbl_preview import tbl_preview

        html = tbl_preview(_PARAM_DATA_MISSING, show_all=True, highlight_missing=True).as_html()
        missing_flags = _has_missing_class(html)
        cells = _extract_data_cells(html)
        # Row 1 (idx 1): x=None, y="b", z=NaN → missing at col 0 and 2
        n_cols = 3
        assert missing_flags[1 * n_cols + 0] is True  # None
        assert missing_flags[1 * n_cols + 1] is False  # "b"
        assert missing_flags[1 * n_cols + 2] is True  # NaN
        # Row 2 (idx 2): x=3, y=None, z=3.3 → missing at col 1
        assert missing_flags[2 * n_cols + 0] is False
        assert missing_flags[2 * n_cols + 1] is True
        assert missing_flags[2 * n_cols + 2] is False

    def test_missing_not_highlighted(self):
        from great_docs._tbl_preview import tbl_preview

        html = tbl_preview(_PARAM_DATA_MISSING, show_all=True, highlight_missing=False).as_html()
        missing_flags = _has_missing_class(html)
        # No cell should have the missing class
        assert not any(missing_flags)
        # But the cell text should still show None/NaN
        cells = _extract_data_cells(html)
        assert cells[1][0] == "None"
        assert cells[1][2] == "NaN"

    # -- show_dtypes -------------------------------------------------------

    def test_dtypes_shown(self):
        from great_docs._tbl_preview import tbl_preview

        html = tbl_preview(_PARAM_DATA, show_all=True, show_dtypes=True).as_html()
        assert 'class="gd-tbl-dtype">' in html
        for dt in ("str", "f64"):
            assert f"<em>{dt}</em>" in html

    def test_dtypes_hidden(self):
        from great_docs._tbl_preview import tbl_preview

        html = tbl_preview(_PARAM_DATA, show_all=True, show_dtypes=False).as_html()
        assert 'class="gd-tbl-dtype">' not in html

    # -- show_dimensions ---------------------------------------------------

    def test_dimensions_shown(self):
        from great_docs._tbl_preview import tbl_preview

        html = tbl_preview(_PARAM_DATA, show_all=True, show_dimensions=True).as_html()
        assert "gd-tbl-badge" in html
        assert "Rows" in html
        assert "Columns" in html

    def test_dimensions_hidden(self):
        from great_docs._tbl_preview import tbl_preview

        html = tbl_preview(_PARAM_DATA, show_all=True, show_dimensions=False).as_html()
        assert 'class="gd-tbl-badge' not in html

    # -- caption -----------------------------------------------------------

    def test_caption_present(self):
        from great_docs._tbl_preview import tbl_preview

        html = tbl_preview(_PARAM_DATA, show_all=True, caption="Student Scores").as_html()
        assert "Student Scores" in html

    def test_caption_absent(self):
        from great_docs._tbl_preview import tbl_preview

        html = tbl_preview(_PARAM_DATA, show_all=True, caption=None).as_html()
        # Caption element should not appear in the table body
        assert '<td class="gt_heading gt_subtitle' not in html

    # -- combined minimal chrome -------------------------------------------

    def test_minimal_chrome_cells(self):
        """No row numbers, no dtypes, no dimensions — just the data."""
        from great_docs._tbl_preview import tbl_preview

        html = tbl_preview(
            _PARAM_DATA,
            show_all=True,
            show_row_numbers=False,
            show_dtypes=False,
            show_dimensions=False,
        ).as_html()
        cells = _extract_data_cells(html)
        assert len(cells) == 10
        assert cells[0] == ["Alice", "95.5", "A"]
        nums = _extract_row_numbers(html)
        assert nums == []
        assert 'class="gd-tbl-badge' not in html
        assert 'class="gd-tbl-dtype">' not in html

    # -- mixed types and edge values ---------------------------------------

    def test_edge_values_cells(self):
        from great_docs._tbl_preview import tbl_preview

        data = {
            "val": [
                0,
                -1,
                2**31,
                1e10,
                float("inf"),
                float("-inf"),
                float("nan"),
                None,
                True,
                False,
            ],
        }
        html = tbl_preview(data, show_all=True).as_html()
        cells = _extract_data_cells(html)
        expected = [
            ["0"],
            ["-1"],
            [str(2**31)],
            ["10000000000"],
            ["Inf"],
            ["-Inf"],
            ["NaN"],
            ["None"],
            ["True"],
            ["False"],
        ]
        assert cells == expected

    # -- float precision ---------------------------------------------------

    def test_float_precision_cells(self):
        from great_docs._tbl_preview import tbl_preview

        data = {"v": [3 * 1.1, 0.1 + 0.2, 24.200000000000003, 1.0, 0.0]}
        html = tbl_preview(data, show_all=True).as_html()
        cells = _extract_data_cells(html)
        assert cells == [["3.3"], ["0.3"], ["24.2"], ["1"], ["0"]]

    # -- HTML escaping in cells --------------------------------------------

    def test_html_escaping_cells(self):
        from great_docs._tbl_preview import tbl_preview

        data = {"html": ["<b>bold</b>", 'a "quote"', "x&y"]}
        html = tbl_preview(data, show_all=True).as_html()
        cells = _extract_data_cells(html)
        assert cells[0] == ["&lt;b&gt;bold&lt;/b&gt;"]
        assert cells[1] == ["a &quot;quote&quot;"]
        assert cells[2] == ["x&amp;y"]

    # -- head_tail + column subset combo -----------------------------------

    def test_head_tail_with_column_subset(self):
        from great_docs._tbl_preview import tbl_preview

        html = tbl_preview(_PARAM_DATA, n_head=2, n_tail=1, columns=["name", "grade"]).as_html()
        headers = _extract_column_headers(html)
        assert headers == ["name", "grade"]
        cells = _extract_data_cells(html)
        assert len(cells) == 3
        assert cells[0] == ["Alice", "A"]
        assert cells[1] == ["Bob", "B"]
        assert cells[2] == ["Jack", "C"]

    # -- empty and single-row edge cases -----------------------------------

    def test_single_row_cells(self):
        from great_docs._tbl_preview import tbl_preview

        data = {"a": [42], "b": ["only"]}
        html = tbl_preview(data, show_all=True).as_html()
        cells = _extract_data_cells(html)
        assert cells == [["42", "only"]]

    def test_empty_string_cells(self):
        from great_docs._tbl_preview import tbl_preview

        data = {"a": ["", "x", ""], "b": [1, 2, 3]}
        html = tbl_preview(data, show_all=True).as_html()
        cells = _extract_data_cells(html)
        assert cells[0] == ["", "1"]
        assert cells[2] == ["", "3"]
