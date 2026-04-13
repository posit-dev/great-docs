"""
gdtest_page_status — Page status badges in sidebar and on page titles.

Dimensions: T2
Focus: Tests the page_status feature: pages annotated with `status:` frontmatter
       display visual badges in the sidebar navigation and below page titles.
       Built-in statuses (new, updated, beta, deprecated, experimental) and a
       custom status (draft) are exercised. Pages without status should show
       no badge. The _page_status.json data file should be generated and injected
       inline as window.__GD_STATUS_DATA__.
"""

SPEC = {
    "name": "gdtest_page_status",
    "description": "Page status badges in sidebar navigation and on pages",
    "dimensions": ["T2"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-page-status",
            "version": "0.1.0",
            "description": "A test package for the page status badges feature",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "display_name": "Page Status Demo",
        "page_status": {
            "enabled": True,
            "show_in_sidebar": True,
            "show_on_pages": True,
            "statuses": {
                "draft": {
                    "label": "Draft",
                    "icon": "pencil",
                    "color": "#999999",
                    "description": "Work in progress",
                },
            },
        },
    },
    "files": {
        "gdtest_page_status/__init__.py": '''\
            """A test package for the page status badges feature."""

            __version__ = "0.1.0"
            __all__ = ["Processor", "run_pipeline", "PipelineError"]


            class PipelineError(Exception):
                """Raised when a pipeline step fails."""


            class Processor:
                """
                A data processor that runs a pipeline of steps.

                Parameters
                ----------
                name
                    Processor name.
                steps
                    Number of steps in the pipeline.
                """

                def __init__(self, name: str, steps: int = 3):
                    self.name = name
                    self.steps = steps

                def execute(self) -> str:
                    """
                    Execute the processing pipeline.

                    Returns
                    -------
                    str
                        A summary of the execution.
                    """
                    return f"Processed {self.steps} steps"

                def validate(self) -> bool:
                    """
                    Validate pipeline configuration.

                    Returns
                    -------
                    bool
                        True if valid.

                    Raises
                    ------
                    PipelineError
                        If validation fails.
                    """
                    if self.steps <= 0:
                        raise PipelineError("Steps must be positive")
                    return True


            def run_pipeline(name: str, steps: int = 3) -> str:
                """
                Run a named pipeline.

                Parameters
                ----------
                name
                    Pipeline name.
                steps
                    Number of steps (default 3).

                Returns
                -------
                str
                    Execution summary.
                """
                p = Processor(name, steps)
                p.validate()
                return p.execute()
        ''',
        "user_guide/01-getting-started.qmd": """\
            ---
            title: Getting Started
            status: new
            ---

            Welcome to the Page Status Demo!

            This page has `status: new` and should show a green
            "New" badge in the sidebar and below the title.
        """,
        "user_guide/02-configuration.qmd": """\
            ---
            title: Configuration Guide
            status: updated
            ---

            Learn the configuration options.

            This page has `status: updated` and should show a blue
            "Updated" badge.
        """,
        "user_guide/03-advanced.qmd": """\
            ---
            title: Advanced Usage
            status: beta
            ---

            Advanced features that are still in beta.

            This page has `status: beta` and should show an amber
            "Beta" badge with a flask icon.
        """,
        "user_guide/04-migration.qmd": """\
            ---
            title: Migration from v1
            status: deprecated
            ---

            This migration guide is deprecated.

            The v1 API has been removed. This page has `status: deprecated`
            and should show a red "Deprecated" badge with a warning icon.
        """,
        "user_guide/05-experimental.qmd": """\
            ---
            title: Experimental Features
            status: experimental
            ---

            These features are experimental and may change.

            This page has `status: experimental` and should show a
            purple "Experimental" badge.
        """,
        "user_guide/06-draft-notes.qmd": """\
            ---
            title: Draft Notes
            status: draft
            ---

            This page uses a custom status `draft` defined in
            the great-docs.yml configuration.
        """,
        "user_guide/07-stable.qmd": """\
            ---
            title: Stable Features
            ---

            This page has no status and should NOT display any
            status badge.
        """,
        "user_guide/08-subtitle-only.qmd": """\
            ---
            title: Subtitle Only
            subtitle: A page with a subtitle but no description
            status: new
            ---

            This page tests the badge layout when a subtitle is present
            but there is no description.
        """,
        "user_guide/09-description-only.qmd": """\
            ---
            title: Description Only
            description: A page with a description but no subtitle
            status: beta
            ---

            This page tests the badge layout when a description is present
            but there is no subtitle.
        """,
        "user_guide/10-subtitle-and-description.qmd": """\
            ---
            title: Subtitle and Description
            subtitle: Both subtitle and description present
            description: This page has both a subtitle and a description alongside a status badge.
            status: updated
            ---

            This page tests the badge layout when both a subtitle and a
            description are present.
        """,
        "user_guide/11-neither.qmd": """\
            ---
            title: Title Only
            status: deprecated
            ---

            This page has only a title (no subtitle, no description)
            with a status badge. The simplest layout case.
        """,
        "README.md": """\
            # gdtest-page-status

            A test package demonstrating page status badges.

            ## Features

            - Visual status indicators in sidebar navigation
            - Page-level status banners below titles
            - Built-in statuses: new, updated, beta, deprecated, experimental
            - Custom status definitions via configuration
        """,
    },
    "expected": {
        "detected_name": "gdtest-page-status",
        "detected_module": "gdtest_page_status",
        "detected_parser": "numpy",
        "export_names": ["PipelineError", "Processor", "run_pipeline"],
        "num_exports": 3,
        "section_titles": ["Classes", "Functions", "Exceptions"],
        "has_user_guide": True,
        "user_guide_files": [
            "01-getting-started.qmd",
            "02-configuration.qmd",
            "03-advanced.qmd",
            "04-migration.qmd",
            "05-experimental.qmd",
            "06-draft-notes.qmd",
            "07-stable.qmd",
            "08-subtitle-only.qmd",
            "09-description-only.qmd",
            "10-subtitle-and-description.qmd",
            "11-neither.qmd",
        ],
    },
}
