from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from great_docs._mock_code import expand_mock_cells, process_directory, process_qmd_file


# ---------------------------------------------------------------------------
# expand_mock_cells — unit tests
# ---------------------------------------------------------------------------


class TestExpandMockCells:
    """Test the core text-rewriting function."""

    def test_basic_mock_cell(self):
        """A mock cell is split into display (eval: false) + eval (echo: false)."""
        src = textwrap.dedent("""\
            Some text.

            ```{python}
            #| source-code: mock
            display_code()
            # ---
            eval_code()
            ```

            More text.
        """)
        result = expand_mock_cells(src)

        # Display cell
        assert "#| eval: false" in result
        assert "display_code()" in result

        # Eval cell
        assert "#| echo: false" in result
        assert "eval_code()" in result

        # Original option removed
        assert "#| source-code: mock" not in result

        # Delimiter removed
        assert "# ---" not in result

        # Surrounding text preserved
        assert "Some text." in result
        assert "More text." in result

    def test_no_delimiter_is_display_only(self):
        """Without a delimiter, the cell becomes display-only (eval: false)."""
        src = textwrap.dedent("""\
            ```{python}
            #| source-code: mock
            display_only()
            ```
        """)
        result = expand_mock_cells(src)

        assert "#| eval: false" in result
        assert "display_only()" in result
        # No eval cell should be emitted
        assert "#| echo: false" not in result

    def test_output_title_forwarded(self):
        """output-title is forwarded to the eval cell only."""
        src = textwrap.dedent("""\
            ```{python}
            #| source-code: mock
            #| output-title: "Response"
            show_this()
            # ---
            run_this()
            ```
        """)
        result = expand_mock_cells(src)

        lines = result.split("\n")

        # output-title should appear in the eval cell block, not display
        # Find the eval cell (starts with echo: false)
        eval_start = None
        display_start = None
        for i, line in enumerate(lines):
            if line.strip() == "#| echo: false":
                eval_start = i
            if line.strip() == "#| eval: false":
                display_start = i

        assert eval_start is not None
        assert display_start is not None

        # output-title should be between eval_start and the next closing fence
        eval_section = "\n".join(lines[eval_start:])
        assert '#| output-title: "Response"' in eval_section

        # output-title should NOT be in the display cell
        display_section = "\n".join(lines[display_start:eval_start])
        assert "output-title" not in display_section

    def test_other_options_forwarded(self):
        """Non-mock options like warning: false are forwarded to both cells."""
        src = textwrap.dedent("""\
            ```{python}
            #| source-code: mock
            #| warning: false
            show()
            # ---
            run()
            ```
        """)
        result = expand_mock_cells(src)

        # warning: false should appear twice (once per cell)
        assert result.count("#| warning: false") == 2

    def test_multiple_mock_cells(self):
        """Multiple mock cells in one file are all expanded."""
        src = textwrap.dedent("""\
            ```{python}
            #| source-code: mock
            a()
            # ---
            a_real()
            ```

            Text between.

            ```{python}
            #| source-code: mock
            b()
            # ---
            b_real()
            ```
        """)
        result = expand_mock_cells(src)

        assert result.count("#| eval: false") == 2
        assert result.count("#| echo: false") == 2
        assert "a()" in result
        assert "a_real()" in result
        assert "b()" in result
        assert "b_real()" in result
        assert "Text between." in result

    def test_non_mock_cells_unchanged(self):
        """Regular code cells are not modified."""
        src = textwrap.dedent("""\
            ```{python}
            #| echo: false
            normal_code()
            ```
        """)
        result = expand_mock_cells(src)
        assert result.strip() == src.strip()

    def test_static_code_blocks_unchanged(self):
        """Non-executable code blocks (```python) are not touched."""
        src = textwrap.dedent("""\
            ```python
            #| source-code: mock
            not_executable()
            # ---
            hidden()
            ```
        """)
        result = expand_mock_cells(src)
        # Should be unchanged since it's not ```{python}
        assert result.strip() == src.strip()

    def test_multiline_display_and_eval(self):
        """Multi-line code in both display and eval regions."""
        src = textwrap.dedent("""\
            ```{python}
            #| source-code: mock
            import chatlas as ctl
            chat = ctl.ChatOpenAI()
            chat.chat("Hello")
            # ---
            import chatlas as ctl
            chat = ctl.ChatOpenAI(debug=True)
            chat.chat("Hello", header=False)
            ```
        """)
        result = expand_mock_cells(src)

        lines = result.split("\n")
        # Find display cell body
        in_display = False
        display_body = []
        for line in lines:
            if line.strip() == "#| eval: false":
                in_display = True
                continue
            if in_display and line.strip() == "```":
                break
            if in_display and not line.startswith("#|"):
                display_body.append(line)

        assert 'chat.chat("Hello")' in "\n".join(display_body)
        assert "debug=True" not in "\n".join(display_body)

    def test_multiple_delimiters_only_first_splits(self):
        """Only the first # --- delimiter is used to split."""
        src = textwrap.dedent("""\
            ```{python}
            #| source-code: mock
            display()
            # ---
            eval_line_1()
            # ---
            eval_line_2()
            ```
        """)
        result = expand_mock_cells(src)

        # eval_line_2 should be in the eval cell (after the split)
        assert "eval_line_1()" in result
        assert "eval_line_2()" in result
        # The second # --- should remain as part of the eval code
        # (it's just a comment in the eval section)

    def test_empty_eval_section(self):
        """Delimiter at the end with no eval code: display-only cell."""
        src = textwrap.dedent("""\
            ```{python}
            #| source-code: mock
            display()
            # ---
            ```
        """)
        result = expand_mock_cells(src)

        assert "#| eval: false" in result
        assert "display()" in result
        # No eval cell emitted (empty eval_lines)
        assert "#| echo: false" not in result

    def test_empty_display_section(self):
        """No code before delimiter: empty display cell, eval cell has code."""
        src = textwrap.dedent("""\
            ```{python}
            #| source-code: mock
            # ---
            hidden_eval()
            ```
        """)
        result = expand_mock_cells(src)

        assert "#| eval: false" in result
        assert "#| echo: false" in result
        assert "hidden_eval()" in result

    def test_echo_not_forwarded_to_display(self):
        """echo: option is not forwarded to the display cell."""
        src = textwrap.dedent("""\
            ```{python}
            #| source-code: mock
            #| echo: true
            show()
            # ---
            run()
            ```
        """)
        result = expand_mock_cells(src)
        lines = result.split("\n")

        # Find display cell section
        eval_false_idx = next(i for i, l in enumerate(lines) if "#| eval: false" in l)
        echo_false_idx = next(i for i, l in enumerate(lines) if "#| echo: false" in l)

        # Between eval: false and echo: false (the display cell),
        # there should be no echo: option
        display_section = lines[eval_false_idx:echo_false_idx]
        assert not any("#| echo:" in l for l in display_section)

    def test_preserves_surrounding_content(self):
        """YAML frontmatter, text, and other cells are preserved."""
        src = textwrap.dedent("""\
            ---
            title: "Test"
            ---

            # Introduction

            Some text.

            ```{python}
            normal_cell()
            ```

            ```{python}
            #| source-code: mock
            display()
            # ---
            eval()
            ```

            ## Conclusion

            Final text.
        """)
        result = expand_mock_cells(src)

        assert '---\ntitle: "Test"\n---' in result
        assert "# Introduction" in result
        assert "normal_cell()" in result
        assert "## Conclusion" in result
        assert "Final text." in result

    def test_no_mock_cells_returns_unchanged(self):
        """A file with no mock cells is returned unchanged."""
        src = textwrap.dedent("""\
            ---
            title: "No mocks"
            ---

            ```{python}
            x = 1
            ```
        """)
        result = expand_mock_cells(src)
        assert result == src


# ---------------------------------------------------------------------------
# process_qmd_file — file-level tests
# ---------------------------------------------------------------------------


class TestProcessQmdFile:
    """Test the file-level processing function."""

    def test_modifies_file_with_mock(self, tmp_path: Path):
        qmd = tmp_path / "test.qmd"
        qmd.write_text(
            textwrap.dedent("""\
                ```{python}
                #| source-code: mock
                a()
                # ---
                b()
                ```
            """),
            encoding="utf-8",
        )

        result = process_qmd_file(qmd)
        assert result is True

        content = qmd.read_text(encoding="utf-8")
        assert "#| eval: false" in content
        assert "#| echo: false" in content

    def test_skips_file_without_mock(self, tmp_path: Path):
        qmd = tmp_path / "test.qmd"
        original = textwrap.dedent("""\
            ```{python}
            x = 1
            ```
        """)
        qmd.write_text(original, encoding="utf-8")

        result = process_qmd_file(qmd)
        assert result is False
        assert qmd.read_text(encoding="utf-8") == original


# ---------------------------------------------------------------------------
# process_directory — directory-level tests
# ---------------------------------------------------------------------------


class TestProcessDirectory:
    """Test recursive directory processing."""

    def test_processes_nested_files(self, tmp_path: Path):
        # Create a file with mock code in a subdirectory
        subdir = tmp_path / "user-guide"
        subdir.mkdir()

        (subdir / "page.qmd").write_text(
            textwrap.dedent("""\
                ```{python}
                #| source-code: mock
                show()
                # ---
                run()
                ```
            """),
            encoding="utf-8",
        )

        # And a file without mock code
        (tmp_path / "index.qmd").write_text(
            textwrap.dedent("""\
                ```{python}
                normal()
                ```
            """),
            encoding="utf-8",
        )

        modified = process_directory(tmp_path)
        assert len(modified) == 1
        assert "user-guide/page.qmd" in modified[0] or "page.qmd" in modified[0]

    def test_empty_directory(self, tmp_path: Path):
        modified = process_directory(tmp_path)
        assert modified == []
