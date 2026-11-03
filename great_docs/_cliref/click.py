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
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .._api_diff import CliCommandInfo, CliOptionInfo
from .._build.steps import USER_CODE_ERRORS
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

    Import `cli_module`, or else the first of the package's `cli`, `__main__`, `main`, `console`
    and `commands` modules that holds a command. In that module, take the attribute `cli_name`
    names, or else the first command among `cli`, `main`, `app`, `command` and the module's own
    name, or else the first public command.

    Parameters
    ----------
    module_name
        The package's importable name.
    package_root
        The directory holding `pyproject.toml`, whose first script names the command.
    cli_module
        The `cli.module` setting: the module that defines the command line.
    cli_name
        The `cli.name` setting: the attribute that holds the command.
    display_name
        The command's name when `pyproject.toml` lists no scripts, typically the project name.
        Defaults to `module_name`.
    report
        Receives a line for the module found or the reason none was.

    Returns
    -------
    :
        The command tree, with `entry_point_name` set on the root, or `None` when the package
        has no command line.
    """
    # Determine the CLI module to import
    cli_module_path = cli_module
    if not cli_module_path:
        # Try common CLI module locations
        common_cli_modules = [
            f"{module_name}.cli",
            f"{module_name}.__main__",
            f"{module_name}.main",
            f"{module_name}.console",
            f"{module_name}.commands",
        ]
        for module_path in common_cli_modules:
            try:
                module = importlib.import_module(module_path)
                # Look for a Click command/group or Typer app in the module
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if is_cli_command(attr):
                        cli_module_path = module_path
                        break
                if cli_module_path:
                    break
            except ImportError:
                continue

    if not cli_module_path:
        report(f"No Click CLI found in {module_name}")
        return None

    try:
        module = importlib.import_module(cli_module_path)
    except ImportError as e:
        report(f"Could not import CLI module {cli_module_path}: {e}")
        return None

    # Find the main Click command/group
    cli_obj = None

    # First, look for explicitly named CLI
    if cli_name:
        cli_obj = getattr(module, cli_name, None)

    # Otherwise, search for Click commands/groups (or Typer apps)
    if not cli_obj:
        for attr_name in ["cli", "main", "app", "command", module_name]:
            attr = getattr(module, attr_name, None)
            if is_cli_command(attr):
                cli_obj = attr
                cli_name = attr_name
                break

    # If still not found, look for any Click command/group or Typer app
    if not cli_obj:
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            attr = getattr(module, attr_name)
            if is_cli_command(attr):
                cli_obj = attr
                cli_name = attr_name
                break

    # Normalize to a Click command so the extraction below can introspect
    # params/subcommands uniformly (Typer apps are converted here).
    cli_obj = to_click_command(cli_obj)

    if not cli_obj:
        report(f"No Click command/group found in {cli_module_path}")
        return None

    report(f"Found Click CLI: {cli_name} in {cli_module_path}")

    # When [project.scripts] is absent, fall back to the display name (the
    # project name) rather than the importable module name, which may differ.
    resolved_name = entry_point_name(package_root) or (display_name or module_name).replace(
        "_", "-"
    )

    cli_info = extract_command(cli_obj, resolved_name)
    cli_info["entry_point_name"] = resolved_name
    return cli_info


def find_command(module_name: str, *, cli_module: str | None, cli_name: str | None) -> Any | None:
    """
    Find a package's command line as a Click command

    Parameters
    ----------
    module_name
        The package's importable name.
    cli_module
        The `cli.module` setting: the module that defines the command line.
    cli_name
        The `cli.name` setting: the attribute that holds the command.

    Returns
    -------
    :
        The Click command, or `None` when the package has no command line.
    """
    cli_module_path = cli_module
    if not cli_module_path:
        for mod in (
            f"{module_name}.cli",
            f"{module_name}.__main__",
            f"{module_name}.main",
        ):
            try:
                m = importlib.import_module(mod)
                if any(is_cli_command(getattr(m, a, None)) for a in dir(m)):
                    cli_module_path = mod
                    break
            except ImportError:
                continue
    if not cli_module_path:
        return None
    try:
        module = importlib.import_module(cli_module_path)
    except ImportError:
        return None

    if cli_name:
        obj = to_click_command(getattr(module, cli_name, None))
        if obj is not None:
            return obj

    for attr_name in ["cli", "main", "app", "command", module_name]:
        obj = to_click_command(getattr(module, attr_name, None))
        if obj is not None:
            return obj

    for attr_name in dir(module):
        if attr_name.startswith("_"):
            continue
        obj = to_click_command(getattr(module, attr_name))
        if obj is not None:
            return obj
    return None


def entry_point_name(package_root: Path) -> str | None:
    """
    Read the name of the package's first script from `pyproject.toml`

    Parameters
    ----------
    package_root
        The directory holding `pyproject.toml`.

    Returns
    -------
    :
        The first `[project.scripts]` name, else the first `[project.gui-scripts]` name, or
        `None` when there is neither or the file is missing or unreadable.
    """
    pyproject_path = package_root / "pyproject.toml"
    if not pyproject_path.exists():
        return None

    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, UnicodeDecodeError, OSError):
        return None

    project = data.get("project", {})
    scripts = project.get("scripts", {})
    if scripts:
        return next(iter(scripts))

    gui_scripts = project.get("gui-scripts", {})
    if gui_scripts:
        return next(iter(gui_scripts))

    return None


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

    return {
        "names": names,
        "name_display": ", ".join(names),
        "help": param.help or "",
        "type": opt_type,
        "default": default,
        "required": param.required,
        "is_flag": param.is_flag,
        "multiple": param.multiple,
        "envvar": param.envvar,
        "show_default": getattr(param, "show_default", False),
        "is_eager": param.is_eager,
        "hidden": getattr(param, "hidden", False),
    }


def extract_argument(param: Any) -> CliArgument:
    """
    Describe a Click argument for the reference pages

    Parameters
    ----------
    param
        The Click argument.

    Returns
    -------
    :
        The argument's description; its type is `None` for text.
    """
    type_name = param.type.name if hasattr(param.type, "name") else str(param.type)

    return {
        "name": param.name,
        "name_display": param.human_readable_name,
        "type": type_name.upper() if type_name != "TEXT" else None,
        "required": param.required,
        "nargs": param.nargs,
    }


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

        module = importlib.import_module(cli_module)

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
