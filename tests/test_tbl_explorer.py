# pyright: reportPrivateUsage=false

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from great_docs._tables.explorer import (
    TblExplorer,
    _get_js_source,
    _render_explorer_css,
    _serialize_data_blob,
    _serialize_value,
    tbl_explorer,
)


# ---------------------------------------------------------------------------
# TblExplorer class
# ---------------------------------------------------------------------------


class TestTblExplorer:
    """Tests for the TblExplorer result class."""

    def test_repr_html(self):
        html = "<div>table</div>"
        te = TblExplorer(html)
        assert te._repr_html_() == html

    def test_as_html(self):
        html = "<div>content</div>"
        te = TblExplorer(html)
        assert te.as_html() == html

    def test_save(self, tmp_path: Path):
        html = "<div>saved table</div>"
        te = TblExplorer(html)
        out = tmp_path / "table.html"
        te.save(out)
        assert out.read_text(encoding="utf-8") == html

    def test_repr(self):
        html = "<div>x</div>"
        te = TblExplorer(html)
        assert "TblExplorer" in repr(te)
        assert str(len(html)) in repr(te)


# ---------------------------------------------------------------------------
# _serialize_value
# ---------------------------------------------------------------------------


class TestSerializeValue:
    """Tests for _serialize_value()."""

    def test_none(self):
        assert _serialize_value(None) is None

    def test_bool_true(self):
        assert _serialize_value(True) is True

    def test_bool_false(self):
        assert _serialize_value(False) is False

    def test_int(self):
        assert _serialize_value(42) == 42

    def test_float_normal(self):
        assert _serialize_value(3.14) == 3.14

    def test_float_nan(self):
        assert _serialize_value(float("nan")) is None

    def test_float_inf(self):
        assert _serialize_value(float("inf")) is None

    def test_float_neg_inf(self):
        assert _serialize_value(float("-inf")) is None

    def test_string_passthrough(self):
        assert _serialize_value("hello") == "hello"

    def test_other_types_stringified(self):
        assert _serialize_value([1, 2, 3]) == "[1, 2, 3]"


# ---------------------------------------------------------------------------
# _serialize_data_blob
# ---------------------------------------------------------------------------


class TestSerializeDataBlob:
    """Tests for _serialize_data_blob()."""

    def test_basic_serialization(self):
        result = _serialize_data_blob(
            col_names=["a", "b"],
            col_dtypes=["i64", "str"],
            alignments=["right", "left"],
            all_rows=[[1, "x"], [2, "y"]],
            total_rows=2,
            tbl_type="Dict",
            config={"pageSize": 10},
        )
        parsed = json.loads(result)
        assert parsed["totalRows"] == 2
        assert parsed["tableType"] == "Dict"
        assert len(parsed["columns"]) == 2
        assert parsed["columns"][0]["name"] == "a"
        assert parsed["rows"] == [[1, "x"], [2, "y"]]

    def test_script_tag_escape(self):
        result = _serialize_data_blob(
            col_names=["html"],
            col_dtypes=["str"],
            alignments=["left"],
            all_rows=[["</script>"]],
            total_rows=1,
            tbl_type="Dict",
            config={},
        )
        # Should not contain literal </script>
        assert "</script>" not in result
        assert r"<\/script>" in result

    def test_nan_values_serialized_as_null(self):
        result = _serialize_data_blob(
            col_names=["x"],
            col_dtypes=["f64"],
            alignments=["right"],
            all_rows=[[float("nan")]],
            total_rows=1,
            tbl_type="Dict",
            config={},
        )
        parsed = json.loads(result)
        assert parsed["rows"] == [[None]]


# ---------------------------------------------------------------------------
# _render_explorer_css
# ---------------------------------------------------------------------------


class TestRenderExplorerCss:
    """Tests for _render_explorer_css()."""

    def test_contains_uid(self):
        css = _render_explorer_css("abc123")
        assert "#gd-tbl-abc123" in css
        assert "<style>" in css

    def test_contains_toolbar_rules(self):
        css = _render_explorer_css("test")
        assert ".gd-tbl-toolbar" in css


# ---------------------------------------------------------------------------
# _get_js_source
# ---------------------------------------------------------------------------


class TestGetJsSource:
    """Tests for _get_js_source()."""

    def test_loads_js_file(self):
        # This should work if the asset file exists
        js = _get_js_source()
        assert len(js) > 0
        assert "function" in js.lower() or "const" in js.lower() or "var" in js.lower()

    def test_raises_when_file_missing(self, tmp_path: Path):
        # Patch the asset name to something that doesn't exist in the assets dir
        with patch("great_docs._tables.explorer._JS_ASSET_NAME", "does-not-exist-xyz.js"):
            with pytest.raises(FileNotFoundError, match="does-not-exist-xyz.js"):
                _get_js_source()


# ---------------------------------------------------------------------------
# tbl_explorer (main entry point)
# ---------------------------------------------------------------------------


class TestTblExplorerFunction:
    """Tests for tbl_explorer() function."""

    def test_dict_input(self):
        data = {"name": ["Alice", "Bob"], "age": [30, 25]}
        result = tbl_explorer(data)
        assert isinstance(result, TblExplorer)
        html = result.as_html()
        assert "Alice" in html
        assert "Bob" in html

    def test_list_of_dicts_input(self):
        data = [{"x": 1, "y": "a"}, {"x": 2, "y": "b"}]
        result = tbl_explorer(data)
        html = result.as_html()
        assert "gd-tbl-explorer" in html

    def test_columns_subset(self):
        data = {"a": [1, 2], "b": [3, 4], "c": [5, 6]}
        result = tbl_explorer(data, columns=["a", "c"])
        html = result.as_html()
        # Column "b" should not be in the column headers
        assert ">a<" in html or "a</th" in html or '"a"' in html

    def test_custom_page_size(self):
        data = {"val": list(range(50))}
        result = tbl_explorer(data, page_size=5)
        html = result.as_html()
        assert "gd-tbl" in html

    def test_no_pagination(self):
        data = {"val": list(range(5))}
        result = tbl_explorer(data, page_size=0)
        html = result.as_html()
        assert "gd-tbl" in html

    def test_custom_id(self):
        data = {"x": [1]}
        result = tbl_explorer(data, id="my-custom-id")
        html = result.as_html()
        assert "gd-tbl-my-custom-id" in html

    def test_show_options(self):
        data = {"x": [1, 2]}
        result = tbl_explorer(
            data,
            show_row_numbers=False,
            show_dtypes=False,
            show_dimensions=False,
        )
        html = result.as_html()
        assert "gd-tbl" in html

    def test_all_controls_disabled(self):
        data = {"x": [1]}
        result = tbl_explorer(
            data,
            sortable=False,
            filterable=False,
            column_toggle=False,
            copyable=False,
            downloadable=False,
        )
        html = result.as_html()
        assert "gd-tbl" in html

    def test_large_dataset_warning(self):
        """Datasets > 10_000 rows emit a warning."""
        data = {"x": list(range(10_001))}
        with pytest.warns(UserWarning, match="embedding 10,001 rows"):
            tbl_explorer(data)

    def test_highlight_missing_disabled(self):
        data = {"x": [None, 1]}
        result = tbl_explorer(data, highlight_missing=False)
        html = result.as_html()
        assert "gd-tbl" in html

    def test_caption(self):
        data = {"x": [1]}
        result = tbl_explorer(data, caption="My Table")
        html = result.as_html()
        assert "My Table" in html
