"""
gdtest_theme_cosmo — Tests site.theme: 'cosmo'.

Dimensions: Q1
Focus: Site config with cosmo theme.
"""

SPEC = {
    "name": "gdtest_theme_cosmo",
    "description": "Tests site.theme: 'cosmo' config.",
    "dimensions": ["Q1"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-theme-cosmo",
            "version": "0.1.0",
            "description": "Test site theme cosmo config.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "site": {"theme": "cosmo"},
    },
    "files": {
        "gdtest_theme_cosmo/__init__.py": '''\
            """Package testing site theme cosmo config."""

            __all__ = ["style", "theme"]


            def style(text: str) -> str:
                """Apply a style transformation to the text.

                Parameters
                ----------
                text : str
                    The text to style.

                Returns
                -------
                str
                    The styled text.

                Examples
                --------
                >>> style("hello")
                'HELLO'
                """
                return text.upper()


            def theme(name: str) -> dict:
                """Get a theme configuration by name.

                Parameters
                ----------
                name : str
                    The name of the theme.

                Returns
                -------
                dict
                    A dictionary of theme settings.

                Examples
                --------
                >>> theme("dark")
                {'name': 'dark', 'bg': '#000'}
                """
                return {"name": name, "bg": "#000"}
        ''',
        "README.md": ("# gdtest-v2-theme-cosmo\n\nTest site theme cosmo config.\n"),
    },
    "expected": {
        "detected_name": "gdtest-v2-theme-cosmo",
        "detected_module": "gdtest_theme_cosmo",
        "detected_parser": "numpy",
        "export_names": ["style", "theme"],
        "num_exports": 2,
    },
}
