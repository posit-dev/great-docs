"""Tests for annotation formatting."""

import pytest

from great_docs._qrenderer._format import render_formatted_expr


class TestRenderFormattedExpr:
    """Verify render_formatted_expr produces plain text (no links)."""

    def _make_expr(self, code: str) -> "gf.Expr":
        """Create a griffe Expr from a type annotation string."""
        import griffe as gf

        with gf.temporary_visited_package(
            "pkg", {"__init__.py": f"x: {code}"}, docstring_parser="numpy"
        ) as m:
            return m["x"].annotation

    def test_no_links_in_long_annotation(self):
        """Long annotations must not contain InterLink markdown."""
        # Build a union type long enough to trigger ruff formatting (>79 chars)
        expr = self._make_expr("SomeVeryLongClassName | another_module.AnotherLongClass | None")
        result = render_formatted_expr(expr)

        # No markdown link syntax should appear
        assert "](" not in result
        assert "][" not in result

    def test_preserves_annotation_text(self):
        """The formatted output should contain the original type names."""
        expr = self._make_expr("dict[str, int] | None")
        result = render_formatted_expr(expr)

        assert "dict" in result
        assert "str" in result
        assert "int" in result
        assert "None" in result

    def test_whitespace_encoded(self):
        """Spaces and newlines should be encoded for HTML inline display."""
        from great_docs._qrenderer._format import pretty_code

        # pretty_code converts 4-space indents to &nbsp; and newlines to <br>
        result = pretty_code("(\n    Foo\n    | Bar\n)")

        assert "&nbsp;" in result
        assert "<br>" in result


class TestCSSAnnotationHeight:
    """Verify the CSS source uses min-height for dt elements."""

    @pytest.fixture()
    def css_source(self):
        from pathlib import Path

        css_path = (
            Path(__file__).resolve().parents[2] / "great_docs" / "assets" / "great-docs-q.scss"
        )
        return css_path.read_text()

    def test_dt_uses_min_height(self, css_source):
        assert "min-height: 32px" in css_source

    def test_dt_no_fixed_height(self, css_source):
        # Ensure we didn't accidentally leave a fixed height
        # Match "height: 32px" that is NOT preceded by "min-"
        lines = css_source.splitlines()
        for line in lines:
            stripped = line.strip()
            if stripped == "height: 32px;":
                # Check it's inside a dt block
                pytest.fail("Found fixed 'height: 32px' in CSS — should be 'min-height'")
