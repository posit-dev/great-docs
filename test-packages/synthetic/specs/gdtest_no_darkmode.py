"""
gdtest_no_darkmode — Tests dark_mode_toggle: false config.

Dimensions: K15
Focus: dark_mode_toggle config option set to false to disable the dark mode toggle.
"""

SPEC = {
    "name": "gdtest_no_darkmode",
    "description": "Tests dark_mode_toggle: false config",
    "dimensions": ["K15"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-no-darkmode",
            "version": "0.1.0",
            "description": "Test dark_mode_toggle false config",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "dark_mode_toggle": False,
    },
    "files": {
        "gdtest_no_darkmode/__init__.py": '''\
            """Package testing dark_mode_toggle false config."""

            __version__ = "0.1.0"
            __all__ = ["light_func", "bright_func"]


            def light_func(x: int) -> int:
                """
                Apply a light transformation to the input.

                Parameters
                ----------
                x
                    The input integer value.

                Returns
                -------
                int
                    The transformed value.
                """
                return x + 1


            def bright_func(x: int) -> int:
                """
                Apply a bright transformation to the input.

                Parameters
                ----------
                x
                    The input integer value.

                Returns
                -------
                int
                    The transformed value.
                """
                return x * 2
        ''',
        "README.md": """\
            # gdtest-v2-no-darkmode

            Tests dark_mode_toggle: false config.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-no-darkmode",
        "detected_module": "gdtest_no_darkmode",
        "detected_parser": "numpy",
        "export_names": ["bright_func", "light_func"],
        "num_exports": 2,
    },
}
