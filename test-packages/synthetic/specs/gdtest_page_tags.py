"""
gdtest_page_tags — Page tags with hierarchical tags, shadow tags, and tag icons.

Dimensions: T1
Focus: Tests the page tags feature: tagged user-guide pages, auto-generated
       tags/index.qmd, tag pills above page titles via page-tags.js, hierarchical
       tag organization, shadow tags excluded from public view, and tag icons.
"""

SPEC = {
    "name": "gdtest_page_tags",
    "description": "Page tags with hierarchy, shadow tags, and tag icons",
    "dimensions": ["T1"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-page-tags",
            "version": "0.1.0",
            "description": "A test package for the page tags feature",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "display_name": "Page Tags Demo",
        "tags": {
            "enabled": True,
            "index_page": True,
            "show_on_pages": True,
            "hierarchical": True,
            "icons": {
                "Python": "code",
                "Tutorial": "book-open",
                "API": "plug",
            },
            "shadow": ["needs-review", "internal"],
        },
    },
    "files": {
        "gdtest_page_tags/__init__.py": '''\
            """A test package for the page tags feature."""

            __version__ = "0.1.0"
            __all__ = ["Widget", "create_widget", "WidgetError"]


            class WidgetError(Exception):
                """Raised when a widget operation fails."""


            class Widget:
                """
                A configurable widget.

                Parameters
                ----------
                name
                    Display name of the widget.
                size
                    Size in pixels (default 100).
                """

                def __init__(self, name: str, size: int = 100):
                    self.name = name
                    self.size = size

                def render(self) -> str:
                    """
                    Render the widget to HTML.

                    Returns
                    -------
                    str
                        An HTML string.
                    """
                    return f"<widget>{self.name}</widget>"

                def resize(self, new_size: int) -> None:
                    """
                    Resize the widget.

                    Parameters
                    ----------
                    new_size
                        New size in pixels.

                    Raises
                    ------
                    WidgetError
                        If new_size is negative.
                    """
                    if new_size < 0:
                        raise WidgetError("Size must be non-negative")
                    self.size = new_size


            def create_widget(name: str, size: int = 100) -> Widget:
                """
                Factory function for creating widgets.

                Parameters
                ----------
                name
                    Display name of the widget.
                size
                    Size in pixels (default 100).

                Returns
                -------
                Widget
                    A new widget instance.
                """
                return Widget(name, size)
        ''',
        "user_guide/01-intro.qmd": """\
            ---
            title: Introduction
            tags: [Tutorial, Getting Started]
            ---

            Welcome to the Page Tags Demo user guide!

            This guide covers the basics of widget creation.
        """,
        "user_guide/02-configuration.qmd": """\
            ---
            title: Configuration
            tags: [Python, Python/Configuration, Tutorial]
            ---

            Learn how to configure widgets for your project.

            ## Basic Setup

            Create a widget with default settings:

            ```python
            from gdtest_page_tags import create_widget

            w = create_widget("my-widget")
            ```
        """,
        "user_guide/03-advanced.qmd": """\
            ---
            title: Advanced Usage
            tags: [Python/Advanced, API, needs-review]
            ---

            Advanced patterns for power users.

            ## Custom Rendering

            Override the default render method for custom output.
        """,
        "user_guide/04-errors.qmd": """\
            ---
            title: Error Handling
            tags: [Python/Advanced, API, internal]
            ---

            How to handle errors when working with widgets.

            ## WidgetError

            The `WidgetError` exception is raised when an invalid operation
            is attempted.
        """,
        "user_guide/05-rendering.qmd": """\
            ---
            title: Rendering Widgets
            subtitle: A deep dive into the rendering pipeline
            tags: [Python, Tutorial]
            ---

            This page has a subtitle to test tag pill placement.

            ## The Render Pipeline

            Widgets go through a multi-step rendering pipeline before
            producing their final HTML output.
        """,
        "user_guide/06-faq.qmd": """\
            ---
            title: Frequently Asked Questions
            ---

            This page has no tags at all.

            ## Why use widgets?

            Widgets provide a reusable, configurable abstraction for
            building HTML components.
        """,
        "user_guide/07-tips.qmd": """\
            ---
            title: Tips and Tricks
            description: Handy shortcuts and lesser-known features.
            tags: [Tutorial]
            ---

            This page uses description (not subtitle) with tags.

            ## Keyboard Shortcuts

            Use Ctrl+W to close the current widget.
        """,
        "user_guide/08-best-practices.qmd": """\
            ---
            title: Best Practices
            subtitle: Patterns for production-quality widgets
            description: A curated collection of widget best practices.
            tags: [Python, Tutorial]
            ---

            This page has both subtitle and description, plus tags.

            ## Naming Conventions

            Use descriptive names for your widgets.
        """,
        "README.md": """\
            # gdtest-page-tags

            A test package demonstrating the page tags feature.

            ## Features

            - Tagged user guide pages for discoverability
            - Hierarchical tag organization
            - Shadow tags for internal use
            - Tag icons for visual cues
        """,
    },
    "expected": {
        "detected_name": "gdtest-page-tags",
        "detected_module": "gdtest_page_tags",
        "detected_parser": "numpy",
        "export_names": ["Widget", "WidgetError", "create_widget"],
        "num_exports": 3,
        "section_titles": ["Classes", "Functions", "Exceptions"],
        "has_user_guide": True,
        "user_guide_files": [
            "01-intro.qmd",
            "02-configuration.qmd",
            "03-advanced.qmd",
            "04-errors.qmd",
            "05-rendering.qmd",
            "06-faq.qmd",
            "07-tips.qmd",
            "08-best-practices.qmd",
        ],
    },
}
