"""
gdtest_ug_mixed_ext — User guide with mixed file extensions.

Dimensions: M7
Focus: User guide containing both .qmd and .md files.
"""

SPEC = {
    "name": "gdtest_ug_mixed_ext",
    "description": "User guide with mixed .qmd and .md file extensions.",
    "dimensions": ["M7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-ug-mixed-ext",
            "version": "0.1.0",
            "description": "Test mixed file extensions in user guide.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_ug_mixed_ext/__init__.py": '"""Test package for mixed extension user guide."""\n',
        "gdtest_ug_mixed_ext/core.py": '''
            """Core mix/split functions."""


            def mix(a: list, b: list) -> list:
                """Mix two lists by interleaving their elements.

                Parameters
                ----------
                a : list
                    The first list.
                b : list
                    The second list.

                Returns
                -------
                list
                    A new list with elements interleaved from both inputs.

                Examples
                --------
                >>> mix([1, 2], [3, 4])
                [1, 3, 2, 4]
                """
                result = []
                for x, y in zip(a, b):
                    result.extend([x, y])
                return result


            def split(data: list) -> tuple:
                """Split a list into two halves.

                Parameters
                ----------
                data : list
                    The list to split.

                Returns
                -------
                tuple
                    A tuple of two lists representing the halves.

                Examples
                --------
                >>> split([1, 2, 3, 4])
                ([1, 2], [3, 4])
                """
                mid = len(data) // 2
                return (data[:mid], data[mid:])
        ''',
        "user_guide/intro.qmd": (
            "---\n"
            "title: Introduction\n"
            "---\n"
            "\n"
            "# Introduction\n"
            "\n"
            "This is the introduction written in Quarto format.\n"
        ),
        "user_guide/setup.md": (
            "---\n"
            "title: Setup\n"
            "---\n"
            "\n"
            "# Setup\n"
            "\n"
            "This is the setup guide written in plain Markdown.\n"
        ),
        "user_guide/advanced.qmd": (
            "---\ntitle: Advanced\n---\n\n# Advanced\n\nAdvanced topics written in Quarto format.\n"
        ),
    },
    "expected": {
        "files_exist": [
            "great-docs/user-guide/intro.html",
            "great-docs/user-guide/setup.html",
            "great-docs/user-guide/advanced.html",
        ],
        "files_contain": {
            "great-docs/user-guide/intro.html": ["Introduction", "Quarto format"],
            "great-docs/user-guide/setup.html": ["Setup", "plain Markdown"],
            "great-docs/user-guide/advanced.html": ["Advanced"],
        },
    },
}
