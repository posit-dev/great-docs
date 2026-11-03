"""
Rust CLI project detection and command extraction

Projects using clap, structopt, argh or custom command parsers expose their command structure
through `--help`. Extraction follows the same approach as Go CLI extraction and produces the
shared page model, so the same renderer can write pages for both.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RustCliProject:
    """Metadata about a detected Rust CLI project."""

    project_root: Path
    package_name: str  # from [package].name in Cargo.toml
    binary_names: list[str] = field(default_factory=list)  # [[bin]] names, or inferred
    uses_clap: bool = False  # True when clap appears in [dependencies]


def detect_rust_cli_project(project_root: Path) -> RustCliProject | None:
    """Detect whether *project_root* is a documentable Rust CLI project.

    A project is considered documentable when it has a ``Cargo.toml`` at the root with a
    ``[package]`` section and at least one binary target (explicit ``[[bin]]`` or ``src/main.rs``).

    Parameters
    ----------
    project_root
        Directory to inspect.

    Returns
    -------
    RustCliProject | None
        Detected project info, or ``None`` if the directory is not a Rust CLI project.
    """
    cargo_toml = project_root / "Cargo.toml"
    if not cargo_toml.exists():
        return None

    cargo_text = _read_cargo_toml(cargo_toml)
    if cargo_text is None:
        return None

    package_name = _parse_package_name(cargo_text)
    if not package_name:
        return None

    binary_names = _find_binary_targets(project_root, cargo_text, package_name)
    if not binary_names:
        return None

    return RustCliProject(
        project_root=project_root,
        package_name=package_name,
        binary_names=binary_names,
        uses_clap=_uses_clap(cargo_text),
    )


# ---------------------------------------------------------------------------
# Internal helpers – file-system / static analysis
# ---------------------------------------------------------------------------


def _read_cargo_toml(cargo_toml: Path) -> str | None:
    """Read the Cargo.toml contents, returning ``None`` on failure."""
    try:
        return cargo_toml.read_text(encoding="utf-8")
    except OSError:
        return None


def _parse_package_name(cargo_text: str) -> str | None:
    """Extract the package name from Cargo.toml text.

    Looks for ``name = "..."`` under a ``[package]`` header. This is a lightweight regex-based
    parser that avoids requiring a TOML library.
    """
    in_package = False
    for line in cargo_text.splitlines():
        stripped = line.strip()
        if stripped == "[package]":
            in_package = True
            continue
        if in_package:
            if stripped.startswith("["):
                break
            m = re.match(r'^name\s*=\s*"([^"]+)"', stripped)
            if m:
                return m.group(1)
    return None


def _find_binary_targets(
    project_root: Path,
    cargo_text: str,
    package_name: str,
) -> list[str]:
    """Determine binary target names.

    Search order:

    1. Explicit ``[[bin]]`` sections with ``name = "..."``
    2. ``src/main.rs`` exists → binary name is the package name (Cargo default)

    Parameters
    ----------
    project_root
        Root of the Rust project.
    cargo_text
        Contents of Cargo.toml.
    package_name
        The [package].name value (used as fallback binary name).

    Returns
    -------
    list[str]
        Binary names. Empty if no binary targets are found.
    """
    # Explicit [[bin]] entries
    bin_names: list[str] = []
    in_bin = False
    for line in cargo_text.splitlines():
        stripped = line.strip()
        if stripped == "[[bin]]":
            in_bin = True
            continue
        if in_bin:
            if stripped.startswith("["):
                in_bin = False
                continue
            m = re.match(r'^name\s*=\s*"([^"]+)"', stripped)
            if m:
                bin_names.append(m.group(1))
                in_bin = False

    if bin_names:
        return bin_names

    # Default: src/main.rs implies a single binary with the package name
    if (project_root / "src" / "main.rs").exists():
        return [package_name]

    return []


def _uses_clap(cargo_text: str) -> bool:
    """Return ``True`` when Cargo.toml lists ``clap`` as a dependency."""
    return bool(re.search(r"^\s*clap\s*=", cargo_text, re.MULTILINE))


# ---------------------------------------------------------------------------
# Binary build + CLI introspection
# ---------------------------------------------------------------------------


def build_rust_binary(
    rust_project: RustCliProject,
    binary_name: str | None = None,
    output_dir: Path | None = None,
) -> Path | None:
    """Compile a Rust CLI binary via ``cargo build``.

    Requires ``cargo`` to be on ``PATH``.

    Parameters
    ----------
    rust_project
        The detected Rust CLI project.
    binary_name
        Which binary to build when the project produces multiple. Defaults to the first.
    output_dir
        Directory for the output binary. Defaults to a fresh tempdir so the project tree is
        never modified.

    Returns
    -------
    Path | None
        Path to the compiled binary, or ``None`` if the build failed.
    """
    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(prefix="great-docs-rust-"))

    bin_name = binary_name or rust_project.binary_names[0]

    try:
        result = subprocess.run(
            [
                "cargo",
                "build",
                "--release",
                "--bin",
                bin_name,
                "--target-dir",
                str(output_dir / "_cargo_target"),
            ],
            cwd=str(rust_project.project_root),
            capture_output=True,
            text=True,
            timeout=300,
        )
    except FileNotFoundError:
        print("'cargo' not found on PATH; cannot build Rust binary")
        return None
    except subprocess.TimeoutExpired:
        print("cargo build timed out")
        return None

    if result.returncode != 0:
        print(f"cargo build failed:\n{result.stderr}")
        return None

    # cargo puts the binary under target-dir/release/<name>
    binary_path = output_dir / "_cargo_target" / "release" / bin_name
    if not binary_path.exists():
        print(f"Expected binary not found at {binary_path}")
        return None

    return binary_path


def introspect_rust_cli(rust_project: RustCliProject) -> dict | None:
    """
    Build and run a Rust CLI to extract its command structure

    The command tree uses the shared CLI page model, so the same renderer can write pages
    for Click, Go and Rust commands.

    For projects with multiple binaries, the first binary is documented.

    Parameters
    ----------
    rust_project
        The detected Rust CLI project.

    Returns
    -------
    :
        CLI structure, or `None` if the binary could not be built or run.
    """
    bin_name = rust_project.binary_names[0]
    binary_path = build_rust_binary(rust_project, bin_name)
    if not binary_path:
        return None

    cli_info = _extract_clap_commands(binary_path, bin_name)
    if cli_info:
        cli_info["entry_point_name"] = bin_name
    return cli_info


# ---------------------------------------------------------------------------
# Help-text parsing (clap-flavoured)
# ---------------------------------------------------------------------------

# Clap section headers: "Usage:", "Commands:", "Options:", "Arguments:", etc.
# Clap uses "Commands:" (not "Available Commands:" like Cobra), and "Options:" (not "Flags:").
# Some clap CLIs also use custom section names.
_SECTION_HEADER_RE = re.compile(r"^([A-Z][A-Za-z ]+):\s*$")

# Inline usage header: "Usage: cmd [OPTIONS] ..." — clap puts usage on the same line.
_INLINE_USAGE_RE = re.compile(r"^Usage:\s+(.+)$")

_COMMAND_LINE_RE = re.compile(r"^\s{1,8}(\S+)\s{2,}(.*)$")

# Clap-builtin commands that are not worth documenting
_CLAP_BUILTIN_COMMANDS = frozenset({"help"})

# Clap flag pattern. Examples:
#   -h, --help               Print help
#   -V, --version            Print version
#   -n, --name <NAME>        Name to greet [default: World]
#       --config <PATH>      Config file path
#   -v, --verbose...         Enable verbose output
#       --check              (no description)
_CLAP_FLAG_RE = re.compile(
    r"^\s*"
    r"(?:(-\w),\s*)?"  # optional short flag
    r"(--[\w-]+)"  # long flag (required)
    r"(\.{3})?"  # optional "..." for repeatable flags
    r"(?:\s+<([^>]+)>)?"  # optional <VALUE_NAME>
    r"(?:\s{2,}(.*)|$)"  # separator + description, OR end of line (no description)
)

# Clap default value pattern: [default: value]
_CLAP_DEFAULT_RE = re.compile(r"\[default:\s*([^\]]+)\]\s*$")

# Clap possible values pattern: [possible values: a, b, c]
_CLAP_POSSIBLE_VALUES_RE = re.compile(r"\[possible values:\s*([^\]]+)\]")


def _parse_clap_flag(raw: str) -> dict | None:
    """Parse a single clap flag line into a dict compatible with Click's option format.

    Parameters
    ----------
    raw
        A single flag line from ``--help`` output.

    Returns
    -------
    dict | None
        Option dict, or ``None`` if the line could not be parsed.
    """
    m = _CLAP_FLAG_RE.match(raw)
    if not m:
        return None

    short, long_name, dots, value_name, description = (
        m.group(1),
        m.group(2),
        m.group(3),
        m.group(4),
        m.group(5) or "",
    )

    is_flag = value_name is None
    flag_type = value_name.lower() if value_name else None

    # Extract default value
    default: str | None = None
    dm = _CLAP_DEFAULT_RE.search(description)
    if dm:
        default = dm.group(1).strip()
        description = description[: dm.start()].strip()

    # Strip possible-values annotation from description (keep it for type info)
    pv = _CLAP_POSSIBLE_VALUES_RE.search(description)
    if pv:
        description = description[: pv.start()].strip()

    names = [long_name]
    if short:
        names.insert(0, short)
    name_display = ", ".join(names)
    if value_name:
        name_display += f" <{value_name}>"
    if dots:
        name_display = name_display.replace(long_name, long_name + "...")

    return {
        "names": names,
        "name_display": name_display,
        "type": flag_type,
        "help": description.strip(),
        "default": default,
        "is_flag": is_flag,
        "required": False,
        "hidden": False,
    }


def _short_help(description: str, limit: int = 150) -> str:
    """Condense a full command description into a one-line summary.

    Mirrors `go._short_help` for consistency.
    """
    description = description.strip()
    if not description:
        return ""

    first_sentence = description.split(". ", 1)[0].rstrip(".")
    if len(first_sentence) <= limit:
        return first_sentence

    if (
        len(description) <= limit
    ):  # pragma: no cover — first_sentence ≤ desc, so first_sentence>limit implies desc>limit
        return description

    truncated = description[:limit].rsplit(" ", 1)[0].rstrip()
    return f"{truncated}..."


def _extract_clap_commands(
    binary_path: Path,
    name: str,
    parent_args: list[str] | None = None,
    display_path: str | None = None,
) -> dict | None:
    """Recursively extract the command tree from a clap-based CLI binary.

    Calls ``binary [subcommand...] --help`` and parses the output.

    Parameters
    ----------
    binary_path
        Path to the compiled binary.
    name
        Display name for this command node.
    parent_args
        Invocation tokens appended after the binary name to reach this subcommand.
    display_path
        Full display path for this node, e.g. ``"yamark git-filter"``.

    Returns
    -------
    dict | None
        Parsed command structure, or ``None`` on timeout/error.
    """
    args_list = parent_args or []
    node_display = display_path or name
    cmd_args = [str(binary_path)] + args_list + ["--help"]

    try:
        result = subprocess.run(
            cmd_args,
            capture_output=True,
            text=True,
            timeout=10,
        )
        # clap writes --help to stdout; fall back to stderr
        help_text = result.stdout or result.stderr
    except (subprocess.TimeoutExpired, OSError):
        return None

    return _parse_clap_help(help_text, name, binary_path, args_list, node_display)


def _parse_clap_help(
    help_text: str,
    name: str,
    binary_path: Path,
    parent_args: list[str],
    display_path: str | None = None,
) -> dict:
    """Parse the output of ``<binary> [subcommand...] --help``.

    clap's help format is::

        Description text

        Usage: binary [OPTIONS] [COMMAND]

        Commands:
          sub-a  Short description
          sub-b  Short description

        Options:
          -h, --help     Print help
          -V, --version  Print version
    """
    lines = help_text.splitlines()

    # Description: non-empty lines before the first section header or inline Usage:
    desc_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if _SECTION_HEADER_RE.match(stripped) or _INLINE_USAGE_RE.match(stripped):
            break
        if stripped:
            desc_lines.append(stripped)
    description = " ".join(desc_lines)

    # Sections that contain flag/option definitions
    _OPTION_SECTIONS = frozenset({"Options", "Global Options", "Flags", "Global Flags"})
    # Sections that contain positional argument definitions
    _ARGUMENT_SECTIONS = frozenset({"Arguments"})
    # Sections that never contain subcommand entries
    _NON_COMMAND_SECTIONS = frozenset({"Usage", "Examples", "Aliases"})

    subcommand_names: list[tuple[str, str]] = []
    options: list[dict] = []
    arguments: list[dict] = []
    current_section = ""

    for line in lines:
        stripped = line.strip()

        header_m = _SECTION_HEADER_RE.match(stripped)
        if header_m:
            current_section = header_m.group(1)
            continue

        # Also handle "Usage: ..." inline header
        if _INLINE_USAGE_RE.match(stripped):
            current_section = "Usage"
            continue

        if not stripped:
            continue

        if current_section in _OPTION_SECTIONS:
            if stripped.startswith("-"):
                parsed = _parse_clap_flag(stripped)
                if parsed:
                    options.append(parsed)

        elif current_section in _ARGUMENT_SECTIONS:
            # clap prints positional args as:
            #   <REQUIRED>     Description
            #   [OPTIONAL]...  Description
            #   [OPTIONAL]     (no description)
            m = re.match(
                r"^\s*(?:<([^>]+)>|\[([^\]]+)\])(\.{3})?"
                r"(?:\s{2,}(.*)|$)",
                line,
            )
            if m:
                arg_name = m.group(1) or m.group(2)
                is_required = m.group(1) is not None
                arg_help = (m.group(4) or "").strip()
                arguments.append(
                    {
                        "name": arg_name,
                        "help": arg_help,
                        "required": is_required,
                        "default": None,
                    }
                )

        elif (
            current_section not in _OPTION_SECTIONS
            and current_section not in _NON_COMMAND_SECTIONS
            and current_section not in _ARGUMENT_SECTIONS
            and current_section
        ):
            m = _COMMAND_LINE_RE.match(line)
            if m:
                cmd_name = m.group(1)
                cmd_desc = m.group(2).strip()
                if cmd_name not in _CLAP_BUILTIN_COMMANDS:
                    subcommand_names.append((cmd_name, cmd_desc))

    node_full_path = display_path or name

    # Recursively introspect subcommands
    commands: list[dict] = []
    for cmd_name, cmd_short in subcommand_names:
        sub_args = parent_args + [cmd_name]
        sub_display = f"{node_full_path} {cmd_name}"
        sub_info = _extract_clap_commands(binary_path, cmd_name, sub_args, sub_display)
        commands.append(
            sub_info
            if sub_info is not None
            else {
                "name": cmd_name,
                "full_path": sub_display,
                "help": cmd_short,
                "short_help": cmd_short,
                "help_text": "",
                "description": cmd_short,
                "examples": "",
                "commands": [],
                "options": [],
                "arguments": [],
                "is_group": False,
                "deprecated": False,
                "hidden": False,
            }
        )

    return {
        "name": name,
        "full_path": node_full_path,
        "help": description,
        "short_help": _short_help(description),
        "help_text": help_text,
        "description": description,
        "examples": "",
        "commands": commands,
        "options": options,
        "arguments": arguments,
        "is_group": bool(subcommand_names),
        "deprecated": False,
        "hidden": False,
    }
