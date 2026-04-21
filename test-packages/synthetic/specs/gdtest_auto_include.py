"""
gdtest_auto_include — Force-include names that match AUTO_EXCLUDE.

Dimensions: A1, B7, C4, D1, E6, F6, G1, H7
Focus: __all__ includes names like "config", "logging", and "main" that are
       in the AUTO_EXCLUDE set. The great-docs.yml ``auto_include`` option
       forces "config" and "logging" back into the documentation while "main"
       remains excluded. Validates that auto_include selectively overrides
       AUTO_EXCLUDE without disabling it entirely.
"""

SPEC = {
    "name": "gdtest_auto_include",
    "description": "Force-include AUTO_EXCLUDE names via auto_include config",
    "dimensions": ["A1", "B7", "C4", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-auto-include",
            "version": "0.1.0",
            "description": "A synthetic test package testing auto_include override of AUTO_EXCLUDE",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "auto_include": ["config", "logging"],
    },
    "files": {
        "gdtest_auto_include/__init__.py": '''\
            """A test package with auto_include overriding AUTO_EXCLUDE."""

            __version__ = "0.1.0"
            __all__ = ["Widget", "process", "config", "logging", "main"]


            class Widget:
                """
                A public widget class.

                Parameters
                ----------
                label
                    Widget label.
                """

                def __init__(self, label: str):
                    self.label = label

                def render(self) -> str:
                    """
                    Render the widget.

                    Returns
                    -------
                    str
                        Rendered HTML.
                    """
                    return f"<widget>{self.label}</widget>"


            def process(data: str) -> str:
                """
                Process input data.

                Parameters
                ----------
                data
                    Raw input data.

                Returns
                -------
                str
                    Processed data.
                """
                return data.strip()


            class config:
                """
                Configuration manager for the package.

                This is a real public API class that happens to be named ``config``
                — a name normally in AUTO_EXCLUDE. The ``auto_include`` option
                forces it back into documentation.

                Parameters
                ----------
                path
                    Configuration file path.
                """

                def __init__(self, path: str = "config.ini"):
                    self.path = path

                def load(self) -> dict:
                    """
                    Load configuration from file.

                    Returns
                    -------
                    dict
                        Loaded configuration values.
                    """
                    return {}


            class logging:
                """
                Logging facade for the package.

                This is a real public API class that happens to be named ``logging``
                — a name normally in AUTO_EXCLUDE. The ``auto_include`` option
                forces it back into documentation.

                Parameters
                ----------
                level
                    Default log level.
                """

                def __init__(self, level: str = "INFO"):
                    self.level = level

                def info(self, msg: str) -> None:
                    """
                    Log an informational message.

                    Parameters
                    ----------
                    msg
                        The message to log.
                    """
                    pass


            def main():
                """CLI entry point — should still be auto-excluded."""
                pass
        ''',
        "README.md": """\
            # gdtest-auto-include

            A synthetic test package testing auto_include override of AUTO_EXCLUDE.
        """,
    },
    "expected": {
        "detected_name": "gdtest-auto-include",
        "detected_module": "gdtest_auto_include",
        "detected_parser": "numpy",
        "export_names": ["Widget", "process", "config", "logging"],
        "auto_excluded": ["main"],
        "force_included": ["config", "logging"],
        "has_user_guide": False,
    },
}
