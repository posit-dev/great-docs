"""
gdtest_stress_all_sections — Maximum navigation with multiple sections.

Dimensions: N1, N2, N3, N5, N6, M1, P1
Focus: Five custom sections, explicit reference config with two groups,
       and a user guide page — maximum navigation complexity.
"""

SPEC = {
    "name": "gdtest_stress_all_sections",
    "description": "Maximum navigation with multiple sections, reference groups, and user guide.",
    "dimensions": ["N1", "N2", "N3", "N5", "N6", "M1", "P1"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-stress-all-sections",
            "version": "0.1.0",
            "description": "Stress test with maximum navigation complexity.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "sections": [
            {"title": "Examples", "dir": "examples"},
            {"title": "Tutorials", "dir": "tutorials"},
            {"title": "Recipes", "dir": "recipes"},
            {"title": "FAQ", "dir": "faq"},
            {"title": "Blog", "dir": "blog"},
        ],
        "reference": [
            {
                "title": "Core",
                "desc": "Primary API",
                "contents": [
                    {"name": "create"},
                    {"name": "read"},
                ],
            },
            {
                "title": "Admin",
                "desc": "Admin API",
                "contents": [
                    {"name": "update"},
                    {"name": "delete"},
                ],
            },
        ],
    },
    "files": {
        "gdtest_stress_all_sections/__init__.py": '"""Test package for maximum navigation complexity."""\n',
        "gdtest_stress_all_sections/core.py": '''
            """Core CRUD functions."""


            def create(name: str) -> dict:
                """Create a new resource.

                Parameters
                ----------
                name : str
                    The name of the resource to create.

                Returns
                -------
                dict
                    A dictionary with the created resource.

                Examples
                --------
                >>> create("item")
                {'name': 'item', 'id': 1}
                """
                return {"name": name, "id": 1}


            def read(id: int) -> dict:
                """Read a resource by its ID.

                Parameters
                ----------
                id : int
                    The identifier of the resource.

                Returns
                -------
                dict
                    A dictionary with the resource data.

                Examples
                --------
                >>> read(1)
                {'id': 1, 'data': 'loaded'}
                """
                return {"id": id, "data": "loaded"}


            def update(id: int, data: dict) -> dict:
                """Update a resource by its ID.

                Parameters
                ----------
                id : int
                    The identifier of the resource to update.
                data : dict
                    The new data to apply.

                Returns
                -------
                dict
                    The updated resource.

                Examples
                --------
                >>> update(1, {"status": "active"})
                {'id': 1, 'status': 'active'}
                """
                return {"id": id, **data}


            def delete(id: int) -> bool:
                """Delete a resource by its ID.

                Parameters
                ----------
                id : int
                    The identifier of the resource to delete.

                Returns
                -------
                bool
                    True if the resource was deleted.

                Examples
                --------
                >>> delete(1)
                True
                """
                return True
        ''',
        "examples/demo.qmd": (
            "---\n"
            "title: Demo Example\n"
            "---\n"
            "\n"
            "# Demo Example\n"
            "\n"
            "A demonstration of the package in action.\n"
        ),
        "tutorials/start.qmd": (
            "---\n"
            "title: Getting Started\n"
            "---\n"
            "\n"
            "# Getting Started\n"
            "\n"
            "A step-by-step tutorial for new users.\n"
        ),
        "recipes/quick.qmd": (
            "---\ntitle: Quick Recipe\n---\n\n# Quick Recipe\n\nA quick recipe for common tasks.\n"
        ),
        "faq/common.qmd": (
            "---\n"
            "title: Common Questions\n"
            "---\n"
            "\n"
            "# Common Questions\n"
            "\n"
            "Answers to frequently asked questions.\n"
        ),
        "blog/latest.qmd": (
            "---\ntitle: Latest Updates\n---\n\n# Latest Updates\n\nThe latest news and updates.\n"
        ),
        "user_guide/intro.qmd": (
            "---\n"
            "title: Introduction\n"
            "---\n"
            "\n"
            "# Introduction\n"
            "\n"
            "An introduction to the package and its capabilities.\n"
        ),
        "README.md": (
            "# gdtest-v2-stress-all-sections\n\nStress test with maximum navigation complexity.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-v2-stress-all-sections",
        "detected_module": "gdtest_stress_all_sections",
        "detected_parser": "numpy",
        "export_names": ["create", "delete", "read", "update"],
        "num_exports": 4,
    },
}
