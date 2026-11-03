# pyright: reportPrivateUsage=false

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from great_docs._tables.display import (
    _get_ipython,
    disable_tbl_preview,
    enable_tbl_preview,
)


# ---------------------------------------------------------------------------
# _get_ipython
# ---------------------------------------------------------------------------


class TestGetIpython:
    """Tests for _get_ipython() helper."""

    def test_raises_when_ipython_not_installed(self):
        with patch.dict("sys.modules", {"IPython": None}):
            with pytest.raises(RuntimeError, match="IPython is not installed"):
                _get_ipython()

    def test_raises_when_no_active_session(self):
        mock_mod = MagicMock()
        mock_mod.get_ipython.return_value = None
        with patch.dict("sys.modules", {"IPython": mock_mod}):
            with pytest.raises(RuntimeError, match="No active IPython session"):
                _get_ipython()

    def test_returns_ipython_instance(self):
        mock_ip = MagicMock()
        mock_mod = MagicMock()
        mock_mod.get_ipython.return_value = mock_ip
        with patch.dict("sys.modules", {"IPython": mock_mod}):
            result = _get_ipython()
        assert result is mock_ip


# ---------------------------------------------------------------------------
# enable_tbl_preview
# ---------------------------------------------------------------------------


class TestEnableTblPreview:
    """Tests for enable_tbl_preview()."""

    def test_returns_none_when_no_ipython(self):
        with patch(
            "great_docs._tables.display._get_ipython",
            side_effect=RuntimeError("No active IPython session."),
        ):
            result = enable_tbl_preview()
        assert result is None

    def test_registers_polars_formatter(self):
        mock_ip = MagicMock()
        html_formatter = MagicMock()
        mock_ip.display_formatter.formatters = {"text/html": html_formatter}

        # Mock polars available, pandas not
        mock_pl = MagicMock()
        mock_pl.DataFrame = type("PolarsDF", (), {})

        with (
            patch("great_docs._tables.display._get_ipython", return_value=mock_ip),
            patch.dict("sys.modules", {"polars": mock_pl}),
            patch("builtins.__import__", side_effect=_selective_import({"polars": mock_pl})),
        ):
            enable_tbl_preview(n_head=5)

        # for_type should have been called for polars DataFrame
        html_formatter.for_type.assert_called()

    def test_formatter_closure_polars_branch(self):
        """_tbl_preview_formatter returns HTML for recognized DataFrames."""
        mock_ip = MagicMock()
        html_formatter = MagicMock()
        mock_ip.display_formatter.formatters = {"text/html": html_formatter}

        mock_pl = MagicMock()
        mock_pl.DataFrame = type("PolarsDF", (), {})
        mock_df = mock_pl.DataFrame()

        captured = {}

        def _capture_for_type(dtype, fn):
            captured[dtype] = fn

        html_formatter.for_type.side_effect = _capture_for_type

        mock_preview = MagicMock()
        mock_preview.as_html.return_value = "<table>polars</table>"

        with (
            patch("great_docs._tables.display._get_ipython", return_value=mock_ip),
            patch("builtins.__import__", side_effect=_selective_import({"polars": mock_pl})),
            patch("great_docs._tables.preview._is_polars", return_value=True),
            patch("great_docs._tables.preview._is_pandas", return_value=False),
            patch("great_docs._tables.preview.tbl_preview", return_value=mock_preview),
        ):
            enable_tbl_preview()

        # Call the registered formatter with the mock DataFrame
        assert captured, "for_type was never called"
        formatter_fn = next(iter(captured.values()))
        result = formatter_fn(mock_df)
        assert result == "<table>polars</table>"

    def test_formatter_closure_non_dataframe_returns_none(self):
        """_tbl_preview_formatter returns None for unrecognized objects."""
        mock_ip = MagicMock()
        html_formatter = MagicMock()
        mock_ip.display_formatter.formatters = {"text/html": html_formatter}

        mock_pl = MagicMock()
        mock_pl.DataFrame = type("PolarsDF", (), {})

        captured = {}

        def _capture_for_type(dtype, fn):
            captured[dtype] = fn

        html_formatter.for_type.side_effect = _capture_for_type

        with (
            patch("great_docs._tables.display._get_ipython", return_value=mock_ip),
            patch("builtins.__import__", side_effect=_selective_import({"polars": mock_pl})),
            patch("great_docs._tables.preview._is_polars", return_value=False),
            patch("great_docs._tables.preview._is_pandas", return_value=False),
        ):
            enable_tbl_preview()

        assert captured, "for_type was never called"
        formatter_fn = next(iter(captured.values()))
        result = formatter_fn("not a dataframe")
        assert result is None

    def test_registers_pandas_formatter(self):
        mock_ip = MagicMock()
        html_formatter = MagicMock()
        mock_ip.display_formatter.formatters = {"text/html": html_formatter}

        mock_pd = MagicMock()
        mock_pd.DataFrame = type("PandasDF", (), {})

        with (
            patch("great_docs._tables.display._get_ipython", return_value=mock_ip),
            patch("builtins.__import__", side_effect=_selective_import({"pandas": mock_pd})),
        ):
            enable_tbl_preview()

        html_formatter.for_type.assert_called()

    def test_handles_import_errors_gracefully(self):
        """If neither polars nor pandas is available, no error is raised."""
        mock_ip = MagicMock()
        html_formatter = MagicMock()
        mock_ip.display_formatter.formatters = {"text/html": html_formatter}

        def _raise_import(name, *args, **kwargs):
            if name in ("polars", "pandas"):
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *args, **kwargs)

        import builtins

        original_import = builtins.__import__

        with (
            patch("great_docs._tables.display._get_ipython", return_value=mock_ip),
            patch("builtins.__import__", side_effect=_raise_import),
        ):
            enable_tbl_preview()

        # No calls to for_type since neither lib is available
        html_formatter.for_type.assert_not_called()


# ---------------------------------------------------------------------------
# disable_tbl_preview
# ---------------------------------------------------------------------------


class TestDisableTblPreview:
    """Tests for disable_tbl_preview()."""

    def test_returns_none_when_no_ipython(self):
        with patch(
            "great_docs._tables.display._get_ipython",
            side_effect=RuntimeError("No active IPython session."),
        ):
            result = disable_tbl_preview()
        assert result is None

    def test_pops_polars_formatter(self):
        mock_ip = MagicMock()
        html_formatter = MagicMock()
        mock_ip.display_formatter.formatters = {"text/html": html_formatter}

        mock_pl = MagicMock()
        mock_pl.DataFrame = type("PolarsDF", (), {})

        with (
            patch("great_docs._tables.display._get_ipython", return_value=mock_ip),
            patch("builtins.__import__", side_effect=_selective_import({"polars": mock_pl})),
        ):
            disable_tbl_preview()

        html_formatter.pop.assert_called()

    def test_pops_pandas_formatter(self):
        mock_ip = MagicMock()
        html_formatter = MagicMock()
        mock_ip.display_formatter.formatters = {"text/html": html_formatter}

        mock_pd = MagicMock()
        mock_pd.DataFrame = type("PandasDF", (), {})

        with (
            patch("great_docs._tables.display._get_ipython", return_value=mock_ip),
            patch("builtins.__import__", side_effect=_selective_import({"pandas": mock_pd})),
        ):
            disable_tbl_preview()

        html_formatter.pop.assert_called()

    def test_handles_import_errors_gracefully(self):
        mock_ip = MagicMock()
        html_formatter = MagicMock()
        mock_ip.display_formatter.formatters = {"text/html": html_formatter}

        def _raise_import(name, *args, **kwargs):
            if name in ("polars", "pandas"):
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *args, **kwargs)

        import builtins

        original_import = builtins.__import__

        with (
            patch("great_docs._tables.display._get_ipython", return_value=mock_ip),
            patch("builtins.__import__", side_effect=_raise_import),
        ):
            disable_tbl_preview()

        html_formatter.pop.assert_not_called()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _selective_import(available: dict):
    """Create a side_effect function for __import__ that provides specific modules."""
    import builtins

    original_import = builtins.__import__

    def _import(name, *args, **kwargs):
        if name in available:
            return available[name]
        if name in ("polars", "pandas") and name not in available:
            raise ImportError(f"No module named '{name}'")
        return original_import(name, *args, **kwargs)

    return _import
