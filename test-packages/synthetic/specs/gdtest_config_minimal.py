"""
gdtest_config_minimal — Config opts out of source links and dark mode.

Dimensions: A1, B1, C1, D1, E6, F6, G1, H7
Focus: source.enabled=false, dark_mode=false. Tests opt-out flags.
"""

SPEC = {
    "name": "gdtest_config_minimal",
    "description": "Config disables source links and dark mode",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-config-minimal",
            "version": "0.1.0",
            "description": "Test minimal config with opt-outs",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "source": {
            "enabled": False,
        },
        "dark_mode_toggle": False,
    },
    "files": {
        "gdtest_config_minimal/__init__.py": '''\
            """A minimal package with opt-out config."""

            __version__ = "0.1.0"
            __all__ = ["add", "subtract"]


            def add(a: int, b: int) -> int:
                """
                Add two numbers.

                Parameters
                ----------
                a
                    First number.
                b
                    Second number.

                Returns
                -------
                int
                    Sum.
                """
                return a + b


            def subtract(a: int, b: int) -> int:
                """
                Subtract b from a.

                Parameters
                ----------
                a
                    First number.
                b
                    Number to subtract.

                Returns
                -------
                int
                    Difference.
                """
                return a - b
        ''',
        "README.md": """\
            # gdtest-config-minimal

            Tests config with source.enabled=false and dark_mode=false.
        """,
    },
    "expected": {
        "detected_name": "gdtest-config-minimal",
        "detected_module": "gdtest_config_minimal",
        "detected_parser": "numpy",
        "export_names": ["add", "subtract"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
    },
}
