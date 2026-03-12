"""
gdtest_config_all_on — Every possible config toggle set to non-default.

Dimensions: A1, B1, C1, D1, E6, F6, G1, H7
Focus: All config options at once: parser, display_name, source,
       dark_mode, authors, funding, user_guide. Config stress test.
"""

SPEC = {
    "name": "gdtest_config_all_on",
    "description": "Every config toggle set to non-default value",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-config-all-on",
            "version": "0.1.0",
            "description": "Test all config options at once",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "display_name": "All Options Enabled",
        "parser": "google",
        "source": {
            "enabled": True,
            "branch": "develop",
        },
        "dark_mode_toggle": True,
        "authors": [
            {
                "name": "Alpha Author",
                "email": "alpha@example.com",
                "role": "Lead",
                "github": "alpha",
            },
            {
                "name": "Beta Author",
                "email": "beta@example.com",
                "role": "Contributor",
                "github": "beta",
            },
        ],
        "funding": {
            "name": "Test Grant",
            "roles": ["Funder"],
            "homepage": "https://example.com/grant",
        },
        "reference": {
            "title": "API Reference",
        },
    },
    "files": {
        "gdtest_config_all_on/__init__.py": '''\
            """Package testing all config toggles."""

            __version__ = "0.1.0"
            __all__ = ["process", "Config"]


            def process(data: list) -> list:
                """Process the given data.

                Args:
                    data: Input data list.

                Returns:
                    Processed data list.
                """
                return [x * 2 for x in data]


            class Config:
                """Configuration holder.

                Attributes:
                    name: Config name.
                    value: Config value.
                """

                def __init__(self, name: str, value: int = 0):
                    """Initialize config.

                    Args:
                        name: Config name.
                        value: Config value.
                    """
                    self.name = name
                    self.value = value

                def validate(self) -> bool:
                    """Validate this configuration.

                    Returns:
                        True if valid.
                    """
                    return bool(self.name)
        ''',
        "user_guide/getting-started.qmd": """\
            ---
            title: Getting Started
            ---

            # Getting Started

            Quick start guide for the all-on config package.
        """,
        "README.md": """\
            # gdtest-config-all-on

            Tests every config toggle set to a non-default value.
        """,
    },
    "expected": {
        "detected_name": "gdtest-config-all-on",
        "detected_module": "gdtest_config_all_on",
        "detected_parser": "google",
        "export_names": ["process", "Config"],
        "num_exports": 2,
        "section_titles": ["Functions", "Classes"],
        "has_user_guide": True,
    },
}
