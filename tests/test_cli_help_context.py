"""CLI help rendering must use the command's own context class.

Rich-click (and other Click extensions) subclass both the command and the
context: ``RichCommand.context_class`` is ``RichContext``, whose formatter
carries the rich-click configuration. Building a plain ``click.Context``
instead produces a plain formatter and crashes rich-click's ``format_help``.
"""

from __future__ import annotations

from pathlib import Path

import click

from great_docs import GreatDocs


class _CustomContext(click.Context):
    def make_formatter(self) -> click.HelpFormatter:
        formatter = super().make_formatter()
        formatter.config = "custom"
        return formatter


class _CustomCommand(click.Command):
    context_class = _CustomContext

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        # rich-click's format_help accesses formatter.config; a plain Click
        # context would build a formatter without it.
        assert formatter.config == "custom"
        super().format_help(ctx, formatter)


def test_get_click_help_text_uses_command_context_class(tmp_path: Path) -> None:
    command = _CustomCommand("demo", help="Demo command.")
    docs = GreatDocs(project_path=str(tmp_path))

    help_text = docs._get_click_help_text(command, "demo")

    assert "Usage:" in help_text
    assert "Demo command." in help_text
