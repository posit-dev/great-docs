"""
gdtest_index_frontmatter — index.qmd with YAML frontmatter + Quarto cell options.

Dimensions: A1, B1, C1, D1, E6, F6, G3, H7
Focus: Regression coverage for issue #237. The project root ``index.qmd`` has
       its own YAML frontmatter block AND a Quarto code cell with hash-pipe
       (``#|``) cell options. When Great Docs wraps this into the generated
       homepage it must:

         1. Strip the source file's leading frontmatter so it is NOT embedded
            mid-document (otherwise the `---` block renders as a horizontal
            rule with the raw YAML text visible).
         2. Bump real Markdown headings one level, but leave fenced code blocks
            untouched so `#| code-fold: true` is preserved (and not mangled
            into `##| code-fold: true`, which Quarto ignores).
"""

SPEC = {
    "name": "gdtest_index_frontmatter",
    "description": "index.qmd frontmatter stripped; cell options preserved",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F6", "G3", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-index-frontmatter",
            "version": "0.1.0",
            "description": "Synthetic test for index.qmd frontmatter + cell options",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_index_frontmatter/__init__.py": '''\
            """A test package whose homepage is an index.qmd with frontmatter."""

            __version__ = "0.1.0"
            __all__ = ["hello"]


            def hello() -> str:
                """
                Say hello.

                Returns
                -------
                str
                    A greeting.
                """
                return "Hello!"
        ''',
        "index.qmd": """\
            ---
            title: "Embedded Frontmatter Title"
            toc: true
            ---

            # Getting Started

            Welcome to the homepage rendered from a Quarto `index.qmd`.

            ## Highlights

            - First highlight
            - Second highlight

            ```{python}
            #| code-fold: true
            #| code-summary: "Show the setup code"
            # Greet the reader from inside a fenced code cell
            print("hello from the homepage")
            ```
        """,
    },
    "expected": {
        "detected_name": "gdtest-index-frontmatter",
        "detected_module": "gdtest_index_frontmatter",
        "detected_parser": "numpy",
        "export_names": ["hello"],
        "num_exports": 1,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "has_license_page": False,
        "has_citation_page": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
