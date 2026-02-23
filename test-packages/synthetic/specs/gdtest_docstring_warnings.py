"""
gdtest_docstring_warnings — Warnings sections in NumPy-style docstrings.

Dimensions: L20
Focus: Two functions with Warnings sections highlighting dangerous or
       surprising behavior.
"""

SPEC = {
    "name": "gdtest_docstring_warnings",
    "description": "Warnings sections in NumPy-style docstrings",
    "dimensions": ["L20"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-docstring-warnings",
            "version": "0.1.0",
            "description": "Test Warnings section rendering",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "parser": "numpy",
    },
    "files": {
        "gdtest_docstring_warnings/__init__.py": '''\
            """Package with Warnings sections in docstrings."""

            __version__ = "0.1.0"
            __all__ = ["unsafe_eval", "mutable_default"]


            def unsafe_eval(expr: str) -> object:
                """
                Evaluate a Python expression string and return the result.

                Parses and evaluates the given expression string using
                Python's built-in ``eval()`` function.

                Parameters
                ----------
                expr
                    A string containing a valid Python expression.

                Returns
                -------
                object
                    The result of evaluating the expression.

                Raises
                ------
                SyntaxError
                    If the expression string is not valid Python.
                NameError
                    If the expression references undefined names.

                Warnings
                --------
                Never use with untrusted input. This function uses ``eval()``
                internally and can execute arbitrary Python code. An attacker
                could craft an expression that deletes files, exfiltrates
                data, or compromises the system.

                Examples
                --------
                >>> unsafe_eval("2 + 3")
                5

                >>> unsafe_eval("[i**2 for i in range(5)]")
                [0, 1, 4, 9, 16]
                """
                return eval(expr)


            def mutable_default(items: list = None) -> list:
                """
                Append a marker value to a list and return it.

                If no list is provided, an internal default list is used.
                Appends the string ``"added"`` to the list and returns it.

                Parameters
                ----------
                items
                    A list to append to. If ``None``, a new empty list
                    is created for each call.

                Returns
                -------
                list
                    The list with ``"added"`` appended.

                Warnings
                --------
                If you modify this function to use a mutable default argument
                (e.g., ``items=[]``), the default empty list would be shared
                across all calls that omit the argument. Each call would
                mutate the same list object, leading to surprising
                accumulation of values.

                Always use ``None`` as the default and create a new list
                inside the function body to avoid this pitfall.

                Examples
                --------
                >>> mutable_default()
                ['added']

                >>> mutable_default(["existing"])
                ['existing', 'added']
                """
                if items is None:
                    items = []
                items.append("added")
                return items
        ''',
        "README.md": """\
            # gdtest-v2-docstring-warnings

            A synthetic test package with Warnings sections.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-docstring-warnings",
        "detected_module": "gdtest_docstring_warnings",
        "detected_parser": "numpy",
        "export_names": ["mutable_default", "unsafe_eval"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
    },
}
