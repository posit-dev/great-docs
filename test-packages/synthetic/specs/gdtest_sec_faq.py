"""
gdtest_sec_faq — Custom "FAQ" section via config.

Dimensions: N5
Focus: Custom section with title "FAQ" sourced from faq/ directory.
"""

SPEC = {
    "name": "gdtest_sec_faq",
    "description": "Custom 'FAQ' section via sections config.",
    "dimensions": ["N5"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-sec-faq",
            "version": "0.1.0",
            "description": "Test custom FAQ section.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "sections": [
            {"title": "FAQ", "dir": "faq"},
        ],
    },
    "files": {
        "gdtest_sec_faq/__init__.py": '"""Test package for custom FAQ section."""\n',
        "gdtest_sec_faq/core.py": '''
            """Core ask/answer functions."""


            def ask(question: str) -> str:
                """Ask a question and get a response.

                Parameters
                ----------
                question : str
                    The question to ask.

                Returns
                -------
                str
                    A response to the question.

                Examples
                --------
                >>> ask("How do I install?")
                'See the installation guide.'
                """
                return "See the installation guide."


            def answer(question_id: int) -> str:
                """Retrieve the answer for a specific question by ID.

                Parameters
                ----------
                question_id : int
                    The numeric ID of the question.

                Returns
                -------
                str
                    The answer text for the given question ID.

                Examples
                --------
                >>> answer(1)
                'Use pip install to get started.'
                """
                return "Use pip install to get started."
        ''',
        "faq/installation.qmd": (
            "---\n"
            "title: Installation FAQ\n"
            "---\n"
            "\n"
            "# Installation FAQ\n"
            "\n"
            "Frequently asked questions about installing the package.\n"
        ),
        "faq/configuration.qmd": (
            "---\n"
            "title: Configuration FAQ\n"
            "---\n"
            "\n"
            "# Configuration FAQ\n"
            "\n"
            "Frequently asked questions about configuring the package.\n"
        ),
        "faq/troubleshooting.qmd": (
            "---\n"
            "title: Troubleshooting FAQ\n"
            "---\n"
            "\n"
            "# Troubleshooting FAQ\n"
            "\n"
            "Frequently asked questions about troubleshooting common issues.\n"
        ),
        "README.md": ("# gdtest-v2-sec-faq\n\nTest custom FAQ section.\n"),
    },
    "expected": {
        "detected_name": "gdtest-v2-sec-faq",
        "detected_module": "gdtest_sec_faq",
        "detected_parser": "numpy",
        "export_names": ["answer", "ask"],
        "num_exports": 2,
    },
}
