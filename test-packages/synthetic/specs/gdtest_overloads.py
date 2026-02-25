"""
gdtest_overloads — @overload typed functions.

Dimensions: A1, B1, C15, D1, E6, F6, G1, H7
Focus: Functions with @typing.overload decorators. Tests that overloaded
       signatures render without errors. Also tests that RST-style ``::``
       code blocks in docstrings are converted to Markdown fenced blocks.
"""

SPEC = {
    "name": "gdtest_overloads",
    "description": "Functions with @overload signatures",
    "dimensions": ["A1", "B1", "C15", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-overloads",
            "version": "0.1.0",
            "description": "Test overloaded function documentation",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_overloads/__init__.py": '''\
            """Package with @overload decorated functions."""

            from typing import overload, Union

            __version__ = "0.1.0"
            __all__ = ["process", "convert", "transform"]


            @overload
            def process(data: str) -> str: ...

            @overload
            def process(data: int) -> int: ...

            @overload
            def process(data: list) -> list: ...

            def process(data):
                """
                Process data of varying types.

                Parameters
                ----------
                data
                    Input data — can be str, int, or list.

                Returns
                -------
                str or int or list
                    Processed output, same type as input.
                """
                return data


            @overload
            def convert(value: str, to: type) -> int: ...

            @overload
            def convert(value: int, to: type) -> str: ...

            def convert(value, to=str):
                """
                Convert a value to a different type.

                Parameters
                ----------
                value
                    The value to convert.
                to
                    Target type.

                Returns
                -------
                int or str
                    Converted value.
                """
                return to(value)


            def transform(data, mode="upper"):
                """
                Transform data with a given mode.

                This function applies a transformation. Example::

                    result = transform("hello", mode="upper")
                    print(result)

                You can also chain transformations::

                    step1 = transform("hello", mode="upper")
                    step2 = transform(step1, mode="reverse")

                Parameters
                ----------
                data
                    The input data to transform.
                mode
                    Transformation mode (``"upper"``, ``"lower"``, or ``"reverse"``).

                Returns
                -------
                str
                    The transformed string.
                """
                if mode == "upper":
                    return str(data).upper()
                elif mode == "lower":
                    return str(data).lower()
                elif mode == "reverse":
                    return str(data)[::-1]
                return str(data)
        ''',
        "README.md": """\
            # gdtest-overloads

            Tests documentation of @overload decorated functions.
        """,
    },
    "expected": {
        "detected_name": "gdtest-overloads",
        "detected_module": "gdtest_overloads",
        "detected_parser": "numpy",
        "export_names": ["process", "convert", "transform"],
        "num_exports": 3,
        "section_titles": ["Functions"],
        "has_user_guide": False,
    },
}
