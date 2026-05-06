"""
gdtest_user_guide_auto — Auto-discovered user guide with numeric prefixes.

Dimensions: A1, B1, C4, D1, E6, F1, G1, H7
Focus: user_guide/ dir with 01-intro.qmd, 02-quickstart.qmd, 03-advanced.qmd.
       Tests numeric prefix stripping, correct sort order, sidebar clean URLs.
"""

SPEC = {
    "name": "gdtest_user_guide_auto",
    "description": "Auto-discover user guide with numeric prefixes",
    "dimensions": ["A1", "B1", "C4", "D1", "E6", "F1", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-user-guide-auto",
            "version": "0.1.0",
            "description": "A synthetic test package with auto-discovered user guide",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_user_guide_auto/__init__.py": '''\
            """A test package with auto-discovered user guide."""

            __version__ = "0.1.0"
            __all__ = ["App", "run_app"]


            class App:
                """
                Main application class.

                Parameters
                ----------
                name
                    Application name.
                """

                def __init__(self, name: str):
                    self.name = name

                def start(self) -> None:
                    """Start the application."""
                    pass

                def stop(self) -> None:
                    """Stop the application."""
                    pass


            def run_app(name: str) -> App:
                """
                Create and start an application.

                Parameters
                ----------
                name
                    Application name.

                Returns
                -------
                App
                    A running application instance.
                """
                app = App(name)
                app.start()
                return app
        ''',
        "user_guide/01-intro.qmd": """\
            ---
            title: Introduction
            ---

            Welcome to the user guide!
        """,
        "user_guide/02-quickstart.qmd": """\
            ---
            title: Quick Start
            ---

            Get started quickly.
        """,
        "user_guide/03-advanced.qmd": """\
            ---
            title: Advanced Topics
            ---

            Advanced usage patterns.
        """,
        "README.md": """\
            # gdtest-user-guide-auto

            A synthetic test package with auto-discovered user guide.
        """,
    },
    "expected": {
        "detected_name": "gdtest-user-guide-auto",
        "detected_module": "gdtest_user_guide_auto",
        "detected_parser": "numpy",
        "export_names": ["App", "run_app"],
        "num_exports": 2,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": True,
        "user_guide_files": ["01-intro.qmd", "02-quickstart.qmd", "03-advanced.qmd"],
        "coverage_exclude": ['nodoc', 'bigcl', 'supp', 'hdg'],
},
}
