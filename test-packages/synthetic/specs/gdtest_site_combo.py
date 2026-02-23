"""
gdtest_site_combo — Site setting combo: cosmo theme + toc-depth:3 + toc-title:'Contents' + display_name.

Dimensions: Q1, Q5, Q6, K12
Focus: Multiple site config options combined with display_name.
"""

SPEC = {
    "name": "gdtest_site_combo",
    "description": "Site setting combo: cosmo theme + toc-depth:3 + toc-title:'Contents' + display_name.",
    "dimensions": ["Q1", "Q5", "Q6", "K12"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-site-combo",
            "version": "0.1.0",
            "description": "Test site setting combo with display_name.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "display_name": "Combo Site",
        "site": {"theme": "cosmo", "toc-depth": 3, "toc-title": "Contents"},
    },
    "files": {
        "gdtest_site_combo/__init__.py": '''\
            """Package testing site setting combo with display_name."""

            __all__ = ["setup", "render", "publish"]


            def setup(config: dict) -> None:
                """Set up the site with the given configuration.

                Parameters
                ----------
                config : dict
                    A dictionary of site configuration options.

                Returns
                -------
                None

                Examples
                --------
                >>> setup({"theme": "cosmo"})
                """
                pass


            def render(template: str) -> str:
                """Render a template into HTML.

                Parameters
                ----------
                template : str
                    The template string to render.

                Returns
                -------
                str
                    The rendered HTML output.

                Examples
                --------
                >>> render("<h1>Title</h1>")
                '<h1>Title</h1>'
                """
                return template


            def publish(site: str) -> bool:
                """Publish the site to the given destination.

                Parameters
                ----------
                site : str
                    The site name or URL to publish to.

                Returns
                -------
                bool
                    True if publishing was successful.

                Examples
                --------
                >>> publish("my-site")
                True
                """
                return True
        ''',
        "README.md": ("# gdtest-v2-site-combo\n\nTest site setting combo with display_name.\n"),
    },
    "expected": {
        "detected_name": "gdtest-v2-site-combo",
        "detected_module": "gdtest_site_combo",
        "detected_parser": "numpy",
        "export_names": ["publish", "render", "setup"],
        "num_exports": 3,
    },
}
