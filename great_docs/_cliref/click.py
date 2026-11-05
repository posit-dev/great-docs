"""
Find a package's Click or Typer command line and describe it

A Typer app is not itself a Click command, but `typer.main.get_command` turns it into one, so
discovery normalises every candidate with `to_click_command` before introspecting it. Typer
vendors its own copy of Click, so introspection is structural rather than `isinstance` checks
against the top-level `click` package.

Two descriptions come out of a command: `extract_command` builds the page model the reference
pages render, and `extract_snapshot` builds the `CliCommandInfo` that API snapshots persist and
`diff_snapshots` compares.
"""

from __future__ import annotations

import importlib
import re
import subprocess
import sys
import tomllib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import ModuleType
from typing import Any, cast

from .. import _manifest
from .._api_diff import CliCommandInfo, CliOptionInfo
from .._build.steps import USER_CODE_ERRORS
from .._manifest import ManifestError
from .._subprocess import TEXT_MODE_KWARGS
from .model import CliArgument, CliCommand, CliOption


def is_typer_app(obj: Any) -> bool:
    """
    Check whether an object is a `typer.Typer` application

    Parameters
    ----------
    obj
        The candidate object.

    Returns
    -------
    :
        `True` for a Typer app; `False` otherwise, including when Typer is not installed.
    """
    try:
        import typer
    except ImportError:
        return False
    return isinstance(obj, typer.Typer)


def to_click_command(obj: Any) -> Any | None:
    """
    Convert a candidate CLI object to a Click command

    Parameters
    ----------
    obj
        A candidate CLI object. A Click `Command` or `Group` is returned unchanged, and a
        `typer.Typer` app is converted with `typer.main.get_command`.

    Returns
    -------
    :
        The Click command, or `None` when the object is neither a Click command nor a Typer app,
        or Typer is not installed.
    """
    import click

    if isinstance(obj, (click.Command, click.Group)):
        return obj

    try:
        import typer
        from typer.main import get_command
    except ImportError:
        return None

    if isinstance(obj, typer.Typer):
        try:
            return get_command(obj)
        except Exception:  # pragma: no cover - defensive (malformed Typer app)
            return None

    return None


def is_cli_command(obj: Any) -> bool:
    """
    Check whether an object is a documentable CLI

    Parameters
    ----------
    obj
        The candidate object.

    Returns
    -------
    :
        `True` for a Click command or a Typer app.
    """
    return to_click_command(obj) is not None


def is_cli_group(cmd: Any) -> bool:
    """
    Check whether a command is a group with named subcommands

    Click's and Typer's groups both expose a dictionary-like `commands` mapping, and leaf
    commands have none.

    Parameters
    ----------
    cmd
        A Click or Typer command.

    Returns
    -------
    :
        `True` for a command group.
    """
    commands = getattr(cmd, "commands", None)
    return commands is not None and hasattr(commands, "items")


def param_kind(param: Any) -> str:
    """
    Classify a Click or Typer parameter

    Parameters
    ----------
    param
        A command parameter. Plain Click and Typer's vendored Click both set its
        `param_type_name`.

    Returns
    -------
    :
        `"option"`, `"argument"`, or `""` for any other parameter.
    """
    return getattr(param, "param_type_name", "") or ""


@dataclass(frozen=True)
class FoundCommand:
    """
    A discovered command and the reference to its defining object
    """

    command: Any
    """The Click command, converted from a Typer app when needed"""

    target: str
    """The `module:attribute` reference to the original Click command or Typer app"""


def discover(
    module_name: str,
    package_root: Path,
    *,
    cli_module: str | None,
    cli_name: str | None,
    display_name: str | None = None,
    report: Callable[[str], None],
) -> CliCommand | None:
    """
    Find a package's command line and describe it for the reference pages

    Parameters
    ----------
    module_name
        The package's importable name.
    package_root
        The directory holding `pyproject.toml`, which supplies the command's script name.
    cli_module
        The `cli.module` setting: the module that defines the command line.
    cli_name
        The `cli.name` setting: the attribute that holds the command.
    display_name
        The command's name when `pyproject.toml` lists no scripts, typically the project name.
        Defaults to `module_name`.
    report
        Receives a line for the command found or the reason none was.

    Returns
    -------
    :
        The command tree of the command `find_command` finds, with `entry_point_name` set on the
        root, or `None` when the package has no command line.
    """
    found = find_command(module_name, cli_module=cli_module, cli_name=cli_name, report=report)
    if found is None:
        return None

    # When [project.scripts] is absent, fall back to the display name (the
    # project name) rather than the importable module name, which may differ.
    resolved_name = entry_point_name(package_root, found.target) or (
        display_name or module_name
    ).replace("_", "-")

    cli_info = extract_command(found.command, resolved_name)
    cli_info["entry_point_name"] = resolved_name
    return cli_info


def find_command(
    module_name: str,
    *,
    cli_module: str | None,
    cli_name: str | None,
    report: Callable[[str], None] = lambda _line: None,
) -> FoundCommand | None:
    """
    Find a package's command line as a Click command

    Import `cli_module`, or else the first of the package's `cli`, `__main__`, `main`, `console`
    and `commands` modules that holds a command. In that module, take the attribute `cli_name`
    names, or else the first command among `cli`, `main`, `app`, `command` and the module's own
    name, or else the first public command. When `cli_name` names an attribute that is not a
    command, the package has no command line.

    Parameters
    ----------
    module_name
        The package's importable name.
    cli_module
        The `cli.module` setting: the module that defines the command line.
    cli_name
        The `cli.name` setting: the attribute that holds the command.
    report
        Receives a line for the command found or the reason none was.

    Returns
    -------
    :
        The discovered command and its original `module:attribute` reference, or `None` when
        the package has no command line. Typer apps are converted to Click commands.

    Raises
    ------
    ImportError
        When a candidate module exists but fails to import, for example because a dependency
        is missing. The message names the module.
    """
    cli_module_path = cli_module
    if not cli_module_path:
        for candidate in ("cli", "__main__", "main", "console", "commands"):
            module_path = f"{module_name}.{candidate}"
            module = _import_candidate(module_path)
            if module is not None and any(
                is_cli_command(getattr(module, attr_name)) for attr_name in dir(module)
            ):
                cli_module_path = module_path
                break

    if not cli_module_path:
        report(f"No Click CLI found in {module_name}")
        return None

    try:
        module = _import_cli_module(cli_module_path)
    except ImportError as e:
        report(f"Could not import CLI module {cli_module_path}: {e}")
        return None

    cli_obj = None
    if cli_name:
        cli_obj = getattr(module, cli_name, None)

    if not cli_obj:
        for attr_name in ["cli", "main", "app", "command", module_name]:
            attr = getattr(module, attr_name, None)
            if is_cli_command(attr):
                cli_obj = attr
                cli_name = attr_name
                break

    if not cli_obj:
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            attr = getattr(module, attr_name)
            if is_cli_command(attr):
                cli_obj = attr
                cli_name = attr_name
                break

    cli_obj = to_click_command(cli_obj)
    if not cli_obj:
        report(f"No Click command/group found in {cli_module_path}")
        return None

    report(f"Found Click CLI: {cli_name} in {cli_module_path}")
    return FoundCommand(cli_obj, f"{cli_module_path}:{cli_name}")


def _import_candidate(module_path: str) -> ModuleType | None:
    """
    Import a candidate module for the package's command line

    Parameters
    ----------
    module_path
        The module's dotted path.

    Returns
    -------
    :
        The imported module, or `None` if the module or a parent package is missing, or the
        import raises `SystemExit`. An unguarded command call in `__main__` runs on import
        and causes Click to exit.

    Raises
    ------
    ImportError
        When the module exists but fails to import, for example because a dependency is
        missing. The message names the module, and the original error is the cause.
    """
    try:
        return importlib.import_module(module_path)
    except SystemExit:
        return None
    except USER_CODE_ERRORS as error:
        # A missing candidate or parent package means there is no CLI at this location.
        # A missing dependency also raises `ModuleNotFoundError`, but names the dependency.
        missing = error.name if isinstance(error, ModuleNotFoundError) else None
        if missing and (module_path == missing or module_path.startswith(f"{missing}.")):
            return None
        raise ImportError(
            f"importing {module_path} failed: {type(error).__name__}: {error}"
        ) from error


def _import_cli_module(module_path: str) -> ModuleType:
    """
    Import a module that may define a package's command line

    Parameters
    ----------
    module_path
        The module's dotted path.

    Returns
    -------
    :
        The imported module.

    Raises
    ------
    ImportError
        When the module cannot be imported, or when importing it exits. A `__main__` module that
        calls its command without an `if __name__ == "__main__":` guard runs the command on
        import, and Click then exits.
    """
    try:
        return importlib.import_module(module_path)
    except SystemExit as e:
        raise ImportError(f"importing {module_path} exited with status {e.code}") from e


def entry_point_name(package_root: Path, target: str) -> str | None:
    """
    Read a command's script name from `pyproject.toml`

    Parameters
    ----------
    package_root
        The directory holding `pyproject.toml`.
    target
        The `module:attribute` reference to the original Click command or Typer app.

    Returns
    -------
    :
        The first script name whose entry point matches `target`, searching `[project.scripts]`
        before `[project.gui-scripts]`. If none matches, the first name in `[project.scripts]`,
        or in `[project.gui-scripts]` if there are no console scripts. `None` when neither
        table lists scripts or a packaging file cannot be read or parsed.
    """
    try:
        scripts = _manifest.read(package_root)["scripts"]
    except ManifestError:
        return None

    for name, reference in scripts.items():
        # Whitespace and optional extras do not change the command an entry point names.
        if re.sub(r"\s", "", reference.split("[", 1)[0]) == target:
            return name

    return next(iter(scripts), None)


def extract_command(cmd: Any, name: str, parent_path: str = "") -> CliCommand:
    """
    Describe a Click command and its visible subcommands for the reference pages

    API snapshots record commands with `extract_snapshot` instead, in the format that
    `diff_snapshots` compares across releases.

    Parameters
    ----------
    cmd
        The Click command or group.
    name
        The command's name.
    parent_path
        The invocation of the parent command, empty for the root.

    Returns
    -------
    :
        The command tree, with options, arguments, `--help` output, and the help string split
        into description and examples.
    """
    full_path = f"{parent_path} {name}".strip() if parent_path else name

    options: list[CliOption] = []
    arguments: list[CliArgument] = []
    for param in cmd.params:
        kind = param_kind(param)
        if kind == "option":
            opt_info = extract_option(param)
            if opt_info:
                options.append(opt_info)
        elif kind == "argument":
            arguments.append(extract_argument(param))

    description, examples = parse_help_parts(cmd.help or "")

    # Click leaves `short_help` empty for some subcommands; derive it from the help string.
    short_help = getattr(cmd, "short_help", "") or ""
    if not short_help and cmd.help:
        short_help = cmd.get_short_help_str(limit=150)

    info: CliCommand = {
        "name": name,
        "full_path": full_path,
        "help": cmd.help or "",
        "short_help": short_help,
        "help_text": help_output(cmd, full_path),
        "deprecated": getattr(cmd, "deprecated", False),
        "hidden": getattr(cmd, "hidden", False),
        "commands": [],
        "is_group": is_cli_group(cmd),
        "options": options,
        "arguments": arguments,
        "description": description,
        "examples": examples,
    }

    if is_cli_group(cmd):
        for subcmd_name, subcmd in cmd.commands.items():
            if not getattr(subcmd, "hidden", False):
                info["commands"].append(extract_command(subcmd, subcmd_name, full_path))

    return info


def extract_option(param: Any) -> CliOption | None:
    """
    Describe a Click option for the reference pages

    Parameters
    ----------
    param
        The Click option.

    Returns
    -------
    :
        The option's description, or `None` for an option named `help`.
    """
    if param.name == "help":
        return None

    decls = param.opts + param.secondary_opts
    names = sorted(decls, key=len)  # short first, long second

    type_name = param.type.name if hasattr(param.type, "name") else str(param.type)

    # Click marks an unset default with a sentinel object.
    default = param.default
    if default is None or (
        type(default).__name__ in ("Sentinel", "_DEFAULT_SENTINEL")
        or repr(default).startswith("Sentinel")
    ):
        default = None

    # Plain Click names a flag's type "BOOL" and Typer's vendored Click names it "boolean", so
    # suppress the type for every flag rather than match the name.
    opt_type = None if param.is_flag or type_name.upper() == "BOOL" else type_name.upper()

    help_str = param.help or ""
    deprecated = getattr(param, "deprecated", False)
    if deprecated:
        # The page adds its own deprecation notice, so omit Click's appended notice.
        notice = f"(DEPRECATED: {deprecated})" if isinstance(deprecated, str) else "(DEPRECATED)"
        help_str = help_str.removesuffix(notice).rstrip()

    info: CliOption = {
        "names": names,
        "name_display": ", ".join(names),
        "help": help_str,
        "type": opt_type,
        "default": default,
        "required": param.required,
        "is_flag": param.is_flag,
        "multiple": param.multiple,
        "envvar": param.envvar,
        "show_default": getattr(param, "show_default", False),
        "is_eager": param.is_eager,
        "hidden": getattr(param, "hidden", False),
        "deprecated": deprecated,
    }
    choices = extract_choices(param)
    if choices is not None:
        info["choices"] = choices
    return info


def extract_argument(param: Any) -> CliArgument:
    """
    Describe a Click argument for the reference pages

    Parameters
    ----------
    param
        The Click argument or converted Typer argument.

    Returns
    -------
    :
        The argument's description, including non-empty help text when available.
        Its type is `None` for text.
    """
    type_name = param.type.name if hasattr(param.type, "name") else str(param.type)

    info: CliArgument = {
        "name": param.name,
        "name_display": param.human_readable_name,
        "type": type_name.upper() if type_name != "TEXT" else None,
        "required": param.required,
        "nargs": param.nargs,
        "deprecated": getattr(param, "deprecated", False),
    }
    # Typer arguments can declare help text; plain Click arguments have no `help` attribute.
    if help_text := getattr(param, "help", None):
        info["help"] = help_text
    choices = extract_choices(param)
    if choices is not None:
        info["choices"] = choices
    return info


def extract_choices(param: Any) -> list[str] | None:
    """
    Extract accepted command-line values from a Click `Choice`

    Parameters
    ----------
    param
        The Click option or argument.

    Returns
    -------
    :
        The accepted values in declaration order, with `Enum` members represented by their
        names. `None` if the parameter's type does not declare choices.
    """
    # Typer vendors Click, so recognise choices without relying on class identity.
    choices = getattr(param.type, "choices", None)
    if not isinstance(choices, (list, tuple)):
        return None
    return [c.name if isinstance(c, Enum) else str(c) for c in cast(Sequence[object], choices)]


def parse_help_parts(help_text: str) -> tuple[str, list[str]]:
    """
    Split a Click help string into its description and its examples

    Parameters
    ----------
    help_text
        The command's help string as written.

    Returns
    -------
    :
        The prose before an `Examples:` line, with Click's no-rewrap markers removed, and the
        lines after it, without the header or their Click indentation.
    """
    if not help_text:
        return "", []

    lines = help_text.split("\n")
    desc_lines: list[str] = []
    example_lines: list[str] = []
    in_examples = False

    for line in lines:
        stripped = line.strip()

        # Click marks a paragraph it must not rewrap with a line holding only `\b`.
        if stripped in ("\x08", "\\b"):
            continue

        if stripped.lower() == "examples:" and not in_examples:
            in_examples = True
            continue

        if in_examples:
            # Strip common Click indentation (2 or 4 spaces)
            dedented = line
            if line.startswith("    "):
                dedented = line[4:]
            elif line.startswith("  "):
                dedented = line[2:]
            example_lines.append(dedented)
        else:
            desc_lines.append(line)

    description = "\n".join(desc_lines).strip()
    description = description.replace("\x08", "")
    description = description.replace("\\b", "")
    description = re.sub(r"\n{3,}", "\n\n", description)

    while example_lines and not example_lines[-1].strip():
        _ = example_lines.pop()

    return description, example_lines


def help_output(cmd: Any, full_path: str) -> str:
    """
    Render a Click command's `--help` output

    Parameters
    ----------
    cmd
        The Click command.
    full_path
        The invocation shown in the usage line, such as `great-docs build`.

    Returns
    -------
    :
        The help text as `--help` prints it.
    """
    # Build the context from the command's own `context_class` so the help is rendered by the
    # Click the command belongs to, which for Typer is its vendored copy.
    ctx = cmd.context_class(cmd, info_name=full_path)
    return cmd.get_help(ctx)


def read_module_at_tag(project_root: Path, tag: str, package_name: str) -> str | None:
    """
    Find the CLI module a release documented

    Parameters
    ----------
    project_root
        The root of the git repository.
    tag
        The release's git tag.
    package_name
        The package's name.

    Returns
    -------
    :
        `cli.module` from `pyproject.toml` or `great-docs.yml` at the tag when the CLI reference
        is enabled there, else the package's `cli` or `__main__` module if the tag has one, else
        `None`.
    """
    normalized = package_name.replace("-", "_")

    for cfg_file in ("pyproject.toml", "great-docs.yml"):
        try:
            result = subprocess.run(
                ["git", "show", f"{tag}:{cfg_file}"],
                cwd=project_root,
                capture_output=True,
                **TEXT_MODE_KWARGS,
                timeout=10,
            )
            if result.returncode != 0:
                continue
            content = result.stdout

            if cfg_file == "pyproject.toml":
                data = tomllib.loads(content)
                cli_cfg = data.get("tool", {}).get("great-docs", {}).get("cli", {})
                if cli_cfg.get("enabled"):
                    return cli_cfg.get("module")
            else:
                try:
                    from yaml12 import parse_yaml

                    yaml_data: Any = parse_yaml(content) or {}
                    cli_cfg = yaml_data.get("cli", {})
                    if cli_cfg.get("enabled"):
                        return cli_cfg.get("module")
                except (ValueError, AttributeError):
                    pass
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            continue

    # Fallback: check if common CLI module exists at this tag
    for suffix in ("cli", "__main__"):
        mod_path = f"{normalized}/{suffix}.py"
        try:
            check = subprocess.run(
                ["git", "cat-file", "-t", f"{tag}:{mod_path}"],
                cwd=project_root,
                capture_output=True,
                **TEXT_MODE_KWARGS,
                timeout=5,
            )
            if check.returncode == 0:
                return f"{normalized}.{suffix}"
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            continue
    return None


def snapshot_from_source(source_dir: Path, cli_module: str) -> CliCommandInfo | None:
    """
    Import a command line from an extracted source tree and record its snapshot

    `sys.path` and `sys.modules` are restored afterwards, so the installed package stays the one
    later imports find.

    Parameters
    ----------
    source_dir
        The directory holding the extracted package.
    cli_module
        The module that defines the command line.

    Returns
    -------
    :
        The snapshot, or `None` when the module cannot be imported or holds no command.
    """
    str_dir = str(source_dir)
    sys.path.insert(0, str_dir)
    try:
        # Invalidate cached modules that might shadow the extracted source
        parts = cli_module.split(".")
        for i in range(len(parts)):
            prefix = ".".join(parts[: i + 1])
            _ = sys.modules.pop(prefix, None)

        module = _import_cli_module(cli_module)

        cli_obj = None
        for attr_name in ["cli", "main", "app", "command"]:
            obj = to_click_command(getattr(module, attr_name, None))
            if obj is not None:
                cli_obj = obj
                break

        if cli_obj is None:
            for attr_name in dir(module):
                if attr_name.startswith("_"):
                    continue
                obj = to_click_command(getattr(module, attr_name))
                if obj is not None:
                    cli_obj = obj
                    break

        if cli_obj is None:
            return None

        return extract_snapshot(cli_obj)
    except USER_CODE_ERRORS:
        return None
    finally:
        if str_dir in sys.path:
            sys.path.remove(str_dir)
        for key in list(sys.modules):
            if key == cli_module or key.startswith(cli_module + "."):
                _ = sys.modules.pop(key, None)


def extract_snapshot(cli_obj: object) -> CliCommandInfo | None:
    """
    Record a command line in the format that API snapshots persist

    The reference pages describe commands with `extract_command` instead. The snapshot keeps its
    own format so that `diff_snapshots` can compare it with snapshots saved by earlier releases.

    Parameters
    ----------
    cli_obj
        A Click command or group, or a Typer app.

    Returns
    -------
    :
        The command tree, or `None` when the object is neither a Click command nor a Typer app.
    """
    cmd = to_click_command(cli_obj)
    if cmd is None:
        return None

    return _snapshot_command(cmd)


def _snapshot_command(cmd: Any) -> CliCommandInfo:
    """
    Record a Click command and its visible subcommands for an API snapshot

    Parameters
    ----------
    cmd
        The Click command or group.

    Returns
    -------
    :
        The command tree; arguments are recorded as options of type `"argument"`.
    """
    name = getattr(cmd, "name", "") or ""
    help_str = getattr(cmd, "help", "") or ""
    hidden = getattr(cmd, "hidden", False)
    deprecated = getattr(cmd, "deprecated", False)
    is_group = is_cli_group(cmd)

    options: list[CliOptionInfo] = []
    for param in getattr(cmd, "params", []):
        kind = param_kind(param)
        if kind == "option":
            # Use the longest option name (e.g. --verbose over -v)
            opt_name = max(param.opts, key=len) if param.opts else param.name or ""
            options.append(
                CliOptionInfo(
                    name=opt_name,
                    type="option",
                    is_flag=param.is_flag,
                    required=param.required,
                    default=str(param.default) if param.default is not None else None,
                    help=param.help,
                )
            )
        elif kind == "argument":
            options.append(
                CliOptionInfo(
                    name=param.name or "",
                    type="argument",
                    required=param.required,
                )
            )

    subcommands: list[CliCommandInfo] = []
    if is_group:
        for subcmd in getattr(cmd, "commands", {}).values():
            if not getattr(subcmd, "hidden", False):
                subcommands.append(_snapshot_command(subcmd))

    return CliCommandInfo(
        name=name,
        help=help_str,
        options=options,
        subcommands=subcommands,
        is_group=is_group,
        hidden=hidden,
        deprecated=deprecated,
    )
