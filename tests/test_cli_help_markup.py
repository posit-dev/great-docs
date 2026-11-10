"""
Check Rich markup handling in structured CLI help
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock

import click
import pytest

from great_docs import GreatDocs
from great_docs._cliref import click as cli_click
from great_docs._cliref import render as cli_render

rich_click = pytest.importorskip("rich_click")


@pytest.fixture(autouse=True)
def markup_globals(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rich_click.rich_click, "TEXT_MARKUP", "ansi")
    monkeypatch.setattr(rich_click.rich_click, "TEXT_EMOJIS", False)


def test_rich_click_option_help_is_plain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rich_click.rich_click, "TEXT_MARKUP", "rich")

    @rich_click.command()
    @rich_click.option(
        "--dev", is_flag=True, help="Add a [b]Dump Debug[/] button in [cyan]/tmp[/]."
    )
    def main(dev: bool) -> None:
        pass

    info = cli_click.extract_command(main, "demo")

    assert info["options"][0]["help"] == "Add a Dump Debug button in /tmp."
    assert main.params[0].help == "Add a [b]Dump Debug[/] button in [cyan]/tmp[/]."


def test_rich_click_command_help_is_plain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rich_click.rich_click, "TEXT_MARKUP", "rich")
    help_text = "Say [b]hello[/] to [cyan]everyone[/].\n\nExamples:\n    demo [b]hello[/]"
    cmd = rich_click.RichCommand("demo", help=help_text)

    info = cli_click.extract_command(cmd, "demo")

    assert info["help"] == "Say hello to everyone.\n\nExamples:\n    demo hello"
    assert info["short_help"] == "Say hello to everyone."
    assert info["description"] == "Say hello to everyone."
    assert info["examples"] == ["demo hello"]
    assert cmd.help == help_text
    assert cmd.short_help is None


def test_rich_click_ansi_markup_is_kept() -> None:
    @rich_click.command()
    @rich_click.option("--value", help="Literal [b] bracket.")
    def main(value: str) -> None:
        pass

    info = cli_click.extract_command(main, "demo")

    assert info["options"][0]["help"] == "Literal [b] bracket."


def test_plain_click_help_keeps_brackets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rich_click.rich_click, "TEXT_MARKUP", "rich")

    @click.command(help="Keep [b]literal[/] command help.", short_help="Keep [b]short[/] help.")
    @click.option("--value", help="Default is [default: 1].")
    def main(value: str) -> None:
        pass

    info = cli_click.extract_command(main, "demo")

    assert info["options"][0]["help"] == "Default is [default: 1]."
    assert info["help"] == "Keep [b]literal[/] command help."
    assert info["short_help"] == "Keep [b]short[/] help."


def test_rich_click_markdown_markup_is_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rich_click.rich_click, "TEXT_MARKUP", "markdown")

    @rich_click.command()
    @rich_click.option("--value", help="Literal [b] bracket and **bold**.")
    def main(value: str) -> None:
        pass

    info = cli_click.extract_command(main, "demo")

    assert info["options"][0]["help"] == "Literal [b] bracket and **bold**."


@pytest.mark.parametrize("configuration", ["context_settings", "decorator", "object"])
@pytest.mark.parametrize(
    ("global_mode", "command_mode", "expected"),
    [
        ("ansi", "rich", "Keep this value."),
        ("rich", "ansi", "Keep [b]this[/] value."),
        ("rich", "markdown", "Keep [b]this[/] value."),
    ],
)
def test_command_configuration_overrides_globals(
    monkeypatch: pytest.MonkeyPatch,
    configuration: str,
    global_mode: str,
    command_mode: str,
    expected: str,
) -> None:
    monkeypatch.setattr(rich_click.rich_click, "TEXT_MARKUP", global_mode)
    help_text = "Keep [b]this[/] value."
    cmd = rich_click.RichCommand(
        "demo",
        help=help_text,
        short_help=help_text,
        params=[rich_click.RichOption(["--value"], help=help_text)],
    )
    settings = {"text_markup": command_mode}
    if configuration == "decorator":
        cmd = rich_click.rich_config(help_config=settings)(cmd)
    elif configuration == "object":
        cmd.context_settings["rich_help_config"] = rich_click.RichHelpConfiguration(**settings)
    else:
        cmd.context_settings["rich_help_config"] = settings

    info = cli_click.extract_command(cmd, "demo")

    assert info["help"] == expected
    assert info["short_help"] == expected
    assert info["description"] == expected
    assert info["options"][0]["help"] == expected
    assert info["help_text"] == cli_click.help_output(cmd, "demo")
    assert cmd.help == help_text
    assert cmd.short_help == help_text
    assert cmd.params[0].help == help_text


@pytest.mark.parametrize("child_mode", [None, "ansi", "markdown"])
def test_nested_commands_inherit_configuration_with_local_overrides(child_mode: str | None) -> None:
    help_text = "Use [b]nested[/] help."
    child = rich_click.RichCommand(
        "child", help=help_text, params=[rich_click.RichOption(["--value"], help=help_text)]
    )
    if child_mode:
        child.context_settings["rich_help_config"] = {"text_markup": child_mode}
    nested = rich_click.RichGroup("nested", help=help_text, commands={"child": child})
    root = rich_click.RichGroup(
        "root",
        help=help_text,
        context_settings={"rich_help_config": {"text_markup": "rich"}},
        commands={"nested": nested},
    )

    info = cli_click.extract_command(root, "root")
    nested_info = info["commands"][0]
    child_info = nested_info["commands"][0]

    assert info["help"] == "Use nested help."
    assert nested_info["help"] == "Use nested help."
    expected = help_text if child_mode else "Use nested help."
    assert child_info["help"] == expected
    assert child_info["options"][0]["help"] == expected
    assert child_info["full_path"] == "root nested child"


@pytest.mark.parametrize(("emojis", "expected"), [(False, "Key :smile:"), (True, "Key 😄")])
def test_emoji_configuration_is_inherited(emojis: bool, expected: str) -> None:
    help_text = "Key [b]:smile:[/]"
    child = rich_click.RichCommand(
        "child", help=help_text, params=[rich_click.RichOption(["--value"], help=help_text)]
    )
    root = rich_click.RichGroup(
        "root",
        context_settings={"rich_help_config": {"text_markup": "rich", "text_emojis": emojis}},
        commands={"child": child},
    )

    info = cli_click.extract_command(root, "root")["commands"][0]

    assert info["help"] == expected
    assert info["short_help"] == expected
    assert info["options"][0]["help"] == expected


def test_malformed_short_help_is_kept() -> None:
    cmd = rich_click.RichCommand(
        "demo",
        help="Valid [b]help[/]",
        short_help="Keep [/broken] intact.",
        context_settings={"rich_help_config": {"text_markup": "rich"}},
    )

    info = cli_click.extract_command(cmd, "demo")

    assert info["help"] == "Valid help"
    assert info["short_help"] == "Keep [/broken] intact."


def test_extraction_does_not_run_callbacks() -> None:
    command_callback = Mock(side_effect=AssertionError("Command callback ran"))
    parameter_callback = Mock(side_effect=AssertionError("Parameter callback ran"))
    default = Mock(side_effect=AssertionError("Option default ran"))
    cmd = rich_click.RichCommand(
        "demo",
        callback=command_callback,
        help="Use [b]help[/].",
        context_settings={"rich_help_config": {"text_markup": "rich"}},
        params=[
            rich_click.RichOption(["--required"], required=True, callback=parameter_callback),
            rich_click.RichOption(["--optional"], default=default),
        ],
    )

    info = cli_click.extract_command(cmd, "demo")

    assert info["help"] == "Use help."
    command_callback.assert_not_called()
    parameter_callback.assert_not_called()
    default.assert_not_called()


def test_plain_click_works_without_rich_click(monkeypatch: pytest.MonkeyPatch) -> None:
    cmd = click.Command("demo", help="Keep [b]literal[/] help.")
    monkeypatch.setitem(sys.modules, "rich_click", None)

    info = cli_click.extract_command(cmd, "demo")

    assert info["help"] == "Keep [b]literal[/] help."


def test_unexpected_formatter_errors_propagate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        rich_click.RichContext, "make_formatter", Mock(side_effect=RuntimeError("Formatter failed"))
    )

    with pytest.raises(RuntimeError, match="Formatter failed"):
        cli_click.extract_command(rich_click.RichCommand("demo"), "demo")


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("rich", "Keep this value."),
        ("ansi", "Keep [b]this[/] value."),
        ("markdown", "Keep [b]this[/] value."),
    ],
)
def test_generated_pages_respect_markup_mode(tmp_path: Path, mode: str, expected: str) -> None:
    help_text = "Keep [b]this[/] value."
    cmd = rich_click.RichCommand(
        "demo",
        help=help_text,
        short_help=help_text,
        context_settings={"rich_help_config": {"text_markup": mode}},
        params=[rich_click.RichOption(["--value"], help=help_text)],
    )
    docs = GreatDocs(project_path=tmp_path)

    info = cli_click.extract_command(cmd, "demo")
    cli_render.write_pages(docs._config, docs.layout, info, report=lambda message: None)

    root_page = (docs.layout.build_dir / "reference/cli/demo.qmd").read_text()
    index_page = (docs.layout.build_dir / "reference/cli/index.qmd").read_text()
    assert expected in root_page
    assert expected in index_page
    if mode == "rich":
        # Full help is rendered separately; inspect only the structured page sections.
        structured_page = root_page.replace(info["help_text"].rstrip(), "", 1)
        assert "[b]" not in structured_page
        assert "[/]" not in structured_page
