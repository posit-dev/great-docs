"""
gdtest_sec_with_ug — Custom Examples section combined with auto-discovered user guide.

Dimensions: N1, M1
Focus: Custom section coexisting with auto-discovered user guide pages.
"""

SPEC = {
    "name": "gdtest_sec_with_ug",
    "description": "Custom Examples section combined with auto-discovered user guide.",
    "dimensions": ["N1", "M1"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-sec-with-ug",
            "version": "0.1.0",
            "description": "Test custom section with auto-discovered user guide.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "sections": [
            {"title": "Examples", "dir": "examples"},
        ],
    },
    "files": {
        "gdtest_sec_with_ug/__init__.py": '"""Test package for custom section with user guide."""\n',
        "gdtest_sec_with_ug/core.py": '''
            """Core run_example/guide_user functions."""


            def run_example() -> str:
                """Run the example and return a result message.

                Returns
                -------
                str
                    A message indicating the example ran successfully.

                Examples
                --------
                >>> run_example()
                'Example complete'
                """
                return "Example complete"


            def guide_user(topic: str) -> str:
                """Guide the user through a specific topic.

                Parameters
                ----------
                topic : str
                    The topic to guide the user through.

                Returns
                -------
                str
                    A guidance message for the topic.

                Examples
                --------
                >>> guide_user("setup")
                'Guide: setup'
                """
                return f"Guide: {topic}"
        ''',
        "user_guide/intro.qmd": (
            "---\ntitle: Introduction\n---\n\n# Introduction\n\nAn introduction to the project.\n"
        ),
        "user_guide/usage.qmd": (
            "---\ntitle: Usage Guide\n---\n\n# Usage Guide\n\nHow to use the project effectively.\n"
        ),
        "examples/demo.qmd": (
            "---\ntitle: Demo\n---\n\n# Demo\n\nA demonstration of the package features.\n"
        ),
        "README.md": (
            "# gdtest-v2-sec-with-ug\n\nTest custom section with auto-discovered user guide.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-v2-sec-with-ug",
        "detected_module": "gdtest_sec_with_ug",
        "detected_parser": "numpy",
        "export_names": ["guide_user", "run_example"],
        "num_exports": 2,
    },
}
