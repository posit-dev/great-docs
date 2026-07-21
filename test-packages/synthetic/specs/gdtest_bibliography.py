"""
gdtest_bibliography — Project-level bibliography forwarded from great-docs.yml.

Dimensions: A1, B1, C1, D1, E6, F1, G1, H7, K57
Focus: A single project-level `bibliography:` key in great-docs.yml is copied
       into the build directory and wired into _quarto.yml so that *every* page
       can use [@citation-key] syntax without per-page frontmatter. Verifies the
       fix for issue #214 across multiple contexts:
         - the homepage (index.qmd, built from README at the project root),
         - a top-level user-guide page,
         - a user-guide page nested in a subdirectory (depth-independence),
       with one citation key (knuth1984) shared across pages to prove a single
       bibliography genuinely serves the whole project.
"""

SPEC = {
    "name": "gdtest_bibliography",
    "description": "Project-level bibliography forwarded into _quarto.yml",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F1", "G1", "H7", "K57"],
    # ── Project metadata ─────────────────────────────────────────────
    "pyproject_toml": {
        "project": {
            "name": "gdtest-bibliography",
            "version": "0.1.0",
            "description": "Synthetic test for project-level bibliography wiring",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    # ── Source files ──────────────────────────────────────────────────
    "files": {
        "gdtest_bibliography/__init__.py": '''\
            """Package demonstrating project-level citations."""

            __version__ = "0.1.0"
            __all__ = ["weave", "tangle"]


            def weave(source: str) -> str:
                """
                Produce documentation from a literate source.

                The literate programming model this implements is due to Knuth
                [@knuth1984]; this docstring citation probes whether project-level
                bibliography resolution reaches generated API reference pages.

                Parameters
                ----------
                source
                    The literate program source.

                Returns
                -------
                str
                    The woven documentation.
                """
                return source


            def tangle(source: str) -> str:
                """
                Extract compilable code from a literate source.

                Parameters
                ----------
                source
                    The literate program source.

                Returns
                -------
                str
                    The tangled code.
                """
                return source
        ''',
        # The bibliography lives outside the build tree, under docs/. The
        # great-docs.yml `bibliography:` key points here; Great Docs copies it
        # into the build directory at build time. Three entries: knuth1984 is
        # shared across multiple pages; lamport1994 and parnas1972 are page-local.
        "docs/references.bib": """\
            @article{knuth1984,
              title = {Literate Programming},
              author = {Knuth, Donald E.},
              year = {1984},
              journal = {The Computer Journal},
              volume = {27},
              number = {2},
              pages = {97--111},
            }

            @book{lamport1994,
              title = {LaTeX: A Document Preparation System},
              author = {Lamport, Leslie},
              year = {1994},
              publisher = {Addison-Wesley},
              edition = {2nd},
            }

            @article{parnas1972,
              title = {On the Criteria to Be Used in Decomposing Systems into Modules},
              author = {Parnas, David L.},
              year = {1972},
              journal = {Communications of the ACM},
              volume = {15},
              number = {12},
              pages = {1053--1058},
            }
        """,
        # Homepage: README becomes index.qmd at the project root. Citing here
        # exercises the root-level build path (distinct from user-guide/ pages).
        "README.md": """\
            # gdtest-bibliography

            Synthetic test for project-level `bibliography:` wiring (issue #214).
            This package follows the literate programming tradition [@knuth1984].

            ## Purpose

            A single `bibliography: docs/references.bib` entry in `great-docs.yml`
            should:

            - copy `references.bib` into the build directory, and
            - set `bibliography: references.bib` in the generated `_quarto.yml`,

            so that `[@citation-key]` syntax on *any* page resolves to a formatted
            citation and a References section, with no per-page frontmatter.

            ## References

            ::: {#refs}
            :::
        """,
        # Top-level user-guide page citing two keys with no per-page
        # `bibliography:` frontmatter — relying entirely on the project-level key.
        "user_guide/01-citations.qmd": """\
            ---
            title: Citations
            ---

            Literate programming was introduced by Knuth [@knuth1984], who argued
            that programs should be written for human readers first. The approach
            interleaves prose and code, and is often typeset with LaTeX
            [@lamport1994].

            These citations resolve project-wide because `great-docs.yml` sets a
            single `bibliography:` key — no per-page frontmatter is needed.

            ## References

            ::: {#refs}
            :::
        """,
        # Nested user-guide page (one subdirectory deep). The single project-level
        # key must resolve here too, even though the per-page workaround in the
        # issue required paths that depended on this nesting depth. It reuses
        # knuth1984 (shared with the homepage and the top-level page) and adds a
        # page-local key, parnas1972.
        "user_guide/02-advanced/01-decomposition.qmd": """\
            ---
            title: Modular Decomposition
            ---

            Module boundaries should hide design decisions that are likely to
            change [@parnas1972]. Combining that principle with literate
            programming [@knuth1984] yields documentation that tracks the modular
            structure of the code.

            This page lives one directory deep under `user-guide/`, yet the same
            project-level `bibliography:` key resolves its citations — no
            depth-dependent per-page path is required.

            This page deliberately adds *no* manual References heading: Quarto
            generates the section automatically and titles it from the document
            language (here, the English "References").
        """,
    },
    # ── great-docs.yml ────────────────────────────────────────────────
    "config": {
        "bibliography": "docs/references.bib",
    },
    # ── Expected outcomes ─────────────────────────────────────────────
    "expected": {
        "detected_name": "gdtest-bibliography",
        "detected_module": "gdtest_bibliography",
        "detected_parser": "numpy",
        "export_names": ["weave", "tangle"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": True,
        # Only top-level user-guide pages are listed here; the nested page is
        # verified by dedicated tests (the generic UG test globs non-recursively).
        "user_guide_files": ["01-citations.qmd"],
        "has_license_page": False,
        "has_citation_page": False,
        # Bibliography-specific expectations (consumed by dedicated tests)
        "has_bibliography": True,
        "bibliography_file": "references.bib",
        "citation_keys": ["knuth1984", "lamport1994", "parnas1972"],
        "coverage_exclude": ["nodoc", "bigcl", "supp", "hdg"],
    },
}
