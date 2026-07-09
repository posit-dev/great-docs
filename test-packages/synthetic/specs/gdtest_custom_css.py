"""
gdtest_custom_css — Project-level custom CSS forwarded from great-docs.yml.

Dimensions: A1, B1, C1, D1, E6, F1, G1, Q8
Focus: A single project-level `site.css:` key in great-docs.yml (issue #248)
       is copied into the build directory and wired into _quarto.yml's
       `format.html.css`, mirroring the working `bibliography`/`csl` pattern.
"""

SPEC = {
    "name": "gdtest_custom_css",
    "description": "Project-level custom CSS forwarded into _quarto.yml",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F1", "G1", "Q8"],
    # ── Project metadata ─────────────────────────────────────────────
    "pyproject_toml": {
        "project": {
            "name": "gdtest-custom-css",
            "version": "0.1.0",
            "description": "Synthetic test for project-level custom CSS wiring",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    # ── Source files ──────────────────────────────────────────────────
    "files": {
        "gdtest_custom_css/__init__.py": '''\
            """Package demonstrating project-level custom CSS."""

            __version__ = "0.1.0"
            __all__ = ["widget"]


            def widget(name: str) -> str:
                """
                Build a text widget.

                Parameters
                ----------
                name
                    Label for the widget.

                Returns
                -------
                str
                    The rendered widget.
                """
                return f"[{name}]"
        ''',
        # The stylesheet lives outside the build tree, under docs/. The
        # great-docs.yml `site.css:` key points here; Great Docs copies it
        # into the build directory at build time (issue #248).
        "docs/custom.css": """\
            /* gdtest-custom-css marker rule: unique and easily greppable so
               tests can confirm this exact file was linked, not just any
               stylesheet. */
            .gdtest-custom-css-marker {
              --gdtest-custom-css: applied;
            }
        """,
        "user_guide/01-page.qmd": """\
            ---
            title: Page
            ---

            A user-guide page, to confirm project-level CSS applies outside the
            homepage too.
        """,
    },
    # ── great-docs.yml ────────────────────────────────────────────────
    "config": {
        "site": {
            "css": ["docs/custom.css"],
        },
    },
    # ── Expected outcomes ─────────────────────────────────────────────
    "expected": {
        "detected_name": "gdtest-custom-css",
        "detected_module": "gdtest_custom_css",
        "detected_parser": "numpy",
        "export_names": ["widget"],
        "num_exports": 1,
        "section_titles": ["Functions"],
        "has_user_guide": True,
        "user_guide_files": ["01-page.qmd"],
        "has_license_page": False,
        "has_citation_page": False,
        # Custom-CSS-specific expectations (consumed by dedicated tests)
        "has_custom_css": True,
        "custom_css_file": "custom.css",
        "coverage_exclude": ["nodoc", "bigcl", "supp", "hdg"],
    },
}
