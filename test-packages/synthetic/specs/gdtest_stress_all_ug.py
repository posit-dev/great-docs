"""
gdtest_stress_all_ug — Maximum user guide complexity.

Dimensions: M2, M3, M4, M7, M8
Focus: 8 user guide pages across subdirectories with frontmatter sections,
       mixed extensions (.qmd and .md), and numbered filenames.
"""

SPEC = {
    "name": "gdtest_stress_all_ug",
    "description": "Maximum user guide complexity.",
    "dimensions": ["M2", "M3", "M4", "M7", "M8"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-stress-all-ug",
            "version": "0.1.0",
            "description": "Stress test with maximum user guide complexity.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_stress_all_ug/__init__.py": '''\
            """Package stress-testing maximum user guide complexity."""

            __all__ = ["scaffold", "teardown"]


            def scaffold(name: str) -> dict:
                """Scaffold a new project structure.

                Parameters
                ----------
                name : str
                    The name of the project to scaffold.

                Returns
                -------
                dict
                    A dictionary with the scaffolded project structure.

                Examples
                --------
                >>> scaffold("my-project")
                {'name': 'my-project', 'created': True}
                """
                return {"name": name, "created": True}


            def teardown() -> None:
                """Tear down and clean up the current project.

                Returns
                -------
                None

                Examples
                --------
                >>> teardown()
                """
                pass
        ''',
        "user_guide/basics/01-intro.qmd": (
            "---\n"
            "title: Introduction\n"
            "guide-section: Foundation\n"
            "---\n"
            "\n"
            "# Introduction\n"
            "\n"
            "Welcome to the project. This guide covers the fundamentals.\n"
        ),
        "user_guide/basics/02-install.md": (
            "---\n"
            "title: Installation\n"
            "guide-section: Foundation\n"
            "---\n"
            "\n"
            "# Installation\n"
            "\n"
            "Follow these steps to install the package.\n"
            "\n"
            "```bash\n"
            "pip install gdtest-v2-stress-all-ug\n"
            "```\n"
        ),
        "user_guide/basics/03-quickstart.qmd": (
            "---\n"
            "title: Quickstart\n"
            "guide-section: Foundation\n"
            "---\n"
            "\n"
            "# Quickstart\n"
            "\n"
            "Get up and running quickly with this guide.\n"
        ),
        "user_guide/advanced/01-architecture.qmd": (
            "---\n"
            "title: Architecture\n"
            "guide-section: Deep Dive\n"
            "---\n"
            "\n"
            "# Architecture\n"
            "\n"
            "An overview of the system architecture and design decisions.\n"
        ),
        "user_guide/advanced/02-patterns.md": (
            "---\n"
            "title: Patterns\n"
            "guide-section: Deep Dive\n"
            "---\n"
            "\n"
            "# Patterns\n"
            "\n"
            "Common design patterns used throughout the codebase.\n"
        ),
        "user_guide/advanced/03-optimization.qmd": (
            "---\n"
            "title: Optimization\n"
            "guide-section: Deep Dive\n"
            "---\n"
            "\n"
            "# Optimization\n"
            "\n"
            "Techniques for optimizing performance and memory usage.\n"
        ),
        "user_guide/appendix/01-faq.qmd": (
            "---\n"
            "title: FAQ\n"
            "guide-section: Appendix\n"
            "---\n"
            "\n"
            "# Frequently Asked Questions\n"
            "\n"
            "Answers to commonly asked questions.\n"
        ),
        "user_guide/appendix/02-glossary.md": (
            "---\n"
            "title: Glossary\n"
            "guide-section: Appendix\n"
            "---\n"
            "\n"
            "# Glossary\n"
            "\n"
            "Key terms and definitions used in the documentation.\n"
        ),
        "README.md": (
            "# gdtest-v2-stress-all-ug\n\nStress test with maximum user guide complexity.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-v2-stress-all-ug",
        "detected_module": "gdtest_stress_all_ug",
        "detected_parser": "numpy",
        "export_names": ["scaffold", "teardown"],
        "num_exports": 2,
    },
}
