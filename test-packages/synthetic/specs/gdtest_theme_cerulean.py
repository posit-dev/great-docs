"""
gdtest_theme_cerulean — Tests site.theme: 'cerulean'.

Dimensions: Q3
Focus: Site config with cerulean theme.
"""

SPEC = {
    "name": "gdtest_theme_cerulean",
    "description": "Tests site.theme: 'cerulean' config.",
    "dimensions": ["Q3"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-theme-cerulean",
            "version": "0.1.0",
            "description": "Test site theme cerulean config.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "site": {"theme": "cerulean"},
    },
    "files": {
        "gdtest_theme_cerulean/__init__.py": '''\
            """Package testing site theme cerulean config."""

            __all__ = ["paint", "blend"]


            def paint(color: str) -> str:
                """Paint with the given color.

                Parameters
                ----------
                color : str
                    The color to paint with.

                Returns
                -------
                str
                    A description of the painted result.

                Examples
                --------
                >>> paint("blue")
                'painted blue'
                """
                return f"painted {color}"


            def blend(c1: str, c2: str) -> str:
                """Blend two colors together.

                Parameters
                ----------
                c1 : str
                    The first color.
                c2 : str
                    The second color.

                Returns
                -------
                str
                    The blended color description.

                Examples
                --------
                >>> blend("red", "blue")
                'red-blue'
                """
                return f"{c1}-{c2}"
        ''',
        "README.md": ("# gdtest-v2-theme-cerulean\n\nTest site theme cerulean config.\n"),
    },
    "expected": {
        "detected_name": "gdtest-v2-theme-cerulean",
        "detected_module": "gdtest_theme_cerulean",
        "detected_parser": "numpy",
        "export_names": ["blend", "paint"],
        "num_exports": 2,
    },
}
