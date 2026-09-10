from __future__ import annotations

import json
import textwrap
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from great_docs._check_examples import (
    Cell,
    CellError,
    CheckResult,
    PageResult,
    _build_docstring_qmd,
    _check_quarto_available,
    _collect_object_names,
    _detect_package,
    _dict_to_page_result,
    _page_opted_out,
    _parse_errors_from_html,
    _prepare_qmd_for_check,
    _render_page_with_quarto,
    _resolve_member,
    _run_page,
    check_examples,
    discover_qmd_files,
    extract_cells,
    extract_docstring_examples,
    format_console,
    format_json,
    write_log_file,
)
from great_docs.cli import cli

requires_quarto = pytest.mark.skipif(
    _check_quarto_available() is not None,
    reason="Quarto is not installed",
)


# ===================================================================
# extract_cells — basic parsing
# ===================================================================


class TestExtractCells:
    def test_single_cell(self):
        qmd = "```{python}\nx = 1\n```\n"
        cells = extract_cells(qmd)
        assert len(cells) == 1
        assert cells[0].index == 0
        assert cells[0].source == "x = 1"

    def test_multiple_cells(self):
        qmd = "```{python}\nx = 1\n```\n\n```{python}\ny = 2\n```\n"
        cells = extract_cells(qmd)
        assert len(cells) == 2
        assert cells[0].source == "x = 1"
        assert cells[1].source == "y = 2"

    def test_eval_false_skipped(self):
        qmd = "```{python}\n#| eval: false\nx = 1\n```\n"
        cells = extract_cells(qmd)
        assert len(cells) == 0

    def test_check_false_skipped(self):
        qmd = "```{python}\n#| check: false\nx = 1\n```\n"
        cells = extract_cells(qmd)
        assert len(cells) == 0

    def test_non_python_blocks_ignored(self):
        qmd = "```r\nlibrary(dplyr)\n```\n\n```{python}\nx = 1\n```\n"
        cells = extract_cells(qmd)
        assert len(cells) == 1

    def test_plain_fenced_block_ignored(self):
        qmd = "```python\nx = 1\n```\n"
        cells = extract_cells(qmd)
        assert len(cells) == 0

    def test_empty_cell_skipped(self):
        qmd = "```{python}\n\n```\n"
        cells = extract_cells(qmd)
        assert len(cells) == 0

    def test_options_preserved(self):
        qmd = "```{python}\n#| echo: false\n#| output: asis\nx = 1\n```\n"
        cells = extract_cells(qmd)
        assert cells[0].options == {"echo": "false", "output": "asis"}

    def test_options_stripped_from_source(self):
        qmd = "```{python}\n#| echo: false\nx = 1\n```\n"
        cells = extract_cells(qmd)
        assert cells[0].source == "x = 1"

    def test_multiline_cell(self):
        qmd = "```{python}\nx = 1\ny = 2\nz = x + y\n```\n"
        cells = extract_cells(qmd)
        assert cells[0].source == "x = 1\ny = 2\nz = x + y"


# ===================================================================
# extract_cells — option handling
# ===================================================================


class TestExtractCellsOptions:
    def test_eval_no_skipped(self):
        qmd = "```{python}\n#| eval: no\nx = 1\n```\n"
        assert len(extract_cells(qmd)) == 0

    def test_eval_true_kept(self):
        qmd = "```{python}\n#| eval: true\nx = 1\n```\n"
        cells = extract_cells(qmd)
        assert len(cells) == 1

    def test_check_no_skipped(self):
        qmd = "```{python}\n#| check: no\nx = 1\n```\n"
        assert len(extract_cells(qmd)) == 0

    def test_other_options_preserved(self):
        qmd = "```{python}\n#| echo: false\n#| fig-width: 8\nx = 1\n```\n"
        cells = extract_cells(qmd)
        assert cells[0].options == {"echo": "false", "fig-width": "8"}

    def test_cell_index_increments_past_skipped(self):
        qmd = "```{python}\nx = 1\n```\n\n```{python}\n#| eval: false\nskip\n```\n\n```{python}\ny = 2\n```\n"
        cells = extract_cells(qmd)
        assert cells[0].index == 0
        assert cells[1].index == 2

    def test_error_true_option_preserved(self):
        qmd = "```{python}\n#| error: true\nraise ValueError('expected')\n```\n"
        cells = extract_cells(qmd)
        assert len(cells) == 1
        assert cells[0].options.get("error") == "true"

    def test_eval_false_case_insensitive(self):
        for val in ("false", "False", "FALSE"):
            qmd = f"```{{python}}\n#| eval: {val}\nx = 1\n```\n"
            assert len(extract_cells(qmd)) == 0

    def test_check_false_case_insensitive(self):
        for val in ("false", "False", "FALSE"):
            qmd = f"```{{python}}\n#| check: {val}\nx = 1\n```\n"
            assert len(extract_cells(qmd)) == 0

    def test_multiple_options_all_parsed(self):
        qmd = "```{python}\n#| echo: false\n#| output: asis\n#| fig-width: 8\nx = 1\n```\n"
        cells = extract_cells(qmd)
        assert len(cells[0].options) == 3

    def test_options_only_at_top_of_cell(self):
        qmd = "```{python}\nx = 1\n#| echo: false\ny = 2\n```\n"
        cells = extract_cells(qmd)
        assert "#| echo: false" in cells[0].source
        assert cells[0].options == {}


# ===================================================================
# _page_opted_out
# ===================================================================


class TestPageOptedOut:
    def test_opted_out_false(self):
        assert _page_opted_out("---\ncheck-examples: false\n---\nContent") is True

    def test_opted_out_no(self):
        assert _page_opted_out("---\ncheck-examples: no\n---\nContent") is True

    def test_opted_out_off(self):
        assert _page_opted_out("---\ncheck-examples: off\n---\nContent") is True

    def test_not_opted_out(self):
        assert _page_opted_out("---\ntitle: Test\n---\nContent") is False

    def test_opted_out_true(self):
        assert _page_opted_out("---\ncheck-examples: true\n---\nContent") is False

    def test_no_frontmatter(self):
        assert _page_opted_out("No frontmatter here") is False

    def test_empty_frontmatter(self):
        assert _page_opted_out("---\n---\nContent") is False

    def test_case_insensitive(self):
        assert _page_opted_out("---\ncheck-examples: False\n---\nContent") is True
        assert _page_opted_out("---\ncheck-examples: FALSE\n---\nContent") is True

    def test_other_keys_ignored(self):
        assert _page_opted_out("---\nother-key: false\n---\nContent") is False

    def test_with_other_frontmatter_keys(self):
        text = "---\ntitle: Test\ncheck-examples: false\nauthor: Me\n---\nContent"
        assert _page_opted_out(text) is True


# ===================================================================
# Cell selection — integration tests
# ===================================================================


class TestCellSelection:
    """Verify that complex documents produce exactly the right set of cells
    with correct indices and source code."""

    def test_complex_document_selects_correct_cells(self):
        qmd = textwrap.dedent("""\
            ---
            title: "Complex page"
            ---

            Intro paragraph.

            ```{python}
            import pandas as pd
            ```

            Some explanation.

            ```{python}
            #| eval: false
            pd.show_versions()
            ```

            ```r
            library(dplyr)
            ```

            ```{python}
            #| echo: false
            df = pd.DataFrame({"a": [1, 2, 3]})
            ```

            ```{python}
            #| check: false
            # this cell is opt-ed out of checking
            dangerous_call()
            ```

            ```python
            # plain fenced block, not executable
            x = "decorative"
            ```

            ```{python}

            ```

            ```{python}
            result = df.sum()
            ```
        """)
        cells = extract_cells(qmd)
        assert len(cells) == 3
        assert cells[0].index == 0
        assert cells[0].source == "import pandas as pd"
        assert cells[0].options == {}
        assert cells[1].index == 2
        assert cells[1].source == 'df = pd.DataFrame({"a": [1, 2, 3]})'
        assert cells[1].options == {"echo": "false"}
        assert cells[2].index == 5
        assert cells[2].source == "result = df.sum()"

    def test_indices_are_absolute_cell_positions(self):
        qmd = textwrap.dedent("""\
            ```{python}
            a = 1
            ```

            ```{python}
            #| eval: false
            skipped
            ```

            ```{python}
            #| eval: false
            also_skipped
            ```

            ```{python}
            b = 2
            ```

            ```{python}
            #| check: false
            nope
            ```

            ```{python}
            c = 3
            ```
        """)
        cells = extract_cells(qmd)
        assert [(c.index, c.source) for c in cells] == [
            (0, "a = 1"),
            (3, "b = 2"),
            (5, "c = 3"),
        ]

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto")
    def test_quarto_receives_only_eligible_cells(self, mock_render, mock_quarto, tmp_path):
        mock_render.return_value = PageResult("page.qmd", "pass", cells_checked=3)
        page = tmp_path / "page.qmd"
        page.write_text(textwrap.dedent("""\
            ```{python}
            first = 1
            ```

            ```{python}
            #| eval: false
            display_only = True
            ```

            ```{python}
            #| check: false
            opt_out = True
            ```

            ```{python}
            second = 2
            ```

            ```{python}
            third = 3
            ```
        """))
        check_examples(tmp_path, no_docstrings=True)
        assert mock_render.call_count == 1
        cells_sent = mock_render.call_args[0][2]
        assert len(cells_sent) == 3
        assert cells_sent[0].source == "first = 1"
        assert cells_sent[0].index == 0
        assert cells_sent[1].source == "second = 2"
        assert cells_sent[1].index == 3
        assert cells_sent[2].source == "third = 3"
        assert cells_sent[2].index == 4

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto")
    def test_multiple_pages_get_correct_cells(self, mock_render, mock_quarto, tmp_path):
        mock_render.return_value = PageResult("", "pass", cells_checked=1)
        (tmp_path / "a.qmd").write_text(textwrap.dedent("""\
            ```{python}
            x_from_a = 10
            ```
        """))
        (tmp_path / "b.qmd").write_text(textwrap.dedent("""\
            ```{python}
            y_from_b = 20
            ```

            ```{python}
            z_from_b = 30
            ```
        """))
        check_examples(tmp_path, no_docstrings=True)
        assert mock_render.call_count == 2
        first_call_cells = mock_render.call_args_list[0][0][2]
        second_call_cells = mock_render.call_args_list[1][0][2]
        assert len(first_call_cells) == 1
        assert first_call_cells[0].source == "x_from_a = 10"
        assert len(second_call_cells) == 2
        assert second_call_cells[0].source == "y_from_b = 20"
        assert second_call_cells[1].source == "z_from_b = 30"

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto")
    def test_opted_out_page_sends_no_cells(self, mock_render, mock_quarto, tmp_path):
        mock_render.return_value = PageResult("run.qmd", "pass", cells_checked=1)
        (tmp_path / "skip.qmd").write_text(textwrap.dedent("""\
            ---
            check-examples: false
            ---

            ```{python}
            x = 1
            ```

            ```{python}
            y = 2
            ```
        """))
        (tmp_path / "run.qmd").write_text("```{python}\nz = 3\n```\n")
        check_examples(tmp_path, no_docstrings=True)
        assert mock_render.call_count == 1
        cells_sent = mock_render.call_args[0][2]
        assert len(cells_sent) == 1
        assert cells_sent[0].source == "z = 3"

    @requires_quarto
    def test_cell_selection_e2e(self, tmp_path):
        (tmp_path / "page.qmd").write_text(textwrap.dedent("""\
            ```{python}
            executed_cells = []
            ```

            ```{python}
            executed_cells.append("cell_1")
            ```

            ```{python}
            #| eval: false
            executed_cells.append("should_not_appear")
            ```

            ```{python}
            #| check: false
            executed_cells.append("also_should_not_appear")
            ```

            ```{python}
            executed_cells.append("cell_4")
            assert executed_cells == ["cell_1", "cell_4"]
            ```
        """))
        result = check_examples(tmp_path, no_docstrings=True)
        assert result.cells_failed == 0
        assert result.cells_checked == 3

    def test_hashpipe_options_do_not_appear_in_source(self):
        qmd = textwrap.dedent("""\
            ```{python}
            #| echo: false
            #| output: asis
            #| fig-width: 8
            actual_code = True
            more_code = False
            ```
        """)
        cells = extract_cells(qmd)
        assert len(cells) == 1
        assert "#|" not in cells[0].source
        assert cells[0].source == "actual_code = True\nmore_code = False"
        assert cells[0].options == {"echo": "false", "output": "asis", "fig-width": "8"}


# ===================================================================
# discover_qmd_files
# ===================================================================


class TestDiscoverQmdFiles:
    def test_finds_qmd_files(self, tmp_path):
        (tmp_path / "a.qmd").write_text("")
        (tmp_path / "b.qmd").write_text("")
        files = discover_qmd_files(tmp_path)
        assert len(files) == 2

    def test_ignores_non_qmd(self, tmp_path):
        (tmp_path / "a.qmd").write_text("")
        (tmp_path / "b.py").write_text("")
        files = discover_qmd_files(tmp_path)
        assert len(files) == 1

    def test_excludes_build_dir(self, tmp_path):
        (tmp_path / "great-docs").mkdir()
        (tmp_path / "great-docs" / "built.qmd").write_text("")
        (tmp_path / "real.qmd").write_text("")
        files = discover_qmd_files(tmp_path)
        assert len(files) == 1

    def test_excludes_hidden_dirs(self, tmp_path):
        (tmp_path / ".hidden").mkdir()
        (tmp_path / ".hidden" / "secret.qmd").write_text("")
        (tmp_path / "real.qmd").write_text("")
        files = discover_qmd_files(tmp_path)
        assert len(files) == 1

    def test_path_targeting_file(self, tmp_path):
        (tmp_path / "a.qmd").write_text("")
        (tmp_path / "b.qmd").write_text("")
        files = discover_qmd_files(tmp_path, paths=("a.qmd",))
        assert len(files) == 1

    def test_path_targeting_directory(self, tmp_path):
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "c.qmd").write_text("")
        (tmp_path / "other.qmd").write_text("")
        files = discover_qmd_files(tmp_path, paths=("sub",))
        assert len(files) == 1

    def test_include_filter(self, tmp_path):
        (tmp_path / "guide").mkdir()
        (tmp_path / "guide" / "intro.qmd").write_text("")
        (tmp_path / "other.qmd").write_text("")
        files = discover_qmd_files(tmp_path, include="guide/*")
        assert len(files) == 1

    def test_exclude_filter(self, tmp_path):
        (tmp_path / "draft").mkdir()
        (tmp_path / "draft" / "wip.qmd").write_text("")
        (tmp_path / "good.qmd").write_text("")
        files = discover_qmd_files(tmp_path, exclude="draft/*")
        assert len(files) == 1

    def test_recursive(self, tmp_path):
        (tmp_path / "a" / "b").mkdir(parents=True)
        (tmp_path / "a" / "b" / "deep.qmd").write_text("")
        files = discover_qmd_files(tmp_path)
        assert len(files) == 1

    def test_sorted_output(self, tmp_path):
        for name in ["c.qmd", "a.qmd", "b.qmd"]:
            (tmp_path / name).write_text("")
        files = discover_qmd_files(tmp_path)
        names = [f.name for f in files]
        assert names == sorted(names)


# ===================================================================
# _collect_object_names
# ===================================================================


class TestCollectObjectNames:
    def test_string_items(self):
        sections = [{"contents": ["Foo", "Bar"]}]
        assert _collect_object_names(sections) == ["Foo", "Bar"]

    def test_dict_with_name(self):
        sections = [{"contents": [{"name": "Baz"}]}]
        assert _collect_object_names(sections) == ["Baz"]

    def test_nested_contents(self):
        sections = [{"contents": [{"contents": [{"name": "Inner"}]}]}]
        assert _collect_object_names(sections) == ["Inner"]

    def test_mixed(self):
        sections = [{"contents": ["Str", {"name": "Dict"}, {"contents": [{"name": "Nested"}]}]}]
        assert _collect_object_names(sections) == ["Str", "Dict", "Nested"]

    def test_empty_sections(self):
        assert _collect_object_names([]) == []

    def test_empty_contents(self):
        assert _collect_object_names([{"contents": []}]) == []


# ===================================================================
# _resolve_member
# ===================================================================


class TestResolveMember:
    def test_simple_member(self):
        pkg = MagicMock()
        pkg.members = {"Foo": MagicMock()}
        result = _resolve_member(pkg, "Foo")
        assert result is pkg.members["Foo"]

    def test_dotted_member(self):
        inner = MagicMock()
        outer = MagicMock()
        outer.members = {"Foo": inner}
        inner.members = {"bar": MagicMock()}
        result = _resolve_member(outer, "Foo.bar")
        assert result is inner.members["bar"]

    def test_not_found(self):
        pkg = MagicMock()
        pkg.members = {}
        assert _resolve_member(pkg, "Missing") is None

    def test_partial_path(self):
        pkg = MagicMock()
        child = MagicMock()
        child.members = {}
        pkg.members = {"A": child}
        assert _resolve_member(pkg, "A.B") is None

    def test_no_members_attr(self):
        pkg = "not an object with members"
        assert _resolve_member(pkg, "anything") is None


# ===================================================================
# _detect_package
# ===================================================================


class TestDetectPackage:
    def test_with_pyproject(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "my-package"\n')
        assert _detect_package(tmp_path) == "my_package"

    def test_without_pyproject(self, tmp_path):
        assert _detect_package(tmp_path) is None

    def test_hyphen_to_underscore(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "great-tables"\n')
        assert _detect_package(tmp_path) == "great_tables"

    def test_no_project_section(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 88\n")
        assert _detect_package(tmp_path) is None


# ===================================================================
# Quarto availability check
# ===================================================================


class TestCheckQuartoAvailable:
    @requires_quarto
    def test_quarto_available(self):
        err = _check_quarto_available()
        assert err is None

    def test_quarto_not_on_path(self):
        with patch("great_docs._check_examples.shutil.which", return_value=None):
            err = _check_quarto_available()
        assert err is not None
        assert "not installed" in err.lower() or "not on path" in err.lower()

    def test_quarto_version_fails(self):
        with patch("great_docs._check_examples.shutil.which", return_value="/usr/bin/quarto"):
            with patch("great_docs._check_examples.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stderr="bad")
                err = _check_quarto_available()
        assert err is not None
        assert "failed" in err.lower()


# ===================================================================
# _prepare_qmd_for_check
# ===================================================================


class TestPrepareQmdForCheck:
    def test_no_frontmatter_adds_execute_block(self):
        text = "Some content\n\n```{python}\nx = 1\n```\n"
        result = _prepare_qmd_for_check(text, 30)
        assert "execute:" in result
        assert "error: true" in result
        assert "timeout: 30" in result
        assert result.startswith("---\n")

    def test_existing_frontmatter_without_execute(self):
        text = "---\ntitle: Test\n---\n\n```{python}\nx = 1\n```\n"
        result = _prepare_qmd_for_check(text, 30)
        assert "title: Test" in result
        assert "error: true" in result
        assert "timeout: 30" in result

    def test_existing_frontmatter_with_execute(self):
        text = "---\ntitle: Test\nexecute:\n  freeze: true\n  echo: false\n---\n\nContent\n"
        result = _prepare_qmd_for_check(text, 45)
        assert "error: true" in result
        assert "timeout: 45" in result
        assert "echo: false" in result

    def test_check_false_rewritten_to_eval_false(self):
        text = "```{python}\n#| check: false\nraise ValueError\n```\n"
        result = _prepare_qmd_for_check(text, 30)
        assert "#| eval: false" in result
        assert "#| check: false" not in result

    def test_check_false_case_insensitive(self):
        for val in ("false", "False", "FALSE", "no", "No"):
            text = f"```{{python}}\n#| check: {val}\nx = 1\n```\n"
            result = _prepare_qmd_for_check(text, 30)
            assert "#| eval: false" in result

    def test_preserves_other_hashpipes(self):
        text = "```{python}\n#| echo: false\n#| fig-width: 8\nx = 1\n```\n"
        result = _prepare_qmd_for_check(text, 30)
        assert "#| echo: false" in result
        assert "#| fig-width: 8" in result

    def test_custom_timeout(self):
        text = "Some content\n"
        result = _prepare_qmd_for_check(text, 120)
        assert "timeout: 120" in result

    def test_existing_execute_error_overwritten(self):
        text = "---\nexecute:\n  error: false\n---\nContent\n"
        result = _prepare_qmd_for_check(text, 30)
        assert "error: true" in result
        assert "error: false" not in result


# ===================================================================
# _parse_errors_from_html
# ===================================================================


class TestParseErrorsFromHtml:
    def _make_cell_html(self, source: str, error: str | None = None) -> str:
        src_html = f'<code class="sourceCode python">{source}</code>'
        cell = f'<div class="cell" data-execution_count="1">\n'
        cell += f'<div class="sourceCode cell-code"><pre class="sourceCode python">{src_html}</pre></div>\n'
        if error:
            cell += f'<div class="cell-output cell-output-error"><pre>{error}</pre></div>\n'
        cell += '</div>\n'
        return cell

    def test_no_errors(self):
        html = self._make_cell_html("x = 1")
        cells = [Cell(0, "x = 1")]
        errors = _parse_errors_from_html(html, cells)
        assert errors == []

    def test_single_error(self):
        html = self._make_cell_html(
            'raise ValueError("boom")',
            "ValueError: boom",
        )
        cells = [Cell(0, 'raise ValueError("boom")')]
        errors = _parse_errors_from_html(html, cells)
        assert len(errors) == 1
        assert errors[0].error_type == "ValueError"
        assert errors[0].error_message == "boom"
        assert errors[0].cell_index == 0

    def test_error_true_cell_ignored(self):
        html = self._make_cell_html("raise ValueError('ok')", "ValueError: ok")
        cells = [Cell(0, "raise ValueError('ok')", options={"error": "true"})]
        errors = _parse_errors_from_html(html, cells)
        assert errors == []

    def test_multiple_cells_mixed(self):
        html = (
            self._make_cell_html("x = 1")
            + self._make_cell_html("raise TypeError('bad')", "TypeError: bad")
            + self._make_cell_html("y = 2")
        )
        cells = [Cell(0, "x = 1"), Cell(1, "raise TypeError('bad')"), Cell(2, "y = 2")]
        errors = _parse_errors_from_html(html, cells)
        assert len(errors) == 1
        assert errors[0].error_type == "TypeError"
        assert errors[0].cell_index == 1

    def test_traceback_extracted(self):
        tb = "Traceback (most recent call last):\n  File ...\nValueError: test"
        html = self._make_cell_html("bad()", tb)
        cells = [Cell(0, "bad()")]
        errors = _parse_errors_from_html(html, cells)
        assert "Traceback" in errors[0].traceback

    def test_unmatched_source_gets_negative_index(self):
        html = self._make_cell_html("unknown_code()", "NameError: not found")
        cells = [Cell(0, "different_code()")]
        errors = _parse_errors_from_html(html, cells)
        assert len(errors) == 1
        assert errors[0].cell_index == -1


# ===================================================================
# _build_docstring_qmd
# ===================================================================


class TestBuildDocstringQmd:
    def test_basic_output(self):
        cells = [Cell(0, "x = 1"), Cell(1, "y = 2")]
        qmd = _build_docstring_qmd(cells)
        assert "error: true" in qmd
        assert "```{python}" in qmd
        assert "x = 1" in qmd
        assert "y = 2" in qmd

    def test_has_frontmatter(self):
        cells = [Cell(0, "x = 1")]
        qmd = _build_docstring_qmd(cells)
        assert qmd.startswith("---\n")
        assert "---" in qmd

    def test_empty_cells(self):
        qmd = _build_docstring_qmd([])
        assert "error: true" in qmd
        assert "```{python}" not in qmd


# ===================================================================
# _render_page_with_quarto (integration — needs real Quarto)
# ===================================================================


@requires_quarto
class TestRenderPageWithQuarto:
    def test_passing_page(self, tmp_path):
        qmd = tmp_path / "good.qmd"
        qmd.write_text("---\ntitle: Test\n---\n\n```{python}\nx = 1 + 2\n```\n")
        cells = [Cell(0, "x = 1 + 2")]
        result = _render_page_with_quarto(qmd, "good.qmd", cells, 30)
        assert result.status == "pass"
        assert result.cells_checked == 1
        assert result.errors == []

    def test_failing_page(self, tmp_path):
        qmd = tmp_path / "bad.qmd"
        qmd.write_text('```{python}\nraise ValueError("boom")\n```\n')
        cells = [Cell(0, 'raise ValueError("boom")')]
        result = _render_page_with_quarto(qmd, "bad.qmd", cells, 30)
        assert result.status == "fail"
        assert len(result.errors) == 1
        assert result.errors[0].error_type == "ValueError"

    def test_multiple_errors(self, tmp_path):
        qmd = tmp_path / "multi.qmd"
        qmd.write_text(
            '```{python}\nraise TypeError("first")\n```\n\n'
            '```{python}\nraise ValueError("second")\n```\n'
        )
        cells = [
            Cell(0, 'raise TypeError("first")'),
            Cell(1, 'raise ValueError("second")'),
        ]
        result = _render_page_with_quarto(qmd, "multi.qmd", cells, 30)
        assert result.status == "fail"
        assert len(result.errors) == 2

    def test_error_true_cell_not_reported(self, tmp_path):
        qmd = tmp_path / "expected.qmd"
        qmd.write_text(
            '```{python}\n#| error: true\nraise ValueError("expected")\n```\n\n'
            '```{python}\nx = 1\n```\n'
        )
        cells = extract_cells(qmd.read_text())
        result = _render_page_with_quarto(qmd, "expected.qmd", cells, 30)
        assert result.status == "pass"
        assert result.errors == []

    def test_sequential_state_shared(self, tmp_path):
        qmd = tmp_path / "state.qmd"
        qmd.write_text(
            "```{python}\nshared = 42\n```\n\n"
            "```{python}\nassert shared == 42\n```\n"
        )
        cells = [Cell(0, "shared = 42"), Cell(1, "assert shared == 42")]
        result = _render_page_with_quarto(qmd, "state.qmd", cells, 30)
        assert result.status == "pass"


# ===================================================================
# _run_page (subprocess entry point)
# ===================================================================


@requires_quarto
class TestRunPage:
    def test_passing_page(self, tmp_path):
        qmd = tmp_path / "test.qmd"
        qmd.write_text("```{python}\nx = 1\n```\n")
        cells = [Cell(0, "x = 1")]
        cells_json = json.dumps([asdict(c) for c in cells])
        result_json = _run_page("test.qmd", cells_json, 30, str(tmp_path))
        result = json.loads(result_json)
        assert result["status"] == "pass"
        assert result["cells_checked"] == 1

    def test_failing_page(self, tmp_path):
        qmd = tmp_path / "fail.qmd"
        qmd.write_text('```{python}\nraise ValueError("nope")\n```\n')
        cells = [Cell(0, 'raise ValueError("nope")')]
        cells_json = json.dumps([asdict(c) for c in cells])
        result_json = _run_page("fail.qmd", cells_json, 30, str(tmp_path))
        result = json.loads(result_json)
        assert result["status"] == "fail"
        assert len(result["errors"]) == 1

    def test_docstring_mode(self, tmp_path):
        cells = [Cell(0, "x = 1 + 2")]
        cells_json = json.dumps([asdict(c) for c in cells])
        result_json = _run_page(
            "docstring:pkg.Foo", cells_json, 30, str(tmp_path), is_docstring=True
        )
        result = json.loads(result_json)
        assert result["status"] == "pass"


# ===================================================================
# _dict_to_page_result
# ===================================================================


class TestDictToPageResult:
    def test_basic(self):
        d = {"path": "page.qmd", "status": "pass", "cells_checked": 2, "errors": []}
        result = _dict_to_page_result(d)
        assert result.path == "page.qmd"
        assert result.status == "pass"
        assert result.cells_checked == 2

    def test_with_errors(self):
        d = {
            "path": "fail.qmd",
            "status": "fail",
            "cells_checked": 1,
            "errors": [
                {
                    "cell_index": 0,
                    "source": "bad",
                    "error_type": "Err",
                    "error_message": "msg",
                    "traceback": "tb",
                }
            ],
        }
        result = _dict_to_page_result(d)
        assert len(result.errors) == 1
        assert result.errors[0].error_type == "Err"

    def test_with_message(self):
        d = {
            "path": "page.qmd",
            "status": "error",
            "cells_checked": 0,
            "errors": [],
            "message": "something broke",
        }
        result = _dict_to_page_result(d)
        assert result.message == "something broke"


# ===================================================================
# format_console
# ===================================================================


class TestFormatConsole:
    def test_passing_page(self):
        result = CheckResult(
            pages_checked=1,
            pages_passed=1,
            cells_checked=2,
            cells_passed=2,
            pages=[PageResult("page.qmd", "pass", cells_checked=2)],
        )
        output = format_console(result)
        assert "✓ page.qmd (2 cells)" in output
        assert "1 passed, 0 failed" in output

    def test_failing_page(self):
        result = CheckResult(
            pages_checked=1,
            pages_failed=1,
            cells_checked=1,
            cells_failed=1,
            pages=[
                PageResult(
                    "fail.qmd",
                    "fail",
                    cells_checked=1,
                    errors=[CellError(0, "bad()", "NameError", "bad not defined", "")],
                )
            ],
        )
        output = format_console(result)
        assert "✗ fail.qmd" in output
        assert "Cell 0:" in output
        assert "bad()" in output
        assert "NameError: bad not defined" in output

    def test_error_page(self):
        result = CheckResult(
            pages_checked=1,
            pages_failed=1,
            pages=[PageResult("crash.qmd", "error", message="render failed")],
        )
        output = format_console(result)
        assert "✗ crash.qmd" in output
        assert "render failed" in output

    def test_verbose_shows_traceback(self):
        result = CheckResult(
            pages=[
                PageResult(
                    "page.qmd",
                    "fail",
                    cells_checked=1,
                    errors=[CellError(0, "x", "E", "m", "line1\nline2")],
                )
            ],
        )
        output = format_console(result, verbose=True)
        assert "line1" in output
        assert "line2" in output

    def test_no_verbose_hides_traceback(self):
        result = CheckResult(
            pages=[
                PageResult(
                    "page.qmd",
                    "fail",
                    cells_checked=1,
                    errors=[CellError(0, "x", "E", "m", "line1\nline2")],
                )
            ],
        )
        output = format_console(result, verbose=False)
        assert "line1" not in output

    def test_long_source_truncated(self):
        long_source = "x" * 200
        result = CheckResult(
            pages=[
                PageResult(
                    "page.qmd",
                    "fail",
                    cells_checked=1,
                    errors=[CellError(0, long_source, "E", "m", "")],
                )
            ],
        )
        output = format_console(result)
        assert "..." in output


# ===================================================================
# format_json
# ===================================================================


class TestFormatJson:
    def test_structure(self):
        result = CheckResult(
            pages_checked=1,
            pages_passed=1,
            cells_checked=2,
            cells_passed=2,
            pages=[PageResult("page.qmd", "pass", cells_checked=2)],
        )
        data = json.loads(format_json(result))
        assert "summary" in data
        assert "pages" in data
        assert data["summary"]["pages_passed"] == 1

    def test_with_errors(self):
        result = CheckResult(
            pages_checked=1,
            pages_failed=1,
            cells_checked=1,
            cells_failed=1,
            pages=[
                PageResult(
                    "fail.qmd",
                    "fail",
                    cells_checked=1,
                    errors=[CellError(0, "bad", "Err", "msg", "tb")],
                )
            ],
        )
        data = json.loads(format_json(result))
        assert data["pages"][0]["errors"][0]["error_type"] == "Err"

    def test_valid_json(self):
        result = CheckResult()
        json.loads(format_json(result))


# ===================================================================
# write_log_file
# ===================================================================


class TestWriteLogFile:
    def test_creates_log_file(self, tmp_path):
        log_path = tmp_path / "check.log"
        result = CheckResult(
            pages=[
                PageResult(
                    "page.qmd",
                    "fail",
                    cells_checked=1,
                    errors=[CellError(0, "code", "Err", "msg", "tb")],
                )
            ]
        )
        assert write_log_file(result, log_path) is True
        assert log_path.exists()

    def test_no_log_when_all_pass(self, tmp_path):
        log_path = tmp_path / "check.log"
        result = CheckResult(pages=[PageResult("page.qmd", "pass", cells_checked=1)])
        assert write_log_file(result, log_path) is False
        assert not log_path.exists()

    def test_creates_parent_dirs(self, tmp_path):
        log_path = tmp_path / "sub" / "dir" / "check.log"
        result = CheckResult(
            pages=[
                PageResult(
                    "page.qmd",
                    "fail",
                    cells_checked=1,
                    errors=[CellError(0, "code", "Err", "msg", "tb")],
                )
            ]
        )
        write_log_file(result, log_path)
        assert log_path.exists()

    def test_content_includes_error_details(self, tmp_path):
        log_path = tmp_path / "check.log"
        result = CheckResult(
            pages=[
                PageResult(
                    "page.qmd",
                    "fail",
                    cells_checked=1,
                    errors=[CellError(0, "bad()", "NameError", "bad not defined", "full tb here")],
                )
            ]
        )
        write_log_file(result, log_path)
        content = log_path.read_text()
        assert "page.qmd" in content
        assert "bad()" in content
        assert "NameError" in content
        assert "full tb here" in content


# ===================================================================
# Log content — detailed structure
# ===================================================================


class TestLogContent:
    def test_log_entry_structure(self, tmp_path):
        log_path = tmp_path / "check.log"
        result = CheckResult(
            pages=[
                PageResult(
                    "reference/GT.qmd",
                    "fail",
                    cells_checked=3,
                    errors=[
                        CellError(
                            cell_index=2,
                            source='gt.GT(df).fmt_number(columns="price")',
                            error_type="NameError",
                            error_message="name 'df' is not defined",
                            traceback="Traceback (most recent call last):\n  File ...\nNameError: name 'df' is not defined",
                        )
                    ],
                )
            ]
        )
        write_log_file(result, log_path)
        content = log_path.read_text()
        assert "=" * 60 in content
        assert "Page: reference/GT.qmd | Cell 2" in content
        assert 'Source:\ngt.GT(df).fmt_number(columns="price")' in content
        assert "NameError: name 'df' is not defined" in content
        assert "Full traceback:\nTraceback (most recent call last):" in content

    def test_log_preserves_multiline_source(self, tmp_path):
        log_path = tmp_path / "check.log"
        multiline_source = "df = pd.DataFrame({\n    'a': [1, 2],\n    'b': [3, 4],\n})"
        result = CheckResult(
            pages=[
                PageResult(
                    "page.qmd",
                    "fail",
                    cells_checked=1,
                    errors=[CellError(0, multiline_source, "Err", "msg", "tb")],
                )
            ]
        )
        write_log_file(result, log_path)
        content = log_path.read_text()
        assert multiline_source in content

    def test_log_preserves_full_traceback(self, tmp_path):
        log_path = tmp_path / "check.log"
        full_tb = (
            "Traceback (most recent call last):\n"
            '  File "<stdin>", line 1, in <module>\n'
            '  File "mylib.py", line 42, in process\n'
            "    return data[key]\n"
            "KeyError: 'missing'"
        )
        result = CheckResult(
            pages=[
                PageResult(
                    "page.qmd",
                    "fail",
                    cells_checked=1,
                    errors=[CellError(0, "data[key]", "KeyError", "'missing'", full_tb)],
                )
            ]
        )
        write_log_file(result, log_path)
        content = log_path.read_text()
        assert full_tb in content

    def test_log_entries_ordered_by_page_and_cell(self, tmp_path):
        log_path = tmp_path / "check.log"
        result = CheckResult(
            pages=[
                PageResult(
                    "alpha.qmd",
                    "fail",
                    cells_checked=3,
                    errors=[
                        CellError(0, "alpha_cell_0", "E", "m", "t"),
                        CellError(2, "alpha_cell_2", "E", "m", "t"),
                    ],
                ),
                PageResult("beta.qmd", "pass", cells_checked=2),
                PageResult(
                    "gamma.qmd",
                    "fail",
                    cells_checked=1,
                    errors=[CellError(0, "gamma_cell_0", "E", "m", "t")],
                ),
            ]
        )
        write_log_file(result, log_path)
        content = log_path.read_text()
        pos_a0 = content.index("alpha_cell_0")
        pos_a2 = content.index("alpha_cell_2")
        pos_g0 = content.index("gamma_cell_0")
        assert pos_a0 < pos_a2 < pos_g0
        assert "beta.qmd" not in content

    def test_log_skips_error_status_pages(self, tmp_path):
        log_path = tmp_path / "check.log"
        result = CheckResult(
            pages=[
                PageResult("crashed.qmd", "error", message="render died"),
                PageResult(
                    "real_fail.qmd",
                    "fail",
                    cells_checked=1,
                    errors=[CellError(0, "code", "Err", "msg", "tb")],
                ),
            ]
        )
        write_log_file(result, log_path)
        content = log_path.read_text()
        assert "crashed.qmd" not in content
        assert "real_fail.qmd" in content

    def test_log_empty_traceback_omitted(self, tmp_path):
        log_path = tmp_path / "check.log"
        result = CheckResult(
            pages=[
                PageResult(
                    "page.qmd",
                    "fail",
                    cells_checked=1,
                    errors=[CellError(0, "code", "Err", "msg", "")],
                )
            ]
        )
        write_log_file(result, log_path)
        content = log_path.read_text()
        assert "Err: msg" in content
        assert "Full traceback:" not in content

    @requires_quarto
    def test_log_e2e_real_error(self, tmp_path):
        (tmp_path / "page.qmd").write_text(textwrap.dedent("""\
            ```{python}
            data = {"key": "value"}
            ```

            ```{python}
            result = data["nonexistent"]
            ```
        """))
        log_path = tmp_path / "check.log"
        result = check_examples(tmp_path, no_docstrings=True)
        write_log_file(result, log_path)
        assert log_path.exists()
        content = log_path.read_text()
        assert "page.qmd | Cell 1" in content
        assert "KeyError" in content

    @requires_quarto
    def test_log_e2e_multiple_failures(self, tmp_path):
        (tmp_path / "a.qmd").write_text("```{python}\n1/0\n```\n")
        (tmp_path / "b.qmd").write_text(
            "```{python}\nx = 1\n```\n\n```{python}\nundefined_var\n```\n"
        )
        log_path = tmp_path / "check.log"
        result = check_examples(tmp_path, no_docstrings=True)
        write_log_file(result, log_path)
        content = log_path.read_text()
        assert "a.qmd" in content
        assert "b.qmd" in content
        assert "ZeroDivisionError" in content
        assert "NameError" in content


# ===================================================================
# check_examples — orchestrator (mocked Quarto)
# ===================================================================


def _mock_render_pass(qmd_path, page_label, cells, timeout, project_root=None):
    return PageResult(page_label, "pass", cells_checked=len(cells))


def _mock_render_fail(qmd_path, page_label, cells, timeout, project_root=None):
    return PageResult(
        page_label, "fail", cells_checked=len(cells),
        errors=[CellError(0, cells[0].source if cells else "bad", "Err", "msg", "tb")],
    )


class TestCheckExamplesOrchestrator:
    def _write_qmd(self, path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content))

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_passing_project(self, mock_render, mock_quarto, tmp_path):
        self._write_qmd(
            tmp_path / "page.qmd",
            """\
            ---
            title: Test
            ---

            ```{python}
            x = 1
            ```
            """,
        )
        result = check_examples(tmp_path, no_docstrings=True)
        assert result.pages_checked == 1
        assert result.pages_passed == 1
        assert result.cells_failed == 0

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_fail)
    def test_failing_project(self, mock_render, mock_quarto, tmp_path):
        self._write_qmd(
            tmp_path / "page.qmd",
            """\
            ```{python}
            bad
            ```
            """,
        )
        result = check_examples(tmp_path, no_docstrings=True)
        assert result.pages_failed == 1
        assert result.cells_failed == 1

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_opted_out_page_skipped(self, mock_render, mock_quarto, tmp_path):
        self._write_qmd(
            tmp_path / "skipped.qmd",
            """\
            ---
            check-examples: false
            ---

            ```{python}
            raise Exception("should not run")
            ```
            """,
        )
        result = check_examples(tmp_path, no_docstrings=True)
        assert result.pages_checked == 0
        mock_render.assert_not_called()

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_no_executable_cells_page_skipped(self, mock_render, mock_quarto, tmp_path):
        self._write_qmd(
            tmp_path / "no_code.qmd",
            """\
            ---
            title: No code
            ---

            Just text, no code blocks.
            """,
        )
        result = check_examples(tmp_path, no_docstrings=True)
        assert result.pages_checked == 0
        mock_render.assert_not_called()

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_eval_false_cells_excluded(self, mock_render, mock_quarto, tmp_path):
        self._write_qmd(
            tmp_path / "page.qmd",
            """\
            ```{python}
            #| eval: false
            skipped
            ```

            ```{python}
            kept = True
            ```
            """,
        )
        result = check_examples(tmp_path, no_docstrings=True)
        assert result.pages_checked == 1
        cells_arg = mock_render.call_args[0][2]
        assert len(cells_arg) == 1
        assert "kept" in cells_arg[0].source

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_path_targeting(self, mock_render, mock_quarto, tmp_path):
        self._write_qmd(tmp_path / "a.qmd", "```{python}\nx = 1\n```\n")
        self._write_qmd(tmp_path / "b.qmd", "```{python}\ny = 2\n```\n")
        result = check_examples(tmp_path, paths=("a.qmd",), no_docstrings=True)
        assert result.pages_checked == 1
        assert result.pages[0].path == "a.qmd"

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_include_filter(self, mock_render, mock_quarto, tmp_path):
        (tmp_path / "guide").mkdir()
        self._write_qmd(tmp_path / "guide" / "intro.qmd", "```{python}\nx = 1\n```\n")
        self._write_qmd(tmp_path / "other.qmd", "```{python}\ny = 2\n```\n")
        result = check_examples(tmp_path, include="guide/*", no_docstrings=True)
        assert result.pages_checked == 1

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_exclude_filter(self, mock_render, mock_quarto, tmp_path):
        (tmp_path / "draft").mkdir()
        self._write_qmd(tmp_path / "draft" / "wip.qmd", "```{python}\nx = 1\n```\n")
        self._write_qmd(tmp_path / "good.qmd", "```{python}\ny = 2\n```\n")
        result = check_examples(tmp_path, exclude="draft/*", no_docstrings=True)
        assert result.pages_checked == 1
        assert result.pages[0].path == "good.qmd"

    def test_quarto_not_available(self, tmp_path):
        self._write_qmd(tmp_path / "page.qmd", "```{python}\nx = 1\n```\n")
        with patch(
            "great_docs._check_examples._check_quarto_available",
            return_value="Quarto is not installed",
        ):
            result = check_examples(tmp_path, no_docstrings=True)
        assert len(result.pages) == 1
        assert result.pages[0].status == "error"
        assert "Quarto" in result.pages[0].message

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_no_files_returns_empty_result(self, mock_render, mock_quarto, tmp_path):
        result = check_examples(tmp_path, no_docstrings=True)
        assert result.pages_checked == 0
        assert result.pages == []

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_build_dir_excluded(self, mock_render, mock_quarto, tmp_path):
        (tmp_path / "great-docs").mkdir()
        self._write_qmd(
            tmp_path / "great-docs" / "built.qmd", "```{python}\nx = 1\n```\n"
        )
        self._write_qmd(tmp_path / "real.qmd", "```{python}\ny = 2\n```\n")
        result = check_examples(tmp_path, no_docstrings=True)
        assert result.pages_checked == 1
        assert result.pages[0].path == "real.qmd"

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    def test_render_crash_reported_as_error(self, mock_quarto, tmp_path):
        self._write_qmd(tmp_path / "page.qmd", "```{python}\nx = 1\n```\n")
        with patch(
            "great_docs._check_examples._render_page_with_quarto",
            side_effect=Exception("render crashed"),
        ):
            result = check_examples(tmp_path, no_docstrings=True)
        assert result.pages_failed == 1
        assert result.pages[0].status == "error"
        assert "render crashed" in result.pages[0].message

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_docstrings_only_skips_qmd(self, mock_render, mock_quarto, tmp_path):
        self._write_qmd(tmp_path / "page.qmd", "```{python}\nx = 1\n```\n")
        with patch("great_docs._check_examples.extract_docstring_examples", return_value=[]):
            result = check_examples(tmp_path, docstrings_only=True)
        assert result.pages_checked == 0
        mock_render.assert_not_called()

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_no_docstrings_skips_docstring_extraction(self, mock_render, mock_quarto, tmp_path):
        self._write_qmd(tmp_path / "page.qmd", "```{python}\nx = 1\n```\n")
        with patch(
            "great_docs._check_examples.extract_docstring_examples"
        ) as mock_ds:
            result = check_examples(tmp_path, no_docstrings=True)
        mock_ds.assert_not_called()

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto")
    def test_tally_counts(self, mock_render, mock_quarto, tmp_path):
        self._write_qmd(tmp_path / "a.qmd", "```{python}\nx = 1\n```\n\n```{python}\ny = 2\n```\n")
        self._write_qmd(tmp_path / "b.qmd", "```{python}\nz = 3\n```\n")

        def render_side_effect(qmd_path, page_label, cells, timeout, project_root=None):
            if "a.qmd" in page_label:
                return PageResult(page_label, "pass", cells_checked=len(cells))
            else:
                return PageResult(
                    page_label, "fail", cells_checked=len(cells),
                    errors=[CellError(0, "z = 3", "Err", "msg", "tb")],
                )

        mock_render.side_effect = render_side_effect
        result = check_examples(tmp_path, no_docstrings=True)
        assert result.pages_checked == 2
        assert result.pages_passed == 1
        assert result.pages_failed == 1
        assert result.cells_checked == 3
        assert result.cells_passed == 2
        assert result.cells_failed == 1

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_pages_sorted_by_path(self, mock_render, mock_quarto, tmp_path):
        self._write_qmd(tmp_path / "z.qmd", "```{python}\nx = 1\n```\n")
        self._write_qmd(tmp_path / "a.qmd", "```{python}\ny = 2\n```\n")
        self._write_qmd(tmp_path / "m.qmd", "```{python}\nz = 3\n```\n")
        result = check_examples(tmp_path, no_docstrings=True)
        paths = [p.path for p in result.pages]
        assert paths == sorted(paths)


# ===================================================================
# check_examples — parallel mode
# ===================================================================


@requires_quarto
class TestCheckExamplesParallel:
    def _write_qmd(self, path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content))

    def test_parallel_runs_multiple_pages(self, tmp_path):
        self._write_qmd(tmp_path / "a.qmd", "```{python}\nx = 1\n```\n")
        self._write_qmd(tmp_path / "b.qmd", "```{python}\ny = 2\n```\n")
        result = check_examples(
            tmp_path, parallel=True, jobs=2, no_docstrings=True
        )
        assert result.pages_checked == 2
        assert result.pages_passed == 2

    def test_parallel_with_failure(self, tmp_path):
        self._write_qmd(tmp_path / "good.qmd", "```{python}\nx = 1\n```\n")
        self._write_qmd(
            tmp_path / "bad.qmd",
            "```{python}\nraise ValueError('boom')\n```\n",
        )
        result = check_examples(
            tmp_path, parallel=True, jobs=2, no_docstrings=True
        )
        assert result.pages_passed == 1
        assert result.pages_failed == 1

    def test_jobs_gt_1_implies_parallel(self, tmp_path):
        self._write_qmd(tmp_path / "a.qmd", "```{python}\nx = 1\n```\n")
        self._write_qmd(tmp_path / "b.qmd", "```{python}\ny = 2\n```\n")
        result = check_examples(
            tmp_path, jobs=2, no_docstrings=True
        )
        assert result.pages_checked == 2
        assert result.pages_passed == 2

    def test_parallel_pages_isolated(self, tmp_path):
        self._write_qmd(tmp_path / "a.qmd", "```{python}\nparallel_var = 99\n```\n")
        self._write_qmd(
            tmp_path / "b.qmd", "```{python}\nprint(parallel_var)\n```\n"
        )
        result = check_examples(
            tmp_path, parallel=True, jobs=2, no_docstrings=True
        )
        b_result = next(p for p in result.pages if p.path == "b.qmd")
        assert b_result.status == "fail"
        assert any("NameError" in e.error_type for e in b_result.errors)


# ===================================================================
# extract_docstring_examples (mocked)
# ===================================================================


class TestExtractDocstringExamples:
    def test_no_config_file(self, tmp_path):
        result = extract_docstring_examples(tmp_path)
        assert result == []

    def test_no_reference_enabled(self, tmp_path):
        (tmp_path / "great-docs.yml").write_text("display_name: Test\n")
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
        mock_config = MagicMock()
        mock_config.reference_enabled = False
        with patch("great_docs.config.Config", return_value=mock_config):
            result = extract_docstring_examples(tmp_path)
        assert result == []

    def test_no_package_detected(self, tmp_path):
        (tmp_path / "great-docs.yml").write_text("display_name: Test\n")
        mock_config = MagicMock()
        mock_config.reference_enabled = True
        mock_config.reference = [{"contents": ["Foo"]}]
        with patch("great_docs.config.Config", return_value=mock_config):
            result = extract_docstring_examples(tmp_path)
        assert result == []


# ===================================================================
# CLI — check-examples command
# ===================================================================


class TestCheckExamplesCLI:
    def _write_qmd(self, path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content))

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_cli_passing(self, mock_render, mock_quarto, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._write_qmd(tmp_path / "page.qmd", "```{python}\nx = 1\n```\n")
        runner = CliRunner()
        result = runner.invoke(cli, ["check-examples", "--no-docstrings"])
        assert result.exit_code == 0
        assert "1 passed" in result.output

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_fail)
    def test_cli_failing_exit_code_1(self, mock_render, mock_quarto, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._write_qmd(tmp_path / "page.qmd", "```{python}\nbad\n```\n")
        runner = CliRunner()
        result = runner.invoke(cli, ["check-examples", "--no-docstrings"])
        assert result.exit_code == 1

    def test_cli_quarto_not_found_exit_code_2(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._write_qmd(tmp_path / "page.qmd", "```{python}\nx = 1\n```\n")
        runner = CliRunner()
        with patch(
            "great_docs._check_examples._check_quarto_available",
            return_value="Quarto is not installed",
        ):
            result = runner.invoke(cli, ["check-examples", "--no-docstrings"])
        assert result.exit_code == 2

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_cli_json_output(self, mock_render, mock_quarto, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._write_qmd(tmp_path / "page.qmd", "```{python}\nx = 1\n```\n")
        runner = CliRunner()
        result = runner.invoke(cli, ["check-examples", "--no-docstrings", "--json-output"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "summary" in data
        assert data["summary"]["pages_passed"] == 1

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_cli_verbose(self, mock_render, mock_quarto, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._write_qmd(tmp_path / "page.qmd", "```{python}\nx = 1\n```\n")
        runner = CliRunner()
        result = runner.invoke(cli, ["check-examples", "--no-docstrings", "--verbose"])
        assert result.exit_code == 0

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_cli_with_path_argument(self, mock_render, mock_quarto, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._write_qmd(tmp_path / "a.qmd", "```{python}\nx = 1\n```\n")
        self._write_qmd(tmp_path / "b.qmd", "```{python}\ny = 2\n```\n")
        runner = CliRunner()
        result = runner.invoke(cli, ["check-examples", "--no-docstrings", "a.qmd"])
        assert result.exit_code == 0
        assert "a.qmd" in result.output
        assert "b.qmd" not in result.output

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_cli_project_path(self, mock_render, mock_quarto, tmp_path):
        self._write_qmd(tmp_path / "page.qmd", "```{python}\nx = 1\n```\n")
        runner = CliRunner()
        result = runner.invoke(
            cli, ["check-examples", "--no-docstrings", "--project-path", str(tmp_path)]
        )
        assert result.exit_code == 0

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto")
    def test_cli_log_file_written(self, mock_render, mock_quarto, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        def render_fail(qmd_path, page_label, cells, timeout, project_root=None):
            return PageResult(
                page_label, "fail", cells_checked=1,
                errors=[CellError(0, "x", "E", "m", "full tb")],
            )

        mock_render.side_effect = render_fail
        self._write_qmd(tmp_path / "page.qmd", "```{python}\nx\n```\n")
        log_path = tmp_path / "my_log.log"
        runner = CliRunner()
        result = runner.invoke(
            cli, ["check-examples", "--no-docstrings", "--log-file", str(log_path)]
        )
        assert result.exit_code == 1
        assert log_path.exists()
        assert "full tb" in log_path.read_text()

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_cli_no_files_exit_code_0(self, mock_render, mock_quarto, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["check-examples", "--no-docstrings"])
        assert result.exit_code == 0
        assert "0 passed" in result.output

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_cli_include(self, mock_render, mock_quarto, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "guide").mkdir()
        self._write_qmd(tmp_path / "guide" / "intro.qmd", "```{python}\nx = 1\n```\n")
        self._write_qmd(tmp_path / "other.qmd", "```{python}\ny = 2\n```\n")
        runner = CliRunner()
        result = runner.invoke(
            cli, ["check-examples", "--no-docstrings", "--include", "guide/*"]
        )
        assert result.exit_code == 0
        assert "intro.qmd" in result.output
        assert "other.qmd" not in result.output

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_cli_exclude(self, mock_render, mock_quarto, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "draft").mkdir()
        self._write_qmd(tmp_path / "draft" / "wip.qmd", "```{python}\nx = 1\n```\n")
        self._write_qmd(tmp_path / "good.qmd", "```{python}\ny = 2\n```\n")
        runner = CliRunner()
        result = runner.invoke(
            cli, ["check-examples", "--no-docstrings", "--exclude", "draft/*"]
        )
        assert result.exit_code == 0
        assert "good.qmd" in result.output
        assert "wip.qmd" not in result.output

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_cli_timeout(self, mock_render, mock_quarto, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._write_qmd(tmp_path / "page.qmd", "```{python}\nx = 1\n```\n")
        runner = CliRunner()
        result = runner.invoke(
            cli, ["check-examples", "--no-docstrings", "--timeout", "60"]
        )
        assert result.exit_code == 0

    @requires_quarto
    def test_cli_parallel(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._write_qmd(tmp_path / "a.qmd", "```{python}\nx = 1\n```\n")
        self._write_qmd(tmp_path / "b.qmd", "```{python}\ny = 2\n```\n")
        runner = CliRunner()
        result = runner.invoke(
            cli, ["check-examples", "--no-docstrings", "--parallel"]
        )
        assert result.exit_code == 0
        assert "2 passed" in result.output

    @requires_quarto
    def test_cli_jobs(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._write_qmd(tmp_path / "a.qmd", "```{python}\nx = 1\n```\n")
        runner = CliRunner()
        result = runner.invoke(
            cli, ["check-examples", "--no-docstrings", "-j", "2"]
        )
        assert result.exit_code == 0
        assert "1 passed" in result.output

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_cli_docstrings_only(self, mock_render, mock_quarto, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._write_qmd(tmp_path / "page.qmd", "```{python}\nx = 1\n```\n")
        runner = CliRunner()
        with patch(
            "great_docs._check_examples.extract_docstring_examples", return_value=[]
        ):
            result = runner.invoke(cli, ["check-examples", "--docstrings-only"])
        assert result.exit_code == 0
        assert "page.qmd" not in result.output
        mock_render.assert_not_called()

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto")
    def test_cli_default_log_file_location(self, mock_render, mock_quarto, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        def render_fail(qmd_path, page_label, cells, timeout, project_root=None):
            return PageResult(
                page_label, "fail", cells_checked=1,
                errors=[CellError(0, "code", "Err", "msg", "tb")],
            )

        mock_render.side_effect = render_fail
        self._write_qmd(tmp_path / "page.qmd", "```{python}\ncode\n```\n")
        runner = CliRunner()
        result = runner.invoke(cli, ["check-examples", "--no-docstrings"])
        assert result.exit_code == 1
        default_log = tmp_path / ".great-docs" / "check-examples.log"
        assert default_log.exists()
        assert "check-examples.log" in result.output

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_cli_no_log_file_when_passing(self, mock_render, mock_quarto, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._write_qmd(tmp_path / "page.qmd", "```{python}\nx = 1\n```\n")
        runner = CliRunner()
        result = runner.invoke(cli, ["check-examples", "--no-docstrings"])
        assert result.exit_code == 0
        default_log = tmp_path / ".great-docs" / "check-examples.log"
        assert not default_log.exists()
        assert "check-examples.log" not in result.output

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto")
    def test_cli_verbose_shows_traceback(self, mock_render, mock_quarto, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        def render_fail(qmd_path, page_label, cells, timeout, project_root=None):
            return PageResult(
                page_label, "fail", cells_checked=1,
                errors=[CellError(0, "bad_call()", "NameError", "bad_call not defined", "line 1 in <module>\nNameError: bad_call")],
            )

        mock_render.side_effect = render_fail
        self._write_qmd(tmp_path / "page.qmd", "```{python}\nbad_call()\n```\n")
        runner = CliRunner()
        result = runner.invoke(cli, ["check-examples", "--no-docstrings", "--verbose"])
        assert result.exit_code == 1
        assert "line 1 in <module>" in result.output
        assert "NameError: bad_call" in result.output

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto")
    def test_cli_no_verbose_hides_traceback(self, mock_render, mock_quarto, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        def render_fail(qmd_path, page_label, cells, timeout, project_root=None):
            return PageResult(
                page_label, "fail", cells_checked=1,
                errors=[CellError(0, "bad_call()", "NameError", "bad_call not defined", "line 1 in <module>\nNameError: bad_call")],
            )

        mock_render.side_effect = render_fail
        self._write_qmd(tmp_path / "page.qmd", "```{python}\nbad_call()\n```\n")
        runner = CliRunner()
        result = runner.invoke(cli, ["check-examples", "--no-docstrings"])
        assert result.exit_code == 1
        assert "NameError: bad_call not defined" in result.output
        assert "line 1 in <module>" not in result.output

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto")
    def test_cli_json_output_with_failure(self, mock_render, mock_quarto, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        def render_fail(qmd_path, page_label, cells, timeout, project_root=None):
            return PageResult(
                page_label, "fail", cells_checked=1,
                errors=[CellError(0, "1/0", "ZeroDivisionError", "division by zero", "tb lines")],
            )

        mock_render.side_effect = render_fail
        self._write_qmd(tmp_path / "page.qmd", "```{python}\n1/0\n```\n")
        runner = CliRunner()
        result = runner.invoke(cli, ["check-examples", "--no-docstrings", "--json-output"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["summary"]["cells_failed"] == 1
        assert data["pages"][0]["errors"][0]["error_type"] == "ZeroDivisionError"

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_cli_json_no_header(self, mock_render, mock_quarto, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._write_qmd(tmp_path / "page.qmd", "```{python}\nx = 1\n```\n")
        runner = CliRunner()
        result = runner.invoke(cli, ["check-examples", "--no-docstrings", "--json-output"])
        assert result.exit_code == 0
        assert "Checking examples" not in result.output
        json.loads(result.output)

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_cli_multiple_paths(self, mock_render, mock_quarto, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._write_qmd(tmp_path / "a.qmd", "```{python}\nx = 1\n```\n")
        self._write_qmd(tmp_path / "b.qmd", "```{python}\ny = 2\n```\n")
        self._write_qmd(tmp_path / "c.qmd", "```{python}\nz = 3\n```\n")
        runner = CliRunner()
        result = runner.invoke(cli, ["check-examples", "--no-docstrings", "a.qmd", "b.qmd"])
        assert result.exit_code == 0
        assert "a.qmd" in result.output
        assert "b.qmd" in result.output
        assert "c.qmd" not in result.output

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_cli_directory_path(self, mock_render, mock_quarto, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "guide").mkdir()
        self._write_qmd(tmp_path / "guide" / "intro.qmd", "```{python}\nx = 1\n```\n")
        self._write_qmd(tmp_path / "guide" / "advanced.qmd", "```{python}\ny = 2\n```\n")
        self._write_qmd(tmp_path / "other.qmd", "```{python}\nz = 3\n```\n")
        runner = CliRunner()
        result = runner.invoke(cli, ["check-examples", "--no-docstrings", "guide"])
        assert result.exit_code == 0
        assert "intro.qmd" in result.output
        assert "advanced.qmd" in result.output
        assert "other.qmd" not in result.output

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_cli_path_with_include(self, mock_render, mock_quarto, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "guide").mkdir()
        self._write_qmd(tmp_path / "guide" / "intro.qmd", "```{python}\nx = 1\n```\n")
        self._write_qmd(tmp_path / "guide" / "deep.qmd", "```{python}\ny = 2\n```\n")
        runner = CliRunner()
        result = runner.invoke(
            cli, ["check-examples", "--no-docstrings", "guide", "--include", "guide/intro*"]
        )
        assert result.exit_code == 0
        assert "intro.qmd" in result.output
        assert "deep.qmd" not in result.output

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto")
    def test_cli_json_overrides_verbose(self, mock_render, mock_quarto, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        def render_fail(qmd_path, page_label, cells, timeout, project_root=None):
            return PageResult(
                page_label, "fail", cells_checked=1,
                errors=[CellError(0, "x", "E", "m", "tb")],
            )

        mock_render.side_effect = render_fail
        self._write_qmd(tmp_path / "page.qmd", "```{python}\nx\n```\n")
        runner = CliRunner()
        result = runner.invoke(
            cli, ["check-examples", "--no-docstrings", "--json-output", "--verbose"]
        )
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert "summary" in data

    @requires_quarto
    def test_cli_parallel_timeout_verbose(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "a.qmd").write_text("```{python}\nx = 1\n```\n")
        (tmp_path / "b.qmd").write_text("```{python}\nraise ValueError('boom')\n```\n")
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "check-examples",
                "--no-docstrings",
                "--parallel",
                "-j", "2",
                "--timeout", "15",
                "--verbose",
            ],
        )
        assert result.exit_code == 1
        assert "1 passed" in result.output
        assert "1 failed" in result.output
        assert "ValueError" in result.output

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_cli_include_exclude_json(self, mock_render, mock_quarto, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "guide").mkdir()
        (tmp_path / "guide" / "sub").mkdir()
        self._write_qmd(tmp_path / "guide" / "intro.qmd", "```{python}\nx = 1\n```\n")
        self._write_qmd(
            tmp_path / "guide" / "sub" / "deep.qmd", "```{python}\ny = 2\n```\n"
        )
        self._write_qmd(tmp_path / "other.qmd", "```{python}\nz = 3\n```\n")
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "check-examples",
                "--no-docstrings",
                "--include", "guide/*",
                "--exclude", "guide/sub/*",
                "--json-output",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        paths = [p["path"] for p in data["pages"]]
        assert any("intro" in p for p in paths)
        assert not any("deep" in p for p in paths)
        assert not any("other" in p for p in paths)

    def test_cli_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["check-examples", "--help"])
        assert result.exit_code == 0
        assert "Check that Python code examples" in result.output
        assert "--timeout" in result.output
        assert "--json-output" in result.output
        assert "--verbose" in result.output
        assert "--parallel" in result.output
        assert "--jobs" in result.output
        assert "--log-file" in result.output
        assert "--include" in result.output
        assert "--exclude" in result.output
        assert "--no-docstrings" in result.output
        assert "--docstrings-only" in result.output
        assert "Quarto" in result.output

    def test_cli_command_in_main_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert "check-examples" in result.output

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_cli_console_shows_checking_header(self, mock_render, mock_quarto, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._write_qmd(tmp_path / "page.qmd", "```{python}\nx = 1\n```\n")
        runner = CliRunner()
        result = runner.invoke(cli, ["check-examples", "--no-docstrings"])
        assert result.exit_code == 0
        assert "Checking examples..." in result.output

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto")
    def test_cli_console_failure_format(self, mock_render, mock_quarto, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        def render_fail(qmd_path, page_label, cells, timeout, project_root=None):
            return PageResult(
                page_label, "fail", cells_checked=1,
                errors=[CellError(0, "bad()", "NameError", "name 'bad' is not defined", "traceback here")],
            )

        mock_render.side_effect = render_fail
        self._write_qmd(tmp_path / "fail.qmd", "```{python}\nbad()\n```\n")
        runner = CliRunner()
        result = runner.invoke(cli, ["check-examples", "--no-docstrings"])
        assert result.exit_code == 1
        assert "✗ fail.qmd" in result.output
        assert "Cell 0:" in result.output
        assert "bad()" in result.output
        assert "NameError: name 'bad' is not defined" in result.output
        assert "0 passed, 1 failed" in result.output


# ===================================================================
# Integration: end-to-end with real Quarto
# ===================================================================


@requires_quarto
class TestEndToEnd:
    """Full integration tests that use real Quarto rendering."""

    def _write_qmd(self, path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content))

    def test_passing_page_e2e(self, tmp_path):
        self._write_qmd(
            tmp_path / "good.qmd",
            """\
            ---
            title: Good
            ---

            ```{python}
            x = [1, 2, 3]
            ```

            ```{python}
            total = sum(x)
            assert total == 6
            ```
            """,
        )
        result = check_examples(tmp_path, no_docstrings=True)
        assert result.pages_passed == 1
        assert result.cells_failed == 0

    def test_failing_page_e2e(self, tmp_path):
        self._write_qmd(
            tmp_path / "bad.qmd",
            """\
            ```{python}
            data = {"key": "value"}
            ```

            ```{python}
            print(data["missing_key"])
            ```
            """,
        )
        result = check_examples(tmp_path, no_docstrings=True)
        assert result.pages_failed == 1
        assert result.cells_failed == 1
        err = result.pages[0].errors[0]
        assert err.error_type == "KeyError"

    def test_mixed_pages_e2e(self, tmp_path):
        self._write_qmd(tmp_path / "good.qmd", "```{python}\nx = 1\n```\n")
        self._write_qmd(
            tmp_path / "bad.qmd",
            "```{python}\nraise RuntimeError('boom')\n```\n",
        )
        self._write_qmd(
            tmp_path / "skip.qmd",
            "---\ncheck-examples: false\n---\n\n```{python}\nraise Exception\n```\n",
        )
        result = check_examples(tmp_path, no_docstrings=True)
        assert result.pages_passed == 1
        assert result.pages_failed == 1
        assert result.cells_checked == 2

    def test_sequential_state_shared_e2e(self, tmp_path):
        self._write_qmd(
            tmp_path / "state.qmd",
            """\
            ```{python}
            counter = 0
            ```

            ```{python}
            counter += 1
            ```

            ```{python}
            counter += 1
            assert counter == 2
            ```
            """,
        )
        result = check_examples(tmp_path, no_docstrings=True)
        assert result.cells_failed == 0

    def test_independent_pages_e2e(self, tmp_path):
        self._write_qmd(tmp_path / "a.qmd", "```{python}\npage_a_var = 42\n```\n")
        self._write_qmd(
            tmp_path / "b.qmd",
            "```{python}\nprint(page_a_var)\n```\n",
        )
        result = check_examples(tmp_path, no_docstrings=True)
        b_result = next(p for p in result.pages if p.path == "b.qmd")
        assert b_result.status == "fail"
        assert any("NameError" in e.error_type for e in b_result.errors)

    def test_check_false_cell_skipped_e2e(self, tmp_path):
        self._write_qmd(
            tmp_path / "page.qmd",
            """\
            ```{python}
            x = 1
            ```

            ```{python}
            #| check: false
            raise Exception("should not run")
            ```

            ```{python}
            assert x == 1
            ```
            """,
        )
        result = check_examples(tmp_path, no_docstrings=True)
        assert result.cells_failed == 0
        assert result.cells_checked == 2

    def test_error_true_cell_not_reported_e2e(self, tmp_path):
        self._write_qmd(
            tmp_path / "page.qmd",
            """\
            ```{python}
            x = 1
            ```

            ```{python}
            #| error: true
            raise ValueError("intentional")
            ```

            ```{python}
            assert x == 1
            ```
            """,
        )
        result = check_examples(tmp_path, no_docstrings=True)
        assert result.cells_failed == 0


# ===================================================================
# Edge cases — parsing
# ===================================================================


class TestExtractCellsEdgeCases:
    def test_nested_backticks_in_cell(self):
        qmd = textwrap.dedent("""\
            ```{python}
            x = "```not a fence```"
            y = 1
            ```
        """)
        cells = extract_cells(qmd)
        assert len(cells) == 1
        assert 'x = "```not a fence```"' in cells[0].source

    def test_cell_with_only_options_no_code(self):
        qmd = "```{python}\n#| echo: false\n#| output: true\n```\n"
        cells = extract_cells(qmd)
        assert len(cells) == 0

    def test_windows_line_endings(self):
        qmd = "```{python}\r\nx = 1\r\ny = 2\r\n```\r\n"
        cells = extract_cells(qmd)
        assert len(cells) == 1
        assert "x = 1" in cells[0].source

    def test_consecutive_cells_no_gap(self):
        qmd = "```{python}\nx = 1\n```\n```{python}\ny = 2\n```\n"
        cells = extract_cells(qmd)
        assert len(cells) == 2
        assert cells[0].source == "x = 1"
        assert cells[1].source == "y = 2"

    def test_cell_with_indented_code(self):
        qmd = textwrap.dedent("""\
            ```{python}
            def foo():
                return 42

            result = foo()
            ```
        """)
        cells = extract_cells(qmd)
        assert len(cells) == 1
        assert "    return 42" in cells[0].source

    def test_cell_with_blank_lines_in_body(self):
        qmd = "```{python}\nx = 1\n\n\ny = 2\n```\n"
        cells = extract_cells(qmd)
        assert len(cells) == 1
        assert "\n\n" in cells[0].source

    def test_frontmatter_only_qmd(self):
        qmd = "---\ntitle: Empty\n---\n\nJust text.\n"
        cells = extract_cells(qmd)
        assert len(cells) == 0

    def test_eval_false_case_variations(self):
        for val in ("false", "False", "FALSE", "no", "No", "NO"):
            qmd = f"```{{python}}\n#| eval: {val}\nx = 1\n```\n"
            cells = extract_cells(qmd)
            assert len(cells) == 0, f"eval: {val} should be skipped"

    def test_check_false_case_variations(self):
        for val in ("false", "False", "FALSE", "no", "No", "NO"):
            qmd = f"```{{python}}\n#| check: {val}\nx = 1\n```\n"
            cells = extract_cells(qmd)
            assert len(cells) == 0, f"check: {val} should be skipped"

    def test_hashpipe_with_extra_spaces(self):
        qmd = "```{python}\n#|   echo:   false  \nx = 1\n```\n"
        cells = extract_cells(qmd)
        assert len(cells) == 1
        assert cells[0].options["echo"] == "false"

    def test_non_hashpipe_comment_not_treated_as_option(self):
        qmd = "```{python}\n# this is a comment\nx = 1\n```\n"
        cells = extract_cells(qmd)
        assert len(cells) == 1
        assert cells[0].options == {}
        assert "# this is a comment" in cells[0].source

    def test_cell_with_unicode(self):
        qmd = "```{python}\nmessage = 'héllo wörld 🐍'\n```\n"
        cells = extract_cells(qmd)
        assert len(cells) == 1
        assert "héllo wörld 🐍" in cells[0].source


class TestPageOptedOutEdgeCases:
    def test_similar_key_not_matched(self):
        assert _page_opted_out("---\ncheck-examples-extra: false\n---\nContent") is False

    def test_check_examples_with_colon_in_value(self):
        assert _page_opted_out("---\ncheck-examples: false:extra\n---\nContent") is False

    def test_multiple_frontmatter_blocks(self):
        text = "---\ntitle: First\n---\nContent\n---\ncheck-examples: false\n---\n"
        assert _page_opted_out(text) is False

    def test_indented_frontmatter_key(self):
        assert _page_opted_out("---\n  check-examples: false\n---\nContent") is True


# ===================================================================
# Edge cases — Quarto execution
# ===================================================================


@requires_quarto
class TestExecutionEdgeCases:
    """Edge cases for Quarto-based execution."""

    def test_cell_with_output_no_error(self, tmp_path):
        qmd = tmp_path / "page.qmd"
        qmd.write_text("```{python}\nprint('hello')\n```\n\n```{python}\nprint(42)\n```\n")
        cells = extract_cells(qmd.read_text())
        result = _render_page_with_quarto(qmd, "page.qmd", cells, 30)
        assert result.status == "pass"

    def test_cell_with_warning_no_error(self, tmp_path):
        qmd = tmp_path / "page.qmd"
        qmd.write_text("```{python}\nimport warnings; warnings.warn('test warning')\n```\n")
        cells = extract_cells(qmd.read_text())
        result = _render_page_with_quarto(qmd, "page.qmd", cells, 30)
        assert result.status == "pass"

    def test_cell_modifies_namespace(self, tmp_path):
        qmd = tmp_path / "page.qmd"
        qmd.write_text(
            "```{python}\nimport os\n```\n\n"
            "```{python}\ncwd = os.getcwd()\n```\n\n"
            "```{python}\nassert isinstance(cwd, str)\n```\n"
        )
        cells = extract_cells(qmd.read_text())
        result = _render_page_with_quarto(qmd, "page.qmd", cells, 30)
        assert result.status == "pass"

    def test_error_continuation(self, tmp_path):
        qmd = tmp_path / "page.qmd"
        qmd.write_text(
            "```{python}\nundefined_func()\n```\n\n"
            "```{python}\nx = 42\n```\n"
        )
        cells = extract_cells(qmd.read_text())
        result = _render_page_with_quarto(qmd, "page.qmd", cells, 30)
        assert result.status == "fail"
        assert len(result.errors) == 1
        assert result.errors[0].cell_index == 0

    def test_multiple_errors(self, tmp_path):
        qmd = tmp_path / "page.qmd"
        qmd.write_text(
            '```{python}\nraise TypeError("first")\n```\n\n'
            "```{python}\nx = 1\n```\n\n"
            '```{python}\nraise ValueError("second")\n```\n'
        )
        cells = extract_cells(qmd.read_text())
        result = _render_page_with_quarto(qmd, "page.qmd", cells, 30)
        assert len(result.errors) == 2


# ===================================================================
# Edge cases — output formatting
# ===================================================================


class TestOutputEdgeCases:
    def test_json_with_special_characters(self):
        result = CheckResult(
            pages_checked=1,
            pages_failed=1,
            cells_checked=1,
            cells_failed=1,
            pages=[
                PageResult(
                    "page.qmd",
                    "fail",
                    cells_checked=1,
                    errors=[
                        CellError(
                            0,
                            'x = "quotes \\ and\nnewlines"',
                            "ValueError",
                            'bad "value" with\ttabs',
                            "line 1\nline 2",
                        )
                    ],
                )
            ],
        )
        output = format_json(result)
        data = json.loads(output)
        assert data["pages"][0]["errors"][0]["source"] == 'x = "quotes \\ and\nnewlines"'

    def test_json_with_unicode(self):
        result = CheckResult(
            pages_checked=1,
            pages_failed=1,
            cells_checked=1,
            cells_failed=1,
            pages=[
                PageResult(
                    "page.qmd",
                    "fail",
                    cells_checked=1,
                    errors=[
                        CellError(0, "données = '🐍'", "Err", "erreur éè", "")
                    ],
                )
            ],
        )
        output = format_json(result)
        data = json.loads(output)
        assert "données" in data["pages"][0]["errors"][0]["source"]
        assert "erreur éè" in data["pages"][0]["errors"][0]["error_message"]

    def test_console_multiline_source_in_error(self):
        result = CheckResult(
            pages_checked=1,
            pages_failed=1,
            cells_checked=1,
            cells_failed=1,
            pages=[
                PageResult(
                    "page.qmd",
                    "fail",
                    cells_checked=1,
                    errors=[
                        CellError(
                            0,
                            "def foo():\n    return bar()",
                            "NameError",
                            "bar not defined",
                            "",
                        )
                    ],
                )
            ],
        )
        output = format_console(result)
        assert "      def foo():" in output
        assert "          return bar()" in output

    def test_log_with_unicode(self, tmp_path):
        log_path = tmp_path / "check.log"
        result = CheckResult(
            pages=[
                PageResult(
                    "page.qmd",
                    "fail",
                    cells_checked=1,
                    errors=[
                        CellError(0, "résumé = '🎉'", "Erreur", "données 💥", "tracé complet")
                    ],
                )
            ]
        )
        write_log_file(result, log_path)
        content = log_path.read_text(encoding="utf-8")
        assert "résumé = '🎉'" in content
        assert "données 💥" in content
        assert "tracé complet" in content


# ===================================================================
# Edge cases — orchestrator
# ===================================================================


class TestOrchestratorEdgeCases:
    def _write_qmd(self, path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content))

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_all_pages_opted_out(self, mock_render, mock_quarto, tmp_path):
        self._write_qmd(
            tmp_path / "a.qmd",
            "---\ncheck-examples: false\n---\n\n```{python}\nx=1\n```\n",
        )
        self._write_qmd(
            tmp_path / "b.qmd",
            "---\ncheck-examples: false\n---\n\n```{python}\ny=2\n```\n",
        )
        result = check_examples(tmp_path, no_docstrings=True)
        assert result.pages_checked == 0
        assert result.pages == []
        mock_render.assert_not_called()

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_page_with_all_eval_false(self, mock_render, mock_quarto, tmp_path):
        self._write_qmd(
            tmp_path / "page.qmd",
            """\
            ```{python}
            #| eval: false
            a = 1
            ```

            ```{python}
            #| eval: false
            b = 2
            ```
            """,
        )
        result = check_examples(tmp_path, no_docstrings=True)
        assert result.pages_checked == 0
        mock_render.assert_not_called()

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto")
    def test_mixed_pass_fail_error_pages(self, mock_render, mock_quarto, tmp_path):
        self._write_qmd(tmp_path / "a_pass.qmd", "```{python}\nx = 1\n```\n")
        self._write_qmd(tmp_path / "b_fail.qmd", "```{python}\nbad\n```\n")
        self._write_qmd(tmp_path / "c_crash.qmd", "```{python}\nz = 1\n```\n")

        call_count = [0]

        def render_side_effect(qmd_path, page_label, cells, timeout, project_root=None):
            call_count[0] += 1
            if "a_pass" in page_label:
                return PageResult(page_label, "pass", cells_checked=len(cells))
            elif "b_fail" in page_label:
                return PageResult(
                    page_label, "fail", cells_checked=len(cells),
                    errors=[CellError(0, "bad", "NameError", "bad", "tb")],
                )
            else:
                raise RuntimeError("render crashed")

        mock_render.side_effect = render_side_effect
        result = check_examples(tmp_path, no_docstrings=True)

        assert result.pages_passed == 1
        assert result.pages_failed == 2
        assert result.pages_checked == 3

        statuses = {p.path: p.status for p in result.pages}
        assert statuses["a_pass.qmd"] == "pass"
        assert statuses["b_fail.qmd"] == "fail"
        assert statuses["c_crash.qmd"] == "error"

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_empty_qmd_file(self, mock_render, mock_quarto, tmp_path):
        (tmp_path / "empty.qmd").write_text("")
        result = check_examples(tmp_path, no_docstrings=True)
        assert result.pages_checked == 0
        mock_render.assert_not_called()

    @patch("great_docs._check_examples._check_quarto_available", return_value=None)
    @patch("great_docs._check_examples._render_page_with_quarto", side_effect=_mock_render_pass)
    def test_qmd_with_only_non_python_blocks(self, mock_render, mock_quarto, tmp_path):
        (tmp_path / "r_only.qmd").write_text(
            "```{r}\nlibrary(dplyr)\n```\n\n```bash\necho hello\n```\n"
        )
        result = check_examples(tmp_path, no_docstrings=True)
        assert result.pages_checked == 0
        mock_render.assert_not_called()

    @requires_quarto
    def test_many_cells_e2e(self, tmp_path):
        lines = []
        for i in range(20):
            lines.append("```{python}")
            lines.append(f"v_{i} = {i}")
            lines.append("```")
            lines.append("")
        lines.append("```{python}")
        lines.append("total = " + " + ".join(f"v_{i}" for i in range(20)))
        lines.append(f"assert total == {sum(range(20))}")
        lines.append("```")
        (tmp_path / "many.qmd").write_text("\n".join(lines))

        result = check_examples(tmp_path, no_docstrings=True)
        assert result.cells_failed == 0
        assert result.cells_checked == 21
