"""Structured CLI help must not contain rich-click markup.

Rich-click renders ``[b]...[/]`` and ``[cyan]...[/]`` in ``--help``. The
structured option/command fields are written into Quarto pages, where those
tags would appear literally, so extraction has to strip them when rich markup
is active.
"""

from __future__ import annotations

from pathlib import Path

import click
import pytest

from great_docs import GreatDocs

rich_click = pytest.importorskip("rich_click")


def _make_gd(tmp_path: Path) -> GreatDocs:
    (tmp_path / "great-docs.yml").write_text("module: mypkg\n", encoding="utf-8")
    return GreatDocs(project_path=str(tmp_path))


def test_rich_click_option_help_is_plain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rich_click.rich_click, "TEXT_MARKUP", "rich")

    @rich_click.command()
    @rich_click.option(
        "--dev",
        is_flag=True,
        help="Add a [b]Dump Debug[/] button in [cyan]/tmp[/].",
    )
    def main(dev: bool) -> None:
        """Demo command."""

    info = _make_gd(tmp_path)._extract_click_command(main, "demo")

    assert info["options"][0]["help"] == "Add a Dump Debug button in /tmp."


def test_rich_click_command_help_is_plain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rich_click.rich_click, "TEXT_MARKUP", "rich")

    @rich_click.command()
    def main() -> None:
        """Say [b]hello[/] to [cyan]everyone[/]."""

    info = _make_gd(tmp_path)._extract_click_command(main, "demo")

    assert info["help"] == "Say hello to everyone."
    assert info["short_help"] == "Say hello to everyone."
    assert info["description"] == "Say hello to everyone."


def test_rich_click_ansi_markup_is_kept(tmp_path: Path) -> None:
    @rich_click.command()
    @rich_click.option("--value", help="Literal [b] bracket.")
    def main(value: str) -> None:
        """Demo command."""

    info = _make_gd(tmp_path)._extract_click_command(main, "demo")

    assert info["options"][0]["help"] == "Literal [b] bracket."


def test_plain_click_help_keeps_brackets(tmp_path: Path) -> None:
    @click.command()
    @click.option("--value", help="Default is [default: 1].")
    def main(value: str) -> None:
        """Demo command."""

    info = _make_gd(tmp_path)._extract_click_command(main, "demo")

    assert info["options"][0]["help"] == "Default is [default: 1]."


def test_rich_click_markdown_markup_is_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rich_click.rich_click, "TEXT_MARKUP", "markdown")

    @rich_click.command()
    @rich_click.option("--value", help="Literal [b] bracket and **bold**.")
    def main(value: str) -> None:
        """Demo command."""

    info = _make_gd(tmp_path)._extract_click_command(main, "demo")

    assert info["options"][0]["help"] == "Literal [b] bracket and **bold**."
