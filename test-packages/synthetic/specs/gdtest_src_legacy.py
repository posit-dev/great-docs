"""
gdtest_src_legacy — src/ layout with legacy setup.py only.

Dimensions: A2, A8, B1, C1, D1, E6, F6, G1, H7
Focus: Module at src/ discovered with only a setup.py (no pyproject.toml).
       Tests both src/ scanning and setup.py metadata fallback together.
"""

SPEC = {
    "name": "gdtest_src_legacy",
    "description": "src/ layout with setup.py only",
    "dimensions": ["A2", "A8", "B1", "C1", "D1", "E6", "F6", "G1", "H7"],
    "setup_py": """\
from setuptools import setup, find_packages

setup(
    name="gdtest-src-legacy",
    version="0.1.0",
    description="Test src/ layout with legacy setup.py",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
)
""",
    "files": {
        "src/gdtest_src_legacy/__init__.py": '''\
            """Package in src/ layout with setup.py only."""

            __version__ = "0.1.0"
            __all__ = ["legacy_init", "legacy_run"]


            def legacy_init(config: dict = None) -> dict:
                """
                Initialize with legacy configuration.

                Parameters
                ----------
                config
                    Configuration dictionary.

                Returns
                -------
                dict
                    Initialized config.
                """
                return config or {}


            def legacy_run(task: str) -> str:
                """
                Run a legacy task.

                Parameters
                ----------
                task
                    Task name.

                Returns
                -------
                str
                    Task result.
                """
                return f"ran {task}"
        ''',
        "README.md": """\
            # gdtest-src-legacy

            Tests src/ layout with legacy setup.py metadata.
        """,
    },
    "expected": {
        "detected_name": "gdtest-src-legacy",
        "detected_module": "gdtest_src_legacy",
        "detected_parser": "numpy",
        "export_names": ["legacy_init", "legacy_run"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
