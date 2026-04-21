"""
gdtest_no_auto_exclude — Bypass the AUTO_EXCLUDE list entirely.

Dimensions: A1, B7, C4, D1, E6, F6, G1, H7
Focus: __all__ includes names like "main", "cli", "config", "utils", "logger"
       that are in the AUTO_EXCLUDE set. The great-docs.yml ``no_auto_exclude``
       option is set to true, so ALL names pass through — none are
       automatically excluded. Validates that the entire AUTO_EXCLUDE filter
       can be disabled.
"""

SPEC = {
    "name": "gdtest_no_auto_exclude",
    "description": "Bypass AUTO_EXCLUDE entirely via no_auto_exclude config",
    "dimensions": ["A1", "B7", "C4", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-no-auto-exclude",
            "version": "0.1.0",
            "description": "A synthetic test package testing no_auto_exclude bypass",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "no_auto_exclude": True,
    },
    "files": {
        "gdtest_no_auto_exclude/__init__.py": '''\
            """A test package with no_auto_exclude: true."""

            __version__ = "0.1.0"
            __all__ = ["Adapter", "run", "main", "config", "logger"]


            class Adapter:
                """
                A public adapter class.

                Parameters
                ----------
                backend
                    Backend identifier.
                """

                def __init__(self, backend: str):
                    self.backend = backend

                def connect(self) -> bool:
                    """
                    Connect to the backend.

                    Returns
                    -------
                    bool
                        Whether connection succeeded.
                    """
                    return True


            def run(data: str) -> str:
                """
                Run a processing pipeline.

                Parameters
                ----------
                data
                    Input data string.

                Returns
                -------
                str
                    Processed output.
                """
                return data.upper()


            def main():
                """
                CLI entry point.

                Normally auto-excluded, but present because no_auto_exclude is true.

                Returns
                -------
                None
                """
                pass


            class config:
                """
                Configuration manager.

                Normally auto-excluded, but present because no_auto_exclude is true.

                Parameters
                ----------
                path
                    Config file path.
                """

                def __init__(self, path: str = "settings.ini"):
                    self.path = path

                def read(self) -> dict:
                    """
                    Read configuration.

                    Returns
                    -------
                    dict
                        Configuration values.
                    """
                    return {}


            def logger():
                """
                Create a logger instance.

                Normally auto-excluded, but present because no_auto_exclude is true.

                Returns
                -------
                None
                """
                pass
        ''',
        "README.md": """\
            # gdtest-no-auto-exclude

            A synthetic test package testing no_auto_exclude bypass.
        """,
    },
    "expected": {
        "detected_name": "gdtest-no-auto-exclude",
        "detected_module": "gdtest_no_auto_exclude",
        "detected_parser": "numpy",
        "export_names": ["Adapter", "run", "main", "config", "logger"],
        "auto_excluded": [],
        "has_user_guide": False,
    },
}
