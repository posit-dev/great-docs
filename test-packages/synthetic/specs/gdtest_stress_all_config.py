"""
gdtest_stress_all_config — ALL config options at once.

Dimensions: K1, K4, K5, K6, K9, K10, K12, K13, K14, K15
Focus: Stress test with every config option set simultaneously.
"""

SPEC = {
    "name": "gdtest_stress_all_config",
    "description": "ALL config options at once.",
    "dimensions": ["K1", "K4", "K5", "K6", "K9", "K10", "K12", "K13", "K14", "K15"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-stress-all-config",
            "version": "0.1.0",
            "description": "Stress test with all config options.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "display_name": "Stress Test All Config",
        "parser": "google",
        "dynamic": False,
        "github_style": "icon",
        "source": {"enabled": False},
        "sidebar_filter": {"enabled": False},
        "dark_mode_toggle": False,
        "authors": [
            {
                "name": "Test Author",
                "email": "test@example.com",
                "role": "Tester",
                "github": "tester",
            },
        ],
        "funding": {
            "name": "Test Fund",
            "roles": ["Sponsor"],
            "homepage": "https://example.com",
        },
        "site": {"theme": "cosmo", "toc-depth": 3, "toc-title": "Navigation"},
    },
    "files": {
        "gdtest_stress_all_config/__init__.py": '''\
            """Package stress-testing all config options at once."""

            __all__ = ["stress_create", "stress_read", "stress_delete"]


            def stress_create(name: str) -> dict:
                """Create a new stress test resource.

                Args:
                    name: The name of the resource to create.

                Returns:
                    A dictionary with the created resource details.

                Examples:
                    >>> stress_create("test-item")
                    {'name': 'test-item', 'created': True}
                """
                return {"name": name, "created": True}


            def stress_read(id: int) -> dict:
                """Read a stress test resource by ID.

                Args:
                    id: The identifier of the resource to read.

                Returns:
                    A dictionary with the resource data.

                Examples:
                    >>> stress_read(1)
                    {'id': 1, 'data': 'loaded'}
                """
                return {"id": id, "data": "loaded"}


            def stress_delete(id: int) -> bool:
                """Delete a stress test resource by ID.

                Args:
                    id: The identifier of the resource to delete.

                Returns:
                    True if the resource was deleted successfully.

                Examples:
                    >>> stress_delete(1)
                    True
                """
                return True
        ''',
        "README.md": ("# gdtest-v2-stress-all-config\n\nStress test with all config options.\n"),
    },
    "expected": {
        "detected_name": "gdtest-v2-stress-all-config",
        "detected_module": "gdtest_stress_all_config",
        "detected_parser": "google",
        "export_names": ["stress_create", "stress_delete", "stress_read"],
        "num_exports": 3,
    },
}
