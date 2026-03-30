"""
gdtest_code_cells — Executable code cells in docstring Examples.

Dimensions: A1, B1, C1, D1, E6, F6, G1, H7
Focus: Functions with docstring Examples using Quarto executable cell syntax
       (```{python}) and hash-pipe options (#| eval: false).
       Verifies that Great Docs preserves executable cell syntax in API
       reference pages so Quarto can execute them during the build.
"""

SPEC = {
    "name": "gdtest_code_cells",
    "description": "Executable code cells in docstring examples",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F6", "G1", "H7"],
    # ── Project metadata ─────────────────────────────────────────────
    "pyproject_toml": {
        "project": {
            "name": "gdtest-code-cells",
            "version": "0.1.0",
            "description": "Synthetic test for executable code cells in docstrings",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    # ── Source files ──────────────────────────────────────────────────
    "files": {
        "gdtest_code_cells/__init__.py": '''\
            """Test package for executable code cells in API reference."""

            __version__ = "0.1.0"
            __all__ = ["add", "multiply", "greet", "fibonacci"]


            def add(a: int, b: int) -> int:
                """
                Add two numbers.

                This function uses an executable code cell that should be
                run by Quarto during the build.

                Parameters
                ----------
                a
                    First number.
                b
                    Second number.

                Returns
                -------
                int
                    The sum of a and b.

                Examples
                --------
                ```{python}
                from gdtest_code_cells import add

                add(2, 3)
                ```
                """
                return a + b


            def multiply(a: int, b: int) -> int:
                """
                Multiply two numbers.

                This function uses an executable code cell with
                ``#| eval: false`` so the code is displayed but not run.

                Parameters
                ----------
                a
                    First number.
                b
                    Second number.

                Returns
                -------
                int
                    The product of a and b.

                Examples
                --------
                ```{python}
                #| eval: false
                from gdtest_code_cells import multiply

                result = multiply(4, 5)
                print(f"4 x 5 = {result}")
                ```
                """
                return a * b


            def greet(name: str) -> str:
                """
                Greet someone by name.

                This function uses a static code block (no curly braces)
                that should NOT be executed by Quarto.

                Parameters
                ----------
                name
                    The name of the person to greet.

                Returns
                -------
                str
                    A greeting string.

                Examples
                --------
                ```python
                from gdtest_code_cells import greet

                greet("World")
                ```
                """
                return f"Hello, {name}!"


            def fibonacci(n: int) -> list[int]:
                """
                Generate the first n Fibonacci numbers.

                This function demonstrates multiple code blocks: one
                executable and one with ``#| eval: false``.

                Parameters
                ----------
                n
                    How many Fibonacci numbers to generate.

                Returns
                -------
                list[int]
                    The first n Fibonacci numbers.

                Examples
                --------
                An executed cell showing output:

                ```{python}
                from gdtest_code_cells import fibonacci

                fibonacci(8)
                ```

                A non-executed cell with multiple hash-pipe options:

                ```{python}
                #| eval: false
                #| echo: true
                # Generate a large sequence
                big = fibonacci(100)
                print(f"The 100th Fibonacci number is {big[-1]}")
                ```
                """
                if n <= 0:
                    return []
                fibs = [0, 1]
                while len(fibs) < n:
                    fibs.append(fibs[-1] + fibs[-2])
                return fibs[:n]
        ''',
        "README.md": """\
            # gdtest-code-cells

            Synthetic test for executable code cells in docstring examples.

            ## Purpose

            Tests that Great Docs preserves Quarto executable cell syntax:

            - ```` ```{python} ```` — cell is executed, output shown
            - ```` ```{python}\\n#| eval: false ```` — code shown, not executed
            - ```` ```python ```` — static display, no execution
        """,
    },
    # ── Expected outcomes ─────────────────────────────────────────────
    "expected": {
        "detected_name": "gdtest-code-cells",
        "detected_module": "gdtest_code_cells",
        "detected_parser": "numpy",
        "export_names": ["add", "multiply", "greet", "fibonacci"],
        "num_exports": 4,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "has_license_page": False,
        "has_citation_page": False,
    },
}
