"""
gdtest_full_extras — All supporting pages present.

Dimensions: A1, B1, C4, D1, E6, F1, G1, H1+H2+H3+H4+H6
Focus: LICENSE, CITATION.cff, CONTRIBUTING.md, CODE_OF_CONDUCT.md,
       assets/ directory. Plus user guide and mixed class/function exports.
       Tests all extra page generation, asset copying, citation tabs.
"""

SPEC = {
    "name": "gdtest_full_extras",
    "description": "All supporting pages — LICENSE, CITATION, CONTRIBUTING, etc.",
    "dimensions": ["A1", "B1", "C4", "D1", "E6", "F1", "G1", "H1", "H2", "H3", "H4", "H6"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-full-extras",
            "version": "0.1.0",
            "description": "A synthetic test package with all supporting pages",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_full_extras/__init__.py": '''\
            """A test package with all supporting pages."""

            __version__ = "0.1.0"
            __all__ = ["Manager", "start", "stop"]


            class Manager:
                """
                A resource manager.

                Parameters
                ----------
                name
                    Manager name.
                """

                def __init__(self, name: str):
                    self.name = name

                def allocate(self) -> bool:
                    """
                    Allocate resources.

                    Returns
                    -------
                    bool
                        True if allocated.
                    """
                    return True

                def release(self) -> None:
                    """Release all resources."""
                    pass


            def start(manager: Manager) -> None:
                """
                Start a manager.

                Parameters
                ----------
                manager
                    The manager to start.
                """
                pass


            def stop(manager: Manager) -> None:
                """
                Stop a manager.

                Parameters
                ----------
                manager
                    The manager to stop.
                """
                pass
        ''',
        "user_guide/01-getting-started.qmd": """\
            ---
            title: Getting Started
            ---

            Welcome to the project!
        """,
        "user_guide/02-configuration.qmd": """\
            ---
            title: Configuration
            ---

            How to configure the manager.
        """,
        "README.md": """\
            # gdtest-full-extras

            A synthetic test package with all supporting pages.
        """,
        "LICENSE": """\
            MIT License

            Copyright (c) 2026 Test Author

            Permission is hereby granted, free of charge, to any person obtaining a copy.
        """,
        "CITATION.cff": """\
            cff-version: 1.2.0
            message: "If you use this software, please cite it."
            title: "Full Extras Package"
            version: "0.1.0"
            date-released: "2026-01-15"
            authors:
              - family-names: Author
                given-names: Test
        """,
        "CONTRIBUTING.md": """\
            # Contributing

            We welcome contributions!

            ## Development

            ```bash
            pip install -e ".[dev]"
            ```
        """,
        "CODE_OF_CONDUCT.md": """\
            # Code of Conduct

            Be kind. Be respectful. Be constructive.
        """,
        "assets/logo.txt": """\
            ┌───────────────┐
            │ Full Extras   │
            └───────────────┘
        """,
    },
    "expected": {
        "detected_name": "gdtest-full-extras",
        "detected_module": "gdtest_full_extras",
        "detected_parser": "numpy",
        "export_names": ["Manager", "start", "stop"],
        "num_exports": 3,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": True,
        "user_guide_files": ["01-getting-started.qmd", "02-configuration.qmd"],
        "has_license_page": True,
        "has_citation_page": True,
        "has_contributing_page": True,
        "has_code_of_conduct_page": True,
        "has_assets": True,
        "coverage_exclude": ['nodoc', 'bigcl', 'hdg'],
},
}
