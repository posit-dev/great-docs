"""
gdtest_mock_code — Mock code cells and output-title containers.

Dimensions: A1, B1, C1, D1, E6, F6, G1, H7
Focus: Tests the ``source-code: mock`` preprocessor and ``output-title``
       Lua filter working together.  User-guide pages exercise:
       • Basic mock cell split (display + eval)
       • Mock cell with ``output-title``
       • Standalone ``output-title`` on a regular executable cell
       • Mock cell with no delimiter (display-only)
       • Multiple mock cells on one page
       • Mock cell with extra forwarded options
"""

SPEC = {
    "name": "gdtest_mock_code",
    "description": "Mock code cells and output-title containers",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F6", "G1", "H7"],
    # ── Project metadata ─────────────────────────────────────────────
    "pyproject_toml": {
        "project": {
            "name": "gdtest-mock-code",
            "version": "0.1.0",
            "description": "Synthetic test for mock code cells and output-title",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    # ── Source files ──────────────────────────────────────────────────
    "files": {
        "gdtest_mock_code/__init__.py": '''\
            """Test package for mock code cells and output-title."""

            __version__ = "0.1.0"
            __all__ = ["add", "multiply", "greet"]


            def add(a: int, b: int) -> int:
                """
                Add two numbers.

                Parameters
                ----------
                a
                    First number.
                b
                    Second number.

                Returns
                -------
                int
                    Sum of a and b.

                Examples
                --------
                ```python
                from gdtest_mock_code import add

                add(2, 3)
                ```
                """
                return a + b


            def multiply(a: int, b: int) -> int:
                """
                Multiply two numbers.

                Parameters
                ----------
                a
                    First number.
                b
                    Second number.

                Returns
                -------
                int
                    Product of a and b.
                """
                return a * b


            def greet(name: str) -> str:
                """
                Greet someone by name.

                Parameters
                ----------
                name
                    The person to greet.

                Returns
                -------
                str
                    A greeting string.
                """
                return f"Hello, {name}!"
        ''',
        # ── User guide pages ──────────────────────────────────────────
        "user_guide/01-basic-mock.qmd": """\
            ---
            title: Basic Mock Cell
            ---

            A basic mock cell splits display code from eval code.

            ```{python}
            #| source-code: mock
            import gdtest_mock_code

            gdtest_mock_code.add(10, 20)
            # ---
            from gdtest_mock_code import add
            add(10, 20)
            ```

            The reader sees `gdtest_mock_code.add(10, 20)` but the cell
            actually runs `from gdtest_mock_code import add; add(10, 20)`.
        """,
        "user_guide/02-mock-output-title.qmd": """\
            ---
            title: Mock with Output Title
            ---

            Combines `source-code: mock` with `output-title`.

            ```{python}
            #| source-code: mock
            #| output-title: Addition Result
            gdtest_mock_code.add(3, 4)
            # ---
            from gdtest_mock_code import add
            add(3, 4)
            ```

            The output should appear inside a titled container
            labelled "Addition Result".
        """,
        "user_guide/03-standalone-output-title.qmd": """\
            ---
            title: Standalone Output Title
            ---

            `output-title` works on regular (non-mock) executable cells too.

            ```{python}
            #| output-title: Greeting Output
            from gdtest_mock_code import greet
            greet("World")
            ```

            The output should appear inside a titled container
            labelled "Greeting Output".
        """,
        "user_guide/04-no-delimiter.qmd": """\
            ---
            title: No Delimiter Mock
            ---

            A mock cell with no `# ---` delimiter is display-only
            (equivalent to `eval: false`).

            ```{python}
            #| source-code: mock
            gdtest_mock_code.multiply(6, 7)
            ```

            There is no eval cell emitted, so no output appears.
        """,
        "user_guide/05-multiple-mocks.qmd": """\
            ---
            title: Multiple Mock Cells
            ---

            A page with several mock cells interleaved with prose.

            ## First calculation

            ```{python}
            #| source-code: mock
            gdtest_mock_code.add(1, 2)
            # ---
            from gdtest_mock_code import add
            add(1, 2)
            ```

            ## Second calculation

            ```{python}
            #| source-code: mock
            #| output-title: Product
            gdtest_mock_code.multiply(3, 4)
            # ---
            from gdtest_mock_code import multiply
            multiply(3, 4)
            ```

            ## Third — a greeting

            ```{python}
            #| source-code: mock
            #| output-title: Greeting
            gdtest_mock_code.greet("GDG")
            # ---
            from gdtest_mock_code import greet
            greet("GDG")
            ```
        """,
        "user_guide/06-html-repr-output-title.qmd": """\
            ---
            title: HTML Repr with Output Title
            ---

            When `output-title` wraps a rich HTML object like a GT table
            the container should go frameless — no double border.

            ### GT table with output-title

            ```{python}
            #| source-code: mock
            #| output-title: Example Table
            import great_tables as gt
            import pandas as pd

            gt.GT(pd.DataFrame({"x": [1, 2], "y": [3, 4]}))
            # ---
            from great_tables import GT
            import pandas as pd

            GT(pd.DataFrame({"x": [1, 2], "y": [3, 4]}))
            ```

            ### GT table without output-title (baseline)

            ```{python}
            #| source-code: mock
            import great_tables as gt
            import pandas as pd

            gt.GT(pd.DataFrame({"a": [10, 20], "b": [30, 40]}))
            # ---
            from great_tables import GT
            import pandas as pd

            GT(pd.DataFrame({"a": [10, 20], "b": [30, 40]}))
            ```

            ### Plain text with output-title (framed)

            ```{python}
            #| output-title: Text Output
            from gdtest_mock_code import greet
            greet("comparison")
            ```

            The GT table with output-title should show a floating label
            with no frame.  The baseline GT table (no output-title) should
            render identically to any other GT table.  The text output
            should keep its frame.
        """,
        "user_guide/07-output-frame.qmd": """\
            ---
            title: Output Frame (No Title)
            ---

            The `output-frame` option adds a bordered container around
            cell output without a title label.

            ### Framed output (no title)

            ```{python}
            #| output-frame: true
            from gdtest_mock_code import greet
            greet("framed")
            ```

            ### Framed output with mock cell

            ```{python}
            #| source-code: mock
            #| output-frame: true
            gdtest_mock_code.add(5, 5)
            # ---
            from gdtest_mock_code import add
            add(5, 5)
            ```

            ### Unframed output (baseline)

            ```{python}
            from gdtest_mock_code import greet
            greet("no frame")
            ```

            The first two outputs should have a border but no title
            header.  The third should render as a normal cell output.
        """,
        "README.md": """\
            # gdtest-mock-code

            Synthetic test for `source-code: mock` and `output-title`.

            ## Purpose

            Tests that Great Docs correctly:

            - Splits mock cells into display + eval pairs
            - Wraps output in titled containers when `output-title` is set
            - Frames output without a title when `output-frame: true` is set
            - Handles `output-title` on non-mock cells
            - Handles mock cells with no delimiter (display-only)
            - Handles multiple mock cells on one page
            - Goes frameless for rich HTML outputs (GT tables)
        """,
    },
    # ── Expected outcomes ─────────────────────────────────────────────
    "expected": {
        "detected_name": "gdtest-mock-code",
        "detected_module": "gdtest_mock_code",
        "detected_parser": "numpy",
        "export_names": ["add", "multiply", "greet"],
        "num_exports": 3,
        "section_titles": ["Functions"],
        "has_user_guide": True,
        "has_license_page": False,
        "has_citation_page": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
