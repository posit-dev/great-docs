"""
Check Rich markup handling in structured CLI help
"""

from __future__ import annotations

import click
import pytest

from great_docs._cliref import click as cli_click

rich_click = pytest.importorskip("rich_click")


def test_rich_click_option_help_is_plain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rich_click.rich_click, "TEXT_MARKUP", "rich")

    @rich_click.command()
    @rich_click.option(
        "--dev",
        is_flag=True,
        help="Add a [b]Dump Debug[/] button in [cyan]/tmp[/].",
    )
    def main(dev: bool) -> None:
        """Demonstrate a command"""

    info = cli_click.extract_command(main, "demo")

    assert info["options"][0]["help"] == "Add a Dump Debug button in /tmp."


def test_rich_click_command_help_is_plain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rich_click.rich_click, "TEXT_MARKUP", "rich")

    @rich_click.command()
    def main() -> None:
        """Say [b]hello[/] to [cyan]everyone[/]"""

    info = cli_click.extract_command(main, "demo")

    assert info["help"] == "Say hello to everyone"
    assert info["short_help"] == "Say hello to everyone"
    assert info["description"] == "Say hello to everyone"


def test_rich_click_ansi_markup_is_kept() -> None:
    @rich_click.command()
    @rich_click.option("--value", help="Literal [b] bracket.")
    def main(value: str) -> None:
        """Demonstrate a command"""

    info = cli_click.extract_command(main, "demo")

    assert info["options"][0]["help"] == "Literal [b] bracket."


def test_plain_click_help_keeps_brackets() -> None:
    @click.command()
    @click.option("--value", help="Default is [default: 1].")
    def main(value: str) -> None:
        """Demonstrate a command"""

    info = cli_click.extract_command(main, "demo")

    assert info["options"][0]["help"] == "Default is [default: 1]."


def test_rich_click_markdown_markup_is_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rich_click.rich_click, "TEXT_MARKUP", "markdown")

    @rich_click.command()
    @rich_click.option("--value", help="Literal [b] bracket and **bold**.")
    def main(value: str) -> None:
        """Demonstrate a command"""

    info = cli_click.extract_command(main, "demo")

    assert info["options"][0]["help"] == "Literal [b] bracket and **bold**."
