"""
gdtest_setup_py — Legacy setup.py-only package.

Dimensions: A8, B1, C1, D1, E6, F6, G1, H7
Focus: No pyproject.toml — only setup.py with name="..." in setup() call.
       Tests _detect_package_name setup.py regex extraction.
"""

SPEC = {
    "name": "gdtest_setup_py",
    "description": "Legacy setup.py only — no pyproject.toml",
    "dimensions": ["A8", "B1", "C1", "D1", "E6", "F6", "G1", "H7"],
    # No pyproject_toml — this package uses setup.py
    "setup_py": """\
from setuptools import setup, find_packages

setup(
    name="gdtest-setup-py",
    version="0.1.0",
    description="A synthetic test package using setup.py only",
    packages=find_packages(),
    python_requires=">=3.9",
)
""",
    "files": {
        "gdtest_setup_py/__init__.py": '''\
            """A test package using legacy setup.py."""

            __version__ = "0.1.0"
            __all__ = ["echo", "reverse"]


            def echo(text: str) -> str:
                """
                Echo the input text.

                Parameters
                ----------
                text
                    The text to echo.

                Returns
                -------
                str
                    The same text.
                """
                return text


            def reverse(text: str) -> str:
                """
                Reverse the input text.

                Parameters
                ----------
                text
                    The text to reverse.

                Returns
                -------
                str
                    The reversed text.
                """
                return text[::-1]
        ''',
        "README.md": """\
            # gdtest-setup-py

            A synthetic test package using legacy ``setup.py``.
        """,
    },
    "expected": {
        "detected_name": "gdtest-setup-py",
        "detected_module": "gdtest_setup_py",
        "detected_parser": "numpy",
        "export_names": ["echo", "reverse"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp"],
    },
}
