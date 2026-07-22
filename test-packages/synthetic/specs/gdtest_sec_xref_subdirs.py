"""
gdtest_sec_xref_subdirs — Cross-references into numeric-prefix section subdirs.

Dimensions: N12
Focus: Regression for #215. A custom section whose pages live in
       numerically-prefixed subdirectories (``01-topic-a/``, ``02-topic-b/``)
       and contain cross-references to one another, plus a user-guide page that
       links into the section. ``_fix_numeric_prefix_links`` rewrites those
       links to strip prefixes from every path component (``02-topic-b`` ->
       ``topic-b``), so the section copy must also strip prefixes from
       subdirectory names — otherwise the on-disk file lands at
       ``examples/02-topic-b/widget_demo.qmd`` while the rewritten link points at
       ``examples/topic-b/widget_demo.qmd`` and resolves to a dead link.
"""

SPEC = {
    "name": "gdtest_sec_xref_subdirs",
    "description": "Cross-refs into numeric-prefix section subdirs (#215)",
    "dimensions": ["N12"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-sec-xref-subdirs",
            "version": "0.1.0",
            "description": "Cross-references into numeric-prefix custom section subdirectories",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "display_name": "Section Cross-Ref Subdirs Demo",
        # Custom section whose pages live in numerically-prefixed subdirectories.
        "sections": [
            {"title": "Examples", "dir": "examples", "index": True},
        ],
        # Auto-discovery user guide (a string, not a list) so numeric prefixes
        # are stripped and intra-doc links are rewritten.
        "user_guide": "user_guide",
    },
    "files": {
        "gdtest_sec_xref_subdirs/__init__.py": '''\
            """A test package for cross-references into prefixed section subdirs."""

            __version__ = "0.1.0"
            __all__ = ["render", "compose"]


            def render(template: str) -> str:
                """
                Render a template string.

                Parameters
                ----------
                template
                    The template to render.

                Returns
                -------
                str
                    The rendered output.
                """
                return template


            def compose(parts: list) -> str:
                """
                Compose parts into a single string.

                Parameters
                ----------
                parts
                    The parts to compose.

                Returns
                -------
                str
                    The composed result.
                """
                return "".join(parts)
        ''',
        # Section page in a prefixed subdir that links to a sibling page in a
        # DIFFERENT prefixed subdir. The link uses the authored (prefixed) path.
        "examples/01-topic-a/intro.qmd": """\
            ---
            title: Intro
            description: Introduction to topic A.
            ---

            ## Introduction

            This is topic A. For a hands-on demo, see the
            [widget demo](../02-topic-b/widget_demo.qmd) in topic B.
        """,
        "examples/02-topic-b/widget_demo.qmd": """\
            ---
            title: Widget Demo
            description: A hands-on widget demonstration.
            ---

            ## Widget Demo

            This is topic B. Return to the [intro](../01-topic-a/intro.qmd) for
            background.
        """,
        # User-guide page (auto-discovery) that links INTO the prefixed section
        # subdir. Numeric prefixes are stripped from the user-guide filename and
        # the link is rewritten to the unprefixed section path.
        "user_guide/10-concepts.qmd": """\
            ---
            title: Concepts
            ---

            ## Concepts

            For a concrete example, see the
            [widget demo](../examples/02-topic-b/widget_demo.qmd).
        """,
        "README.md": """\
            # gdtest-sec-xref-subdirs

            A test package demonstrating cross-references into numerically
            prefixed custom section subdirectories (`examples/02-topic-b/`).
        """,
    },
    "expected": {
        "detected_name": "gdtest-sec-xref-subdirs",
        "detected_module": "gdtest_sec_xref_subdirs",
        "detected_parser": "numpy",
        "export_names": ["render", "compose"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "sechdg", "sbsec", "hdg"],
    },
}
