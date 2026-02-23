"""
gdtest_ug_deep_nest — Deeply nested user guide structure.

Dimensions: M6
Focus: User guide with multiple levels of nested subdirectories.
"""

SPEC = {
    "name": "gdtest_ug_deep_nest",
    "description": "Deeply nested user guide with multi-level subdirectory structure.",
    "dimensions": ["M6"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-ug-deep-nest",
            "version": "0.1.0",
            "description": "Test deeply nested user guide structure.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_ug_deep_nest/__init__.py": '"""Test package for deeply nested user guide."""\n',
        "gdtest_ug_deep_nest/core.py": '''
            """Core drill_down/summarize functions."""


            def drill_down(path: str) -> list:
                """Drill down into a nested data path.

                Parameters
                ----------
                path : str
                    A dot-separated path to drill into.

                Returns
                -------
                list
                    The items found at the given path.

                Examples
                --------
                >>> drill_down("section1.topic1")
                ['details']
                """
                return []


            def summarize(data: list) -> str:
                """Summarize a list of data items into a string.

                Parameters
                ----------
                data : list
                    The data items to summarize.

                Returns
                -------
                str
                    A summary string of the data.

                Examples
                --------
                >>> summarize(["a", "b", "c"])
                'a, b, c'
                """
                return ", ".join(str(x) for x in data)
        ''',
        "user_guide/section1/topic1/details.qmd": (
            "---\n"
            "title: Topic 1 Details\n"
            "---\n"
            "\n"
            "# Topic 1 Details\n"
            "\n"
            "Detailed information about topic 1 in section 1.\n"
        ),
        "user_guide/section1/topic2/overview.qmd": (
            "---\n"
            "title: Topic 2 Overview\n"
            "---\n"
            "\n"
            "# Topic 2 Overview\n"
            "\n"
            "An overview of topic 2 in section 1.\n"
        ),
        "user_guide/section2/intro.qmd": (
            "---\n"
            "title: Section 2 Introduction\n"
            "---\n"
            "\n"
            "# Section 2 Introduction\n"
            "\n"
            "Introduction to the second section of the guide.\n"
        ),
    },
    "expected": {
        "files_exist": [
            "great-docs/user-guide/section1/topic1/details.html",
            "great-docs/user-guide/section1/topic2/overview.html",
            "great-docs/user-guide/section2/intro.html",
        ],
        "files_contain": {
            "great-docs/user-guide/section1/topic1/details.html": ["Topic 1 Details"],
            "great-docs/user-guide/section1/topic2/overview.html": ["Topic 2 Overview"],
            "great-docs/user-guide/section2/intro.html": ["Section 2 Introduction"],
        },
    },
}
