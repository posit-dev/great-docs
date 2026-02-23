"""
gdtest_theme_lumen — Tests site.theme: 'lumen'.

Dimensions: Q2
Focus: Site config with lumen theme.
"""

SPEC = {
    "name": "gdtest_theme_lumen",
    "description": "Tests site.theme: 'lumen' config.",
    "dimensions": ["Q2"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-theme-lumen",
            "version": "0.1.0",
            "description": "Test site theme lumen config.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "site": {"theme": "lumen"},
    },
    "files": {
        "gdtest_theme_lumen/__init__.py": '''\
            """Package testing site theme lumen config."""

            __all__ = ["illuminate", "dim"]


            def illuminate(scene: str) -> str:
                """Illuminate a scene by adding light.

                Parameters
                ----------
                scene : str
                    The scene description to illuminate.

                Returns
                -------
                str
                    The illuminated scene description.

                Examples
                --------
                >>> illuminate("dark room")
                'bright dark room'
                """
                return f"bright {scene}"


            def dim(brightness: float) -> float:
                """Reduce brightness by half.

                Parameters
                ----------
                brightness : float
                    The current brightness level.

                Returns
                -------
                float
                    The dimmed brightness level.

                Examples
                --------
                >>> dim(1.0)
                0.5
                """
                return brightness / 2.0
        ''',
        "README.md": ("# gdtest-v2-theme-lumen\n\nTest site theme lumen config.\n"),
    },
    "expected": {
        "detected_name": "gdtest-v2-theme-lumen",
        "detected_module": "gdtest_theme_lumen",
        "detected_parser": "numpy",
        "export_names": ["dim", "illuminate"],
        "num_exports": 2,
    },
}
