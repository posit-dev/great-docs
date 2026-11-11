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
