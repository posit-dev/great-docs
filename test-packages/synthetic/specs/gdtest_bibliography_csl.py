"""
gdtest_bibliography_csl — Project-level bibliography with a custom CSL style.

Dimensions: A1, B1, C1, D1, E6, F1, G1, H7, K58
Focus: Exercises the optional `csl:` key alongside `bibliography:` in
       great-docs.yml. A custom numeric Citation Style Language file is copied
       into the build directory and wired into _quarto.yml, so citations render
       as bracketed numbers ([1], [2]) instead of the default Chicago
       author-date style. This proves CSL selection works end to end (issue
       #214's optional CSL support), distinct from gdtest_bibliography which
       uses the default style.
"""

SPEC = {
    "name": "gdtest_bibliography_csl",
    "description": "Project-level bibliography with a custom (numeric) CSL style",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F1", "G1", "H7", "K58"],
    # ── Project metadata ─────────────────────────────────────────────
    "pyproject_toml": {
        "project": {
            "name": "gdtest-bibliography-csl",
            "version": "0.1.0",
            "description": "Synthetic test for project-level bibliography + CSL",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    # ── Source files ──────────────────────────────────────────────────
    "files": {
        "gdtest_bibliography_csl/__init__.py": '''\
            """Package demonstrating a custom citation style."""

            __version__ = "0.1.0"
            __all__ = ["cite"]


            def cite(key: str) -> str:
                """
                Return a citation key.

                Parameters
                ----------
                key
                    The citation key.

                Returns
                -------
                str
                    The same key.
                """
                return key
        ''',
        # Bibliography (two entries, cited in order on the page).
        "docs/references.bib": """\
            @article{knuth1984,
              title = {Literate Programming},
              author = {Knuth, Donald E.},
              year = {1984},
              journal = {The Computer Journal},
            }

            @book{lamport1994,
              title = {LaTeX: A Document Preparation System},
              author = {Lamport, Leslie},
              year = {1994},
              publisher = {Addison-Wesley},
            }
        """,
        # A minimal numeric CSL style: inline citations become [1], [2] and the
        # bibliography is a numbered list — visibly different from the default
        # Chicago author-date style, so a test can confirm the CSL was applied.
        "docs/numeric.csl": """\
            <?xml version="1.0" encoding="utf-8"?>
            <style xmlns="http://purl.org/net/xbiblio/csl" class="in-text" version="1.0" default-locale="en-US">
              <info>
                <title>GD Test Numeric</title>
                <id>gd-test-numeric</id>
                <updated>2024-01-01T00:00:00+00:00</updated>
              </info>
              <citation collapse="citation-number">
                <layout prefix="[" suffix="]" delimiter=",">
                  <text variable="citation-number"/>
                </layout>
              </citation>
              <bibliography>
                <layout>
                  <text variable="citation-number" prefix="[" suffix="] "/>
                  <names variable="author" suffix=". "><name/></names>
                  <text variable="title" suffix="."/>
                </layout>
              </bibliography>
            </style>
        """,
        # A page citing both entries; no per-page frontmatter.
        "user_guide/01-citations.qmd": """\
            ---
            title: Numbered Citations
            ---

            Literate programming was introduced by Knuth [@knuth1984], and LaTeX
            by Lamport [@lamport1994]. With a numeric CSL, these render as
            bracketed numbers rather than author-year text.

            ## References

            ::: {#refs}
            :::
        """,
        "README.md": """\
            # gdtest-bibliography-csl

            Synthetic test for the optional `csl:` key (issue #214). A custom
            numeric Citation Style Language file selects bracketed-number
            citations instead of the default author-date style.
        """,
    },
    # ── great-docs.yml ────────────────────────────────────────────────
    "config": {
        "bibliography": "docs/references.bib",
        "csl": "docs/numeric.csl",
    },
    # ── Expected outcomes ─────────────────────────────────────────────
    "expected": {
        "detected_name": "gdtest-bibliography-csl",
        "detected_module": "gdtest_bibliography_csl",
        "detected_parser": "numpy",
        "export_names": ["cite"],
        "num_exports": 1,
        "section_titles": ["Functions"],
        "has_user_guide": True,
        "user_guide_files": ["01-citations.qmd"],
        "has_license_page": False,
        "has_citation_page": False,
        # Bibliography + CSL expectations (consumed by dedicated tests)
        "has_bibliography": True,
        "bibliography_file": "references.bib",
        "csl_file": "numeric.csl",
        "citation_keys": ["knuth1984", "lamport1994"],
        "coverage_exclude": ['nodoc', 'bigcl', 'supp', 'hdg'],
},
}
