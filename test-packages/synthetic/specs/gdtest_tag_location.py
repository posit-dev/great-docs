"""
gdtest_tag_location — Tag pills at top vs. bottom of pages.

Dimensions: T3
Focus: Tests the tag_location feature which controls placement of tag pills.
       Pages can show tags at the "top" (default, below title) or "bottom"
       (after page metadata / end of content). The global default is set in
       great-docs.yml and individual pages can override via tag-location
       frontmatter. This site exercises both global "bottom" default with
       per-page "top" overrides, and pages that inherit the global default.
"""

SPEC = {
    "name": "gdtest_tag_location",
    "description": "Tag pills at top vs. bottom with per-page overrides",
    "dimensions": ["T3"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-tag-location",
            "version": "0.1.0",
            "description": "A test package for tag_location placement",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "display_name": "Tag Location Demo",
        "site": {
            "show_dates": True,
        },
        "tags": {
            "enabled": True,
            "index_page": True,
            "show_on_pages": True,
            "hierarchical": True,
            "location": "bottom",
            "icons": {
                "Setup": "download",
                "Python": "code",
                "API": "plug",
            },
        },
    },
    "files": {
        "gdtest_tag_location/__init__.py": '''\
            """A test package for the tag location feature."""

            __version__ = "0.1.0"
            __all__ = ["Gadget", "make_gadget"]


            class Gadget:
                """
                A simple gadget.

                Parameters
                ----------
                label
                    Display label for the gadget.
                """

                def __init__(self, label: str):
                    self.label = label

                def activate(self) -> str:
                    """
                    Activate the gadget.

                    Returns
                    -------
                    str
                        Activation message.
                    """
                    return f"Gadget {self.label} activated"


            def make_gadget(label: str) -> Gadget:
                """
                Create a new gadget.

                Parameters
                ----------
                label
                    Display label for the gadget.

                Returns
                -------
                Gadget
                    A new gadget instance.
                """
                return Gadget(label)
        ''',
        # Page 1: inherits global "bottom" — has page metadata dates
        "user_guide/01-intro.qmd": """\
            ---
            title: Introduction
            tags: [Setup, Python]
            date_created: "2025-06-01"
            last_update:
              date: "2026-03-15"
              author: "Alice"
            ---

            Welcome! This page inherits the global tag location (bottom)
            and has page metadata (dates + author). Tags should appear
            *after* the metadata block at the bottom.
        """,
        # Page 2: explicit override to "top" — also has dates
        "user_guide/02-api-guide.qmd": """\
            ---
            title: API Guide
            tags: [API, Python]
            tag-location: top
            date_created: "2025-07-10"
            last_update:
              date: "2026-02-20"
            ---

            This page overrides the global setting and places tags at the top,
            right below the title. Page metadata still appears at the bottom.

            ## Using the API

            Import and use gadgets in your code.
        """,
        # Page 3: inherits global "bottom" — has dates + subtitle
        "user_guide/03-advanced.qmd": """\
            ---
            title: Advanced Patterns
            subtitle: Power-user techniques
            tags: [Python, API]
            date_created: "2025-08-22"
            last_update:
              date: "2026-04-01"
              author: "Bob"
            ---

            This page inherits the global tag location (bottom) and has
            both a subtitle and page metadata. Tags should appear after
            the metadata block.

            ## Multi-Gadget Workflows

            Combine multiple gadgets for complex tasks.
        """,
        # Page 4: explicit "bottom" — no dates (tags under <hr>)
        "user_guide/04-setup.qmd": """\
            ---
            title: Setup Guide
            tags: [Setup]
            tag-location: bottom
            ---

            This page explicitly sets tag-location to bottom and has
            no date metadata. Tags should appear under a horizontal
            rule at the end of content.

            ## Installation

            Install the package via pip.
        """,
        # Page 5: explicit override to "top"
        "user_guide/05-tips.qmd": """\
            ---
            title: Tips and Tricks
            description: Handy shortcuts and lesser-known features.
            tags: [Python, Setup]
            tag-location: top
            ---

            This page overrides to top and has a description field.

            ## Shortcuts

            Use keyboard shortcuts for faster workflows.
        """,
        # Page 6: no tags at all
        "user_guide/06-faq.qmd": """\
            ---
            title: FAQ
            ---

            This page has no tags. No tag pills should appear anywhere.
        """,
        "README.md": """\
            # gdtest-tag-location

            A test package demonstrating the tag_location feature.

            Tags can appear at the top (below title) or bottom (after metadata)
            of each page. The global default is set in great-docs.yml and
            individual pages can override via tag-location frontmatter.
        """,
    },
    "expected": {
        "detected_name": "gdtest-tag-location",
        "detected_module": "gdtest_tag_location",
        "detected_parser": "numpy",
        "export_names": ["Gadget", "make_gadget"],
        "num_exports": 2,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": True,
        "user_guide_files": [
            "01-intro.qmd",
            "02-api-guide.qmd",
            "03-advanced.qmd",
            "04-setup.qmd",
            "05-tips.qmd",
            "06-faq.qmd",
        ],
    },
}
