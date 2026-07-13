"""Go CLI project detection and introspection.

Handles detection of Go-based CLI projects (cobra/urfave) and extraction of their command structure
via the `--help` interface. Entirely decoupled from the Python-package detection code in `core.py`.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GoCliProject:
    """Metadata about a detected Go CLI project."""

    project_root: Path
    module_path: str  # e.g. "github.com/jeroenjanssens/velocirepo"
    binary_name: str  # e.g. "velocirepo"
    main_package: str  # relative Go import path, e.g. "./cmd/velocirepo"
    uses_cobra: bool  # True when spf13/cobra is in go.mod


def detect_go_cli_project(project_root: Path) -> GoCliProject | None:
    """Detect whether *project_root* is a documentable Go CLI project.

    A project is considered documentable when it has a `go.mod` at the root and at least one *main*
    package (i.e. a `main.go` entry-point). The check is purely file-system based and never invokes
    the compiler.

    Parameters
    ----------
    project_root
        Directory to inspect.

    Returns
    -------
    GoCliProject | None
        Detected project info, or `None` if the directory is not a Go CLI project.
    """
    go_mod = project_root / "go.mod"
    if not go_mod.exists():
        return None

    module_path = _parse_go_module_path(go_mod)
    if not module_path:
        return None

    main_package, binary_name = _find_go_main_package(project_root, module_path)
    if not main_package:
        return None

    return GoCliProject(
        project_root=project_root,
        module_path=module_path,
        binary_name=binary_name,
        main_package=main_package,
        uses_cobra=_uses_cobra(go_mod),
    )


# ---------------------------------------------------------------------------
# Internal helpers – file-system / static analysis
# ---------------------------------------------------------------------------


def _parse_go_module_path(go_mod: Path) -> str | None:
    """Return the module path declared in *go_mod*, e.g. `"github.com/user/repo"`."""
    try:
        for line in go_mod.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^module\s+(\S+)", line)
            if m:
                return m.group(1)
    except OSError:
        pass
    return None


def _find_go_main_package(
    project_root: Path,
    module_path: str,
) -> tuple[str, str]:
    """Locate the main package and infer the binary name.

    Search order (standard Go project layouts):

    1. `cmd/<name>/main.go`: multi-binary layout (most common for CLIs)
    2. `cmd/main.go`: single binary under `cmd/`
    3. `main.go`: flat layout

    Parameters
    ----------
    project_root
        Root of the Go project.
    module_path
        Declared module path (used to derive the fallback binary name).

    Returns
    -------
    tuple[str, str]
        `(relative_import_path, binary_name)`, e.g. `("./cmd/velocirepo", "velocirepo")`. Returns
        `("", "")` when no main package is found.
    """
    default_binary = module_path.rsplit("/", 1)[-1]

    cmd_dir = project_root / "cmd"
    if cmd_dir.is_dir():
        # Pattern 1: cmd/<name>/main.go
        for subdir in sorted(cmd_dir.iterdir()):
            if subdir.is_dir() and (subdir / "main.go").exists():
                return f"./cmd/{subdir.name}", subdir.name
        # Pattern 2: cmd/main.go
        if (cmd_dir / "main.go").exists():
            return "./cmd", default_binary

    # Pattern 3: flat main.go
    if (project_root / "main.go").exists():
        return ".", default_binary

    return "", ""


def _uses_cobra(go_mod: Path) -> bool:
    """Return `True` when `go.mod` lists `github.com/spf13/cobra`."""
    try:
        return "github.com/spf13/cobra" in go_mod.read_text(encoding="utf-8")
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Binary build + CLI introspection
# ---------------------------------------------------------------------------


def build_go_binary(
    go_project: GoCliProject,
    output_dir: Path | None = None,
) -> Path | None:
    """Compile the Go CLI to a binary.

    Requires `go` to be on `PATH`.

    Parameters
    ----------
    go_project
        The detected Go CLI project.
    output_dir
        Directory for the output binary. Defaults to a fresh `tempfile` directory so the project
        tree is never modified.

    Returns
    -------
    Path | None
        Path to the compiled binary, or `None` if the build failed.
    """
    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(prefix="great-docs-go-"))

    binary_path = output_dir / go_project.binary_name
    try:
        result = subprocess.run(
            ["go", "build", "-o", str(binary_path), go_project.main_package],
            cwd=str(go_project.project_root),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        print("'go' not found on PATH; cannot build Go binary")
        return None
    except subprocess.TimeoutExpired:
        print("go build timed out")
        return None

    if result.returncode != 0:
        print(f"go build failed:\n{result.stderr}")
        return None

    return binary_path


def introspect_cobra_cli(go_project: GoCliProject) -> dict | None:
    """Build and run a Cobra CLI to extract its command structure.

    The returned dict mirrors the shape that `_discover_click_cli` produces in `core.py`, making it
    straightforward to reuse the existing page-generation helpers.

    Parameters
    ----------
    go_project
        The detected Go CLI project.

    Returns
    -------
    dict | None
        CLI structure, or `None` if the binary could not be built or run.
    """
    binary_path = build_go_binary(go_project)
    if not binary_path:
        return None

    cli_info = _extract_cobra_commands(binary_path, go_project.binary_name)
    if cli_info:
        cli_info["entry_point_name"] = go_project.binary_name
    return cli_info


# ---------------------------------------------------------------------------
# Help-text parsing
# ---------------------------------------------------------------------------

_SECTION_HEADER_RE = re.compile(r"^[A-Z][A-Za-z ]+:$")
_COMMAND_LINE_RE = re.compile(r"^\s{1,8}(\S+)\s{2,}(.*)$")

# Built-in cobra meta-commands that are not worth documenting
_COBRA_BUILTIN_COMMANDS = frozenset({"completion", "help"})

# Go type tokens that appear between the flag name and its description.
# cobra prints e.g. "--flag string   description" or "--flag int   description".
_GO_FLAG_TYPES = frozenset(
    {
        "string",
        "int",
        "int8",
        "int16",
        "int32",
        "int64",
        "uint",
        "uint8",
        "uint16",
        "uint32",
        "uint64",
        "float32",
        "float64",
        "bool",
        "duration",
        "count",
        "stringArray",
        "stringSlice",
        "intSlice",
    }
)

# Pattern: optional short flag, long flag, optional type token, description.
# Examples:
#   -h, --help              help for root
#   -n, --name string       name to greet (default "World")
#   --config string         config file (default: hello.toml)
#       --verbose           enable verbose output
_FLAG_RE = re.compile(
    r"^\s*"
    r"(?:(-\w),\s*)?"  # optional short flag
    r"(--[\w-]+)"  # long flag (required)
    r"(?:\s+(\S+))?"  # optional type token
    r"\s{2,}"  # separator (≥2 spaces)
    r"(.*)"  # description
)
_DEFAULT_PARENS_RE = re.compile(r"\(default[:\s]+[\"']?([^\"')]+)[\"']?\)\s*$")


def _parse_cobra_flag(raw: str) -> dict | None:
    """Parse a single cobra flag line into a dict compatible with Click's option format.

    Parameters
    ----------
    raw
        A single flag line from `--help` output, e.g.
        "`-n, --name string   name to greet (default \"World\")`"

    Returns
    -------
    dict | None
        Option dict with keys `names`, `name_display`, `type`, `help`, `default`, `is_flag`,
        `required`, `hidden`; or `None` if the line could not be parsed.
    """
    m = _FLAG_RE.match(raw)
    if not m:
        return None

    short, long_name, maybe_type, description = m.group(1), m.group(2), m.group(3), m.group(4)

    # Determine whether maybe_type is actually a type token or part of the description
    if maybe_type and maybe_type.lower() in _GO_FLAG_TYPES:
        flag_type: str | None = maybe_type
    else:
        # Not a type token — treat it as part of the description
        flag_type = None
        if maybe_type:
            description = f"{maybe_type}  {description}".strip()

    is_flag = flag_type is None or flag_type == "bool"

    # Extract default value from description
    default: str | None = None
    dm = _DEFAULT_PARENS_RE.search(description)
    if dm:
        default = dm.group(1).strip()
        description = description[: dm.start()].strip()

    # Build names list and display string
    names = [long_name]
    if short:
        names.insert(0, short)
    name_display = ", ".join(names)

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


def _extract_cobra_commands(
    binary_path: Path,
    name: str,
    parent_args: list[str] | None = None,
) -> dict | None:
    """Recursively extract the command tree from a Cobra CLI binary.

    Calls ``binary [subcommand...] --help`` and parses the output.

    Parameters
    ----------
    binary_path
        Path to the compiled binary.
    name
        Display name for this command node.
    parent_args
        Invocation tokens appended after the binary name to reach this subcommand (e.g.
        `["greet"]` -> `binary greet --help`).
    display_path
        Full display path for this node, e.g. `"hello greet"`. When `None` the node is the root
        command and `name` is used.

    Returns
    -------
    dict | None
        Parsed command structure, or ``None`` on timeout/error.
    """
    args_list = parent_args or []
    cmd_args = [str(binary_path)] + args_list + ["--help"]

    try:
        result = subprocess.run(
            cmd_args,
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Cobra writes --help to stdout; fall back to stderr
        help_text = result.stdout or result.stderr
    except (subprocess.TimeoutExpired, OSError):
        return None

    return _parse_cobra_help(help_text, name, binary_path, args_list)


def _parse_cobra_help(
    help_text: str,
    name: str,
    binary_path: Path,
    parent_args: list[str],
) -> dict:
    """Parse the output of ``<binary> [subcommand...] --help``.

    Cobra's help format is::

        <description paragraph(s)>

        Usage:
          <binary> [command]

        Available Commands:
          cmd-a   Short description
          cmd-b   Short description

        Flags:
          --flag string   Description

        Use "<binary> [command] --help" for more information.

    When command groups are defined the section shows group labels before
    the commands indented by an extra two spaces.
    """
    lines = help_text.splitlines()

    # Description: non-empty lines before the first section header
    desc_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if _SECTION_HEADER_RE.match(stripped):
            break
        if stripped:
            desc_lines.append(stripped)
    description = " ".join(desc_lines)

    # Parse sections
    subcommand_names: list[tuple[str, str]] = []
    flags: list[str] = []
    current_section = ""

    for line in lines:
        stripped = line.strip()

        if _SECTION_HEADER_RE.match(stripped):
            current_section = stripped.rstrip(":")
            continue

        if not stripped:
            continue

        if current_section == "Available Commands":
            m = _COMMAND_LINE_RE.match(line)
            if m:
                cmd_name = m.group(1)
                cmd_desc = m.group(2).strip()
                if cmd_name not in _COBRA_BUILTIN_COMMANDS:
                    subcommand_names.append((cmd_name, cmd_desc))

        elif current_section in ("Flags", "Global Flags", "Persistent Flags"):
            if stripped.startswith("-"):
                flags.append(stripped)

    # Recursively introspect subcommands
    commands: list[dict] = []
    for cmd_name, cmd_short in subcommand_names:
        sub_args = parent_args + [cmd_name]
        sub_info = _extract_cobra_commands(binary_path, cmd_name, sub_args)
        commands.append(
            sub_info
            if sub_info is not None
            else {
                "name": cmd_name,
                "help": cmd_short,
                "short_help": cmd_short,
                "help_text": "",
                "commands": [],
                "options": [],
            }
        )

    return {
        "name": name,
        "help": description,
        "short_help": description[:80] if description else "",
        "help_text": help_text,
        "commands": commands,
        "options": flags,
    }
