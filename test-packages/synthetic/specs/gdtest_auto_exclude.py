"""
gdtest_auto_exclude — Exports with AUTO_EXCLUDE names.

Dimensions: A1, B7, C4, D1, E6, F6, G1, H7
Focus: __all__ includes names like "main", "cli", "config", "utils", "logger"
       that are in the AUTO_EXCLUDE set. Tests that auto-exclusion filtering
       removes these while keeping real exports.
"""

SPEC = {
    "name": "gdtest_auto_exclude",
    "description": "Exports include AUTO_EXCLUDE names (main, cli, config, etc.)",
    "dimensions": ["A1", "B7", "C4", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-auto-exclude",
            "version": "0.1.0",
            "description": "A synthetic test package testing AUTO_EXCLUDE filtering",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_auto_exclude/__init__.py": '''\
            """A test package with AUTO_EXCLUDE names in exports."""

            __version__ = "0.1.0"
            # Note: no __all__ — uses griffe fallback to trigger AUTO_EXCLUDE


            class MyClass:
                """
                A real class that should survive auto-exclusion.

                Parameters
                ----------
                name
                    Instance name.
                """

                def __init__(self, name: str):
                    self.name = name

                def run(self) -> str:
                    """
                    Run the instance.

                    Returns
                    -------
                    str
                        Result string.
                    """
                    return f"running {self.name}"


            def real_func(x: int) -> int:
                """
                A real function that should survive auto-exclusion.

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


            def main():
                """CLI entry point — should be auto-excluded."""
                pass


            def cli():
                """CLI module — should be auto-excluded."""
                pass


            def config():
                """Config module — should be auto-excluded."""
                pass


            def utils():
                """Utils module — should be auto-excluded."""
                pass


            def logger():
                """Logger instance — should be auto-excluded."""
                pass
        ''',
        "README.md": """\
            # gdtest-auto-exclude

            A synthetic test package testing AUTO_EXCLUDE filtering.
        """,
    },
    "expected": {
        "detected_name": "gdtest-auto-exclude",
        "detected_module": "gdtest_auto_exclude",
        "detected_parser": "numpy",
        "export_names": ["MyClass", "real_func"],
        "auto_excluded": ["main", "cli", "config", "utils", "logger"],
        "has_user_guide": False,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'sechdg', 'sbsec'],
},
}
