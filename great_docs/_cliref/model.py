"""
The command tree that a CLI reference documents

The Click, Go and Rust extractors build these dictionaries, and the page renderer and the
llms.txt writer read them. Keys other than the names are optional, because the Go and Rust
extractors fill only those their help output provides.
"""

from __future__ import annotations

from typing import Required, TypedDict


class CliOption(TypedDict, total=False):
    """An option of a command, such as `--verbose`"""

    names: Required[list[str]]
    """The option's flags, shortest first."""

    name_display: str
    """The flags joined for display, such as `-v, --verbose`."""

    help: str
    """The option's help text."""

    type: str | None
    """The value type in upper case, or `None` for a flag."""

    choices: list[str]
    """The values a Click `Choice` accepts, as typed on the command line."""

    default: object
    """The default value, or `None` when the option has none."""

    required: bool
    """Whether the command fails without the option."""

    is_flag: bool
    """Whether the option takes no value."""

    multiple: bool
    """Whether the option may be repeated."""

    envvar: str | list[str] | tuple[str, ...] | None
    """The environment variables that supply the value."""

    show_default: object
    """Click's `show_default` setting."""

    is_eager: bool
    """Whether Click processes the option before the others."""

    hidden: bool
    """Whether the option is left out of the reference."""

    deprecated: bool | str
    """Whether the option is deprecated, or Click's deprecation message for it."""


class CliArgument(TypedDict, total=False):
    """A positional argument of a command"""

    name: Required[str]
    """The argument's parameter name."""

    name_display: str
    """The name shown in usage lines."""

    help: str
    """The argument's help text."""

    type: str | None
    """The value type in upper case, or `None` for text."""

    choices: list[str]
    """The values a Click `Choice` accepts, as typed on the command line."""

    default: object
    """The default value, or `None` when the argument has none."""

    required: bool
    """Whether the command fails without the argument."""

    nargs: int
    """The number of values the argument takes; `-1` means any number."""

    deprecated: bool | str
    """Whether the argument is deprecated, or Click's deprecation message for it."""


class CliCommand(TypedDict, total=False):
    """A command or command group, with its options, arguments and subcommands"""

    name: Required[str]
    """The command's own name; for the root, the entry point's name."""

    full_path: Required[str]
    """The invocation from the root, such as `great-docs build`."""

    help: str
    """The command's help string as written."""

    short_help: str
    """A one-line summary."""

    help_text: str
    """The command's full `--help` output."""

    description: str
    """The help string without its examples block."""

    examples: list[str]
    """The lines of the examples block."""

    deprecated: bool | str
    """Whether the command is deprecated, or Click's deprecation message for it."""

    hidden: bool
    """Whether the command is left out of the reference."""

    is_group: bool
    """Whether the command has subcommands of its own."""

    commands: list[CliCommand]
    """The visible subcommands, in registration order."""

    options: list[CliOption]
    """The command's options."""

    arguments: list[CliArgument]
    """The command's positional arguments."""

    entry_point_name: str
    """The name users type to run the root command; set on the root only."""
