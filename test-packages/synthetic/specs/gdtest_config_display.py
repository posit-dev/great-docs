"""
gdtest_config_display — Config with display_name, theme color, authors.

Dimensions: A1, B1, C1, D1, E6, F6, G1, H7
Focus: display_name override, authors with roles, funding info.
       Site title should show 'Pretty Display Name'.
"""

SPEC = {
    "name": "gdtest_config_display",
    "description": "Config with display_name, authors, and funding",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-config-display",
            "version": "0.1.0",
            "description": "Test display_name config",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "display_name": "Pretty Display Name",
        "authors": [
            {
                "name": "Jane Doe",
                "email": "jane@example.com",
                "role": "Creator",
                "github": "janedoe",
            },
            {
                "name": "John Smith",
                "email": "john@example.com",
                "role": "Maintainer",
                "github": "johnsmith",
            },
        ],
        "funding": {
            "name": "Open Source Foundation",
            "roles": ["Sponsor"],
            "homepage": "https://example.com/oss-fund",
        },
    },
    "files": {
        "gdtest_config_display/__init__.py": '''\
            """Package with display_name config."""

            __version__ = "0.1.0"
            __all__ = ["render", "Style"]


            def render(template: str, **kwargs) -> str:
                """
                Render a template string.

                Parameters
                ----------
                template
                    Template string with placeholders.
                **kwargs
                    Values for placeholders.

                Returns
                -------
                str
                    Rendered string.
                """
                return template.format(**kwargs)


            class Style:
                """
                Style configuration.

                Parameters
                ----------
                color
                    CSS color value.
                font_size
                    Font size in pixels.
                """

                def __init__(self, color: str = "#333", font_size: int = 14):
                    self.color = color
                    self.font_size = font_size

                def to_css(self) -> str:
                    """
                    Convert to CSS string.

                    Returns
                    -------
                    str
                        CSS rule string.
                    """
                    return f"color: {self.color}; font-size: {self.font_size}px;"
        ''',
        "README.md": """\
            # gdtest-config-display

            Tests display_name, authors, and funding in config.
        """,
    },
    "expected": {
        "detected_name": "gdtest-config-display",
        "detected_module": "gdtest_config_display",
        "detected_parser": "numpy",
        "export_names": ["render", "Style"],
        "num_exports": 2,
        "section_titles": ["Functions", "Classes"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
