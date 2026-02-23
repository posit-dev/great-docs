"""
gdtest_toc_depth — Tests site.toc-depth: 3.

Dimensions: Q5
Focus: Site config with toc-depth set to 3.
"""

SPEC = {
    "name": "gdtest_toc_depth",
    "description": "Tests site.toc-depth: 3 config.",
    "dimensions": ["Q5"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-toc-depth",
            "version": "0.1.0",
            "description": "Test site toc-depth config.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "site": {"toc-depth": 3},
    },
    "files": {
        "gdtest_toc_depth/__init__.py": '''\
            """Package testing site toc-depth config."""

            __all__ = ["outline", "expand"]


            def outline(doc: str) -> list:
                """Generate an outline for the given document.

                Parameters
                ----------
                doc : str
                    The document content to outline.

                Returns
                -------
                list
                    A list of section headings.

                Examples
                --------
                >>> outline("Chapter 1")
                ['Chapter 1']
                """
                return [doc]


            def expand(section: str) -> dict:
                """Expand a section into its subsections.

                Parameters
                ----------
                section : str
                    The section name to expand.

                Returns
                -------
                dict
                    A dictionary with the section and its children.

                Examples
                --------
                >>> expand("intro")
                {'section': 'intro', 'children': []}
                """
                return {"section": section, "children": []}
        ''',
        "README.md": ("# gdtest-v2-toc-depth\n\nTest site toc-depth config.\n"),
    },
    "expected": {
        "detected_name": "gdtest-v2-toc-depth",
        "detected_module": "gdtest_toc_depth",
        "detected_parser": "numpy",
        "export_names": ["expand", "outline"],
        "num_exports": 2,
    },
}
