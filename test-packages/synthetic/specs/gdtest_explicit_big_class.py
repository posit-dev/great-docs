"""
gdtest_explicit_big_class — Explicit reference config + big class (members: false).

Dimensions: A1, B1, C3, D1, E6, F6, G1, H7
Focus: Explicit reference config that suppresses big-class method listing
       via members: false, verifying that the method section is absent.
"""

SPEC = {
    "name": "gdtest_explicit_big_class",
    "description": "Explicit reference with big class members suppressed",
    "dimensions": ["A1", "B1", "C3", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-explicit-big-class",
            "version": "0.1.0",
            "description": "Test explicit reference with big class members=false",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "reference": [
            {
                "title": "Core",
                "members": [
                    {"name": "BigEngine", "members": False},
                ],
            },
            {
                "title": "Helpers",
                "members": [
                    "helper_a",
                    "helper_b",
                ],
            },
        ],
    },
    "files": {
        "gdtest_explicit_big_class/__init__.py": '''\
            """Package with explicit reference and big class."""

            __version__ = "0.1.0"
            __all__ = ["BigEngine", "helper_a", "helper_b"]


            class BigEngine:
                """
                A complex engine with many methods.

                Parameters
                ----------
                config
                    Configuration dictionary.
                """

                def __init__(self, config: dict):
                    self.config = config

                def start(self) -> None:
                    """Start the engine."""
                    pass

                def stop(self) -> None:
                    """Stop the engine."""
                    pass

                def restart(self) -> None:
                    """Restart the engine."""
                    pass

                def configure(self, key: str, value) -> None:
                    """
                    Configure a setting.

                    Parameters
                    ----------
                    key
                        Setting key.
                    value
                        Setting value.
                    """
                    pass

                def status(self) -> str:
                    """
                    Get engine status.

                    Returns
                    -------
                    str
                        Status string.
                    """
                    return "running"

                def metrics(self) -> dict:
                    """
                    Get performance metrics.

                    Returns
                    -------
                    dict
                        Metrics dictionary.
                    """
                    return {}

                def health_check(self) -> bool:
                    """
                    Run health check.

                    Returns
                    -------
                    bool
                        True if healthy.
                    """
                    return True


            def helper_a(x: int) -> int:
                """
                Helper function A.

                Parameters
                ----------
                x
                    Input value.

                Returns
                -------
                int
                    Processed value.
                """
                return x + 1


            def helper_b(x: int) -> int:
                """
                Helper function B.

                Parameters
                ----------
                x
                    Input value.

                Returns
                -------
                int
                    Processed value.
                """
                return x * 2
        ''',
        "README.md": """\
            # gdtest-explicit-big-class

            Tests explicit reference with members=false on a big class.
        """,
    },
    "expected": {
        "detected_name": "gdtest-explicit-big-class",
        "detected_module": "gdtest_explicit_big_class",
        "detected_parser": "numpy",
        "export_names": ["BigEngine", "helper_a", "helper_b"],
        "num_exports": 3,
        "section_titles": ["Classes", "BigEngine Methods", "Functions"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
