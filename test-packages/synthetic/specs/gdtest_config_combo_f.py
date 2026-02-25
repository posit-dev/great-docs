"""
gdtest_config_combo_f — Config combo: dynamic=false + no dark mode + exclude list + jupyter kernel.

Dimensions: K9, K15, K16, K17
Focus: All opt-out/override flags — static mode, dark mode off, excludes, jupyter kernel.
"""

SPEC = {
    "name": "gdtest_config_combo_f",
    "description": (
        "Config combo: dynamic=false, dark_mode_toggle=false, exclude list, "
        "jupyter kernel. Tests static analysis with multiple opt-out flags."
    ),
    "dimensions": ["K9", "K15", "K16", "K17"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-config-combo-f",
            "version": "0.1.0",
            "description": "Test package for config combo F.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "dynamic": False,
        "dark_mode_toggle": False,
        "exclude": ["_internal_helper", "_utils"],
        "jupyter": {
            "kernel": "python3",
        },
    },
    "files": {
        "gdtest_config_combo_f/__init__.py": '''\
            """Config combo F — dynamic=false, no dark mode, exclude list, jupyter kernel."""

            __version__ = "0.1.0"
            __all__ = ["analyze", "report", "export", "_internal_helper", "_utils"]


            def analyze(dataset: list) -> dict:
                """
                Analyze a dataset and return summary statistics.

                Parameters
                ----------
                dataset : list
                    The data to analyze.

                Returns
                -------
                dict
                    Summary statistics including count, mean, and range.
                """
                return {"count": len(dataset)}


            def report(results: dict) -> str:
                """
                Generate a text report from analysis results.

                Parameters
                ----------
                results : dict
                    The results from `analyze`.

                Returns
                -------
                str
                    Formatted report string.
                """
                return str(results)


            def export(data: dict, fmt: str = "json") -> str:
                """
                Export data in the specified format.

                Parameters
                ----------
                data : dict
                    The data to export.
                fmt : str
                    Output format, one of 'json', 'csv', 'yaml'.

                Returns
                -------
                str
                    The serialized data string.
                """
                return str(data)


            def _internal_helper():
                """Internal helper that should be excluded."""
                pass


            def _utils():
                """Internal utilities that should be excluded."""
                pass
        ''',
        "README.md": """\
            # Config Combo F

            Tests dynamic=false, dark_mode_toggle=false, exclude list, and jupyter kernel config.
        """,
    },
    "expected": {
        "detected_name": "gdtest-config-combo-f",
        "detected_module": "gdtest_config_combo_f",
        "detected_parser": "numpy",
        "export_names": ["analyze", "export", "report"],
        "num_exports": 3,
    },
}
