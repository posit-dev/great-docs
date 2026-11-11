"""
gdtest_webmcp — A site with WebMCP turned on and every feature its tools read.

Focus: `webmcp: true` with an origin-trial token, on a site that has something for most
       WebMCP tools: an API whose method and function share the short name `spin` (so
       neither keeps it as an alias), a Click CLI with a nested group, three user guide
       pages (one opted out with `webmcp: false`, one a draft), a blog with one post, and
       a curated skill with a companion file.

Static checks: `gd-webmcp.json` lists the pages, API, CLI and skills; the opted-out page
carries the `gd-no-webmcp` body class; the draft is left out of the manifest; every page
loads `webmcp.js` after its settings block, which names the site's features; the
origin-trial `<meta>` is in `<head>`; and `llms.txt` has the WebMCP section.

The package has no GitHub repository, so the build writes no changelog from its releases,
and the site leaves out `get_changelog`.
"""

SPEC = {
    "name": "gdtest_webmcp",
    "description": "WebMCP tools on a site with an API, CLI, guide, blog and skill",
    "dimensions": ["A1", "B1", "C4", "D1", "E6", "F1", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-webmcp",
            "version": "0.1.0",
            "description": "A package for trying the WebMCP tools",
            "license": "MIT",
            "requires-python": ">=3.10",
            "scripts": {
                "gdtest-webmcp": "gdtest_webmcp.cli:cli",
            },
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "webmcp": {
            "enabled": True,
            "origin_trials": ["gdtest-webmcp-origin-trial-token"],
        },
        "cli": {
            "enabled": True,
        },
        "sections": [
            {"title": "Blog", "dir": "blog", "type": "blog"},
        ],
    },
    "files": {
        "gdtest_webmcp/__init__.py": '''\
            """A package for trying the WebMCP tools."""

            __version__ = "0.1.0"
            __all__ = ["Widget", "make_widget", "spin"]


            class Widget:
                """
                A widget that spins.

                Parameters
                ----------
                name
                    The widget's name.
                """

                def __init__(self, name: str):
                    self.name = name
                    self.speed = 0

                def spin(self, speed: int = 1) -> "Widget":
                    """
                    Spin the widget.

                    Parameters
                    ----------
                    speed
                        Turns per second.

                    Returns
                    -------
                    Widget
                        The widget, spinning.
                    """
                    self.speed = speed
                    return self

                def stop(self) -> "Widget":
                    """
                    Stop the widget.

                    Returns
                    -------
                    Widget
                        The widget, at rest.
                    """
                    self.speed = 0
                    return self


            def make_widget(name: str) -> Widget:
                """
                Make a widget.

                Parameters
                ----------
                name
                    The widget's name.

                Returns
                -------
                Widget
                    A new widget.

                Examples
                --------
                >>> make_widget("gear").name
                'gear'
                """
                return Widget(name)


            def spin(widget: Widget, speed: int = 1) -> Widget:
                """
                Spin a widget.

                Parameters
                ----------
                widget
                    The widget to spin.
                speed
                    Turns per second.

                Returns
                -------
                Widget
                    The widget, spinning.
                """
                return widget.spin(speed)
        ''',
        "gdtest_webmcp/cli.py": '''\
            """Command-line interface for gdtest-webmcp."""

            import click


            @click.group()
            def cli():
                """gdtest-webmcp: spin widgets from the command line."""


            @cli.command()
            @click.argument("name")
            @click.option("--speed", "-s", default=1, help="Turns per second.")
            def spin(name: str, speed: int) -> None:
                """Spin the widget called NAME."""
                click.echo(f"{name} spins at {speed}")


            @cli.group()
            def config():
                """Read and change the settings."""


            @config.command()
            def show() -> None:
                """Show the settings."""
                click.echo("speed = 1")
        ''',
        "docs/user_guide/01-getting-started.qmd": """\
            ---
            title: Getting Started
            description: Make a widget and spin it.
            ---

            Make a widget with `make_widget()`, then spin it.

            ## Spinning

            ```python
            from gdtest_webmcp import make_widget

            make_widget("gear").spin(speed=3)
            ```

            ## Stopping

            Call `Widget.stop()` to bring it to rest.
        """,
        "docs/user_guide/02-internal-notes.qmd": """\
            ---
            title: Internal Notes
            webmcp: false
            ---

            This page opts out of WebMCP, so it registers no tools.
        """,
        "docs/user_guide/03-roadmap.qmd": """\
            ---
            title: Roadmap
            draft: true
            ---

            This draft is left out of the site and the WebMCP manifest.
        """,
        "docs/blog/first-post/index.qmd": """\
            ---
            title: Widgets Spin Faster
            author: Jane Smith
            date: 2026-05-01
            categories: [releases]
            description: What's new in widgets.
            ---

            Widgets spin faster in this release.

            ## What Changed

            `Widget.spin()` takes a `speed`.
        """,
        "skills/gdtest-webmcp/SKILL.md": """\
            ---
            name: gdtest-webmcp
            description: >
              Make and spin widgets with gdtest-webmcp. Use when writing Python code
              that creates widgets or controls their speed.
            license: MIT
            ---

            # gdtest-webmcp

            ## Gotchas

            1. **`spin()` returns the widget**, so calls can be chained.
            2. A widget starts at rest: call `Widget.spin()` before `Widget.stop()`.

            See [the widget notes](references/widgets.md) for more.
        """,
        "skills/gdtest-webmcp/references/widgets.md": """\
            # Widget Notes

            Every widget has a name and a speed in turns per second.
        """,
        "README.md": """\
            # gdtest-webmcp

            A package for trying the WebMCP tools in a browser that supports them.
        """,
    },
    "expected": {
        "detected_name": "gdtest-webmcp",
        "detected_module": "gdtest_webmcp",
        "detected_parser": "numpy",
        "export_names": ["Widget", "make_widget", "spin"],
        "num_exports": 3,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": True,
        "user_guide_files": [
            "01-getting-started.qmd",
            "02-internal-notes.qmd",
            "03-roadmap.qmd",
        ],
        "cli_enabled": True,
        "cli_has_groups": True,
        "cli_group_names": ["config"],
        "has_skill_md": True,
        "has_skills_page": True,
        "skill_is_curated": True,
        "files_exist": [
            "gd-webmcp.json",
            "webmcp.js",
            "llms.txt",
            ".well-known/agent-skills/index.json",
            "user-guide/getting-started.html",
            "user-guide/internal-notes.html",
        ],
        "coverage_exclude": ["nodoc", "bigcl", "supp", "hdg"],
    },
}
