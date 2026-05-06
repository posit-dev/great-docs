"""
gdtest_user_guide_sections — User guide with frontmatter guide-section metadata.

Dimensions: A1, B1, C4, D1, E6, F2, G1, H7
Focus: .qmd files with guide-section: "Getting Started" and
       guide-section: "Advanced" in frontmatter.
       Tests section grouping from frontmatter.
"""

SPEC = {
    "name": "gdtest_user_guide_sections",
    "description": "User guide with frontmatter guide-section grouping",
    "dimensions": ["A1", "B1", "C4", "D1", "E6", "F2", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-user-guide-sections",
            "version": "0.1.0",
            "description": "A synthetic test package with sectioned user guide",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_user_guide_sections/__init__.py": '''\
            """A test package with sectioned user guide."""

            __version__ = "0.1.0"
            __all__ = ["Widget", "create_widget"]


            class Widget:
                """
                A UI widget.

                Parameters
                ----------
                label
                    Widget label.
                """

                def __init__(self, label: str):
                    self.label = label

                def show(self) -> None:
                    """Show the widget."""
                    pass


            def create_widget(label: str) -> Widget:
                """
                Create a new widget.

                Parameters
                ----------
                label
                    Widget label.

                Returns
                -------
                Widget
                    A new widget.
                """
                return Widget(label)
        ''',
        "user_guide/01-welcome.qmd": """\
            ---
            title: Welcome
            guide-section: Getting Started
            ---

            Welcome to the project!
        """,
        "user_guide/02-install.qmd": """\
            ---
            title: Installation
            guide-section: Getting Started
            ---

            How to install the package.
        """,
        "user_guide/03-customization.qmd": """\
            ---
            title: Customization
            guide-section: Advanced
            ---

            Advanced customization options.
        """,
        "user_guide/04-plugins.qmd": """\
            ---
            title: Plugins
            guide-section: Advanced
            ---

            Writing and using plugins.
        """,
        "README.md": """\
            # gdtest-user-guide-sections

            A synthetic test package with sectioned user guide.
        """,
    },
    "expected": {
        "detected_name": "gdtest-user-guide-sections",
        "detected_module": "gdtest_user_guide_sections",
        "detected_parser": "numpy",
        "export_names": ["Widget", "create_widget"],
        "num_exports": 2,
        "has_user_guide": True,
        "user_guide_files": [
            "01-welcome.qmd",
            "02-install.qmd",
            "03-customization.qmd",
            "04-plugins.qmd",
        ],
        "coverage_exclude": ['nodoc', 'bigcl', 'supp', 'sechdg', 'sbsec', 'hdg'],
},
}
