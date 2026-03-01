"""
gdtest_ug_with_code — User guide pages with Python code blocks.

Dimensions: M12
Focus: User guide containing fenced Python code blocks.
"""

SPEC = {
    "name": "gdtest_ug_with_code",
    "description": "User guide pages with fenced Python code blocks.",
    "dimensions": ["M12"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-ug-with-code",
            "version": "0.1.0",
            "description": "Test user guide with code blocks.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_ug_with_code/__init__.py": (
            '"""Test package for user guide with code blocks."""\n'
            '\n'
            'from .core import process, transform\n'
            '\n'
            '__all__ = ["process", "transform"]\n'
        ),
        "gdtest_ug_with_code/core.py": '''
            """Core process/transform functions."""


            def process(data: list) -> list:
                """Process a list of data items.

                Parameters
                ----------
                data : list
                    The input data to process.

                Returns
                -------
                list
                    The processed data.

                Examples
                --------
                >>> process([1, 2, 3])
                [2, 4, 6]
                """
                return [x * 2 for x in data]


            def transform(data: dict) -> dict:
                """Transform a dictionary of data.

                Parameters
                ----------
                data : dict
                    The input dictionary to transform.

                Returns
                -------
                dict
                    The transformed dictionary.

                Examples
                --------
                >>> transform({"key": "value"})
                {'key': 'VALUE'}
                """
                return {k: v.upper() if isinstance(v, str) else v for k, v in data.items()}
        ''',
        "user_guide/tutorial.qmd": (
            "---\n"
            "title: Tutorial\n"
            "---\n"
            "\n"
            "# Getting Started\n"
            "\n"
            "Here's a basic example that runs and prints output:\n"
            "\n"
            "```{python}\n"
            "from gdtest_ug_with_code.core import process\n"
            "\n"
            "result = process([1, 2, 3])\n"
            "print(result)\n"
            "```\n"
            "\n"
            "And a fenced (non-executable) code block showing a transform:\n"
            "\n"
            "```python\n"
            "from gdtest_ug_with_code.core import transform\n"
            "\n"
            'data = {"key": "value"}\n'
            "output = transform(data)\n"
            "print(output)  # {'key': 'VALUE'}\n"
            "```\n"
        ),
        "README.md": ("# gdtest-ug-with-code\n\nTest user guide with Python code blocks.\n"),
    },
    "expected": {
        "files_exist": [
            "great-docs/user-guide/tutorial.html",
            "great-docs/reference/index.html",
        ],
        "files_contain": {
            "great-docs/user-guide/tutorial.html": [
                "Tutorial",
                "Getting Started",
                "runs and prints output",
                "[2, 4, 6]",
                "fenced (non-executable)",
            ],
            "great-docs/reference/index.html": [
                "process",
                "transform",
            ],
        },
    },
}
