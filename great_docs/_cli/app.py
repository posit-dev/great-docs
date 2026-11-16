"""CLI groups and root command construction"""

from __future__ import annotations

import click

from .. import __version__


class OrderedGroup(click.Group):
    """Click group that lists commands in the order they were added."""

    def list_commands(self, ctx: click.Context) -> list[str]:
        return list(self.commands.keys())


@click.group(cls=OrderedGroup)
@click.version_option(version=__version__, prog_name="great-docs")
def cli():
    """Great Docs: Beautiful documentation for Python packages.

    Great Docs generates professional documentation sites with auto-generated
    API references, CLI documentation, smart navigation, and modern styling.

    Get started with 'great-docs init' to set up your docs, then use
    'great-docs build' to generate your site.
    """
    pass


def register_commands() -> None:
    """Register command families in the public command order"""
    from .build import build, freeze, preview, timings
    from .checks import check_examples, check_links, lint, proofread, seo
    from .ci import ci, setup_github_pages, setup_gitlab_pages
    from .evolution import api_diff_cmd, api_snapshot_cmd, versions
    from .project import changelog, config, init, migrate_layout, scan, uninstall
    from .skills import skill
    from .termshow import termshow

    cli.add_command(init)
    cli.add_command(build)
    cli.add_command(preview)
    cli.add_command(uninstall)
    cli.add_command(config)
    cli.add_command(ci)
    cli.add_command(migrate_layout)
    cli.add_command(scan)
    cli.add_command(freeze)
    cli.add_command(timings)
    cli.add_command(setup_github_pages)
    cli.add_command(setup_gitlab_pages)
    cli.add_command(check_links)
    cli.add_command(check_examples)
    cli.add_command(changelog)
    cli.add_command(proofread)
    cli.add_command(seo)
    cli.add_command(lint)
    cli.add_command(api_diff_cmd)
    cli.add_command(versions)
    cli.add_command(api_snapshot_cmd)
    cli.add_command(skill)
    cli.add_command(termshow)
