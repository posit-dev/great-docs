from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from great_docs._subprocess import TEXT_MODE_KWARGS
from great_docs._translations import get_translation

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ParameterInfo:
    """Snapshot of a single function/method parameter."""

    name: str
    annotation: str | None = None
    default: str | None = None
    kind: str = "POSITIONAL_OR_KEYWORD"

    def to_dict(self) -> dict:
        d: dict = {"name": self.name, "kind": self.kind}
        if self.annotation is not None:
            d["annotation"] = self.annotation
        if self.default is not None:
            d["default"] = self.default
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ParameterInfo":
        return cls(
            name=d["name"],
            annotation=d.get("annotation"),
            default=d.get("default"),
            kind=d.get("kind", "POSITIONAL_OR_KEYWORD"),
        )


# ---------------------------------------------------------------------------
# CLI data models
# ---------------------------------------------------------------------------


@dataclass
class CliOptionInfo:
    """Snapshot of a single CLI option or argument."""

    name: str
    type: str = "option"  # "option" or "argument"
    is_flag: bool = False
    required: bool = False
    default: str | None = None
    help: str | None = None

    def to_dict(self) -> dict:
        d: dict = {"name": self.name, "type": self.type}
        if self.is_flag:
            d["is_flag"] = True
        if self.required:
            d["required"] = True
        if self.default is not None:
            d["default"] = self.default
        if self.help is not None:
            d["help"] = self.help
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "CliOptionInfo":
        return cls(
            name=d["name"],
            type=d.get("type", "option"),
            is_flag=d.get("is_flag", False),
            required=d.get("required", False),
            default=d.get("default"),
            help=d.get("help"),
        )


@dataclass
class CliCommandInfo:
    """Snapshot of a single CLI command or subcommand."""

    name: str
    help: str = ""
    options: list[CliOptionInfo] = field(default_factory=list)
    subcommands: list["CliCommandInfo"] = field(default_factory=list)
    is_group: bool = False
    hidden: bool = False
    deprecated: bool = False

    def to_dict(self) -> dict:
        d: dict = {"name": self.name}
        if self.help:
            d["help"] = self.help
        if self.options:
            d["options"] = [o.to_dict() for o in self.options]
        if self.subcommands:
            d["subcommands"] = [c.to_dict() for c in self.subcommands]
        if self.is_group:
            d["is_group"] = True
        if self.hidden:
            d["hidden"] = True
        if self.deprecated:
            d["deprecated"] = True
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "CliCommandInfo":
        return cls(
            name=d["name"],
            help=d.get("help", ""),
            options=[CliOptionInfo.from_dict(o) for o in d.get("options", [])],
            subcommands=[CliCommandInfo.from_dict(c) for c in d.get("subcommands", [])],
            is_group=d.get("is_group", False),
            hidden=d.get("hidden", False),
            deprecated=d.get("deprecated", False),
        )

    def all_command_paths(self, prefix: str = "") -> list[str]:
        """Return flat list of all command paths (e.g. `["build", "check-links"]`)."""
        path = f"{prefix} {self.name}".strip() if prefix else self.name
        paths = [path]
        for sub in self.subcommands:
            paths.extend(sub.all_command_paths(path))
        return paths


# ---------------------------------------------------------------------------
# Python API data models
# ---------------------------------------------------------------------------


@dataclass
class SymbolInfo:
    """Snapshot of a single public API symbol (class, function, etc.)."""

    name: str
    kind: str  # "class", "function", "module", "attribute"
    parameters: list[ParameterInfo] = field(default_factory=list)
    bases: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    is_async: bool = False
    return_annotation: str | None = None

    def to_dict(self) -> dict:
        d: dict = {"name": self.name, "kind": self.kind}
        if self.parameters:
            d["parameters"] = [p.to_dict() for p in self.parameters]
        if self.bases:
            d["bases"] = self.bases
        if self.decorators:
            d["decorators"] = self.decorators
        if self.is_async:
            d["is_async"] = True
        if self.return_annotation is not None:
            d["return_annotation"] = self.return_annotation
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "SymbolInfo":
        return cls(
            name=d["name"],
            kind=d["kind"],
            parameters=[ParameterInfo.from_dict(p) for p in d.get("parameters", [])],
            bases=d.get("bases", []),
            decorators=d.get("decorators", []),
            is_async=d.get("is_async", False),
            return_annotation=d.get("return_annotation"),
        )


@dataclass
class ParameterChange:
    """A change to a single parameter between two API versions."""

    parameter: str
    change_type: str  # added, removed, renamed, retyped, default_changed
    old_value: str | None = None
    new_value: str | None = None
    is_breaking: bool = False


@dataclass
class SymbolChange:
    """A change to a single API symbol between two versions."""

    symbol: str
    change_type: str  # added, removed, changed, kind_changed
    details: list[str] = field(default_factory=list)
    parameter_changes: list[ParameterChange] = field(default_factory=list)
    is_breaking: bool = False
    migration_hint: str | None = None


@dataclass
class ApiSnapshot:
    """Complete snapshot of a package's public API at a point in time."""

    version: str
    package_name: str
    symbols: dict[str, SymbolInfo] = field(default_factory=dict)
    cli_commands: CliCommandInfo | None = None

    @property
    def symbol_count(self) -> int:
        return len(self.symbols)

    @property
    def class_count(self) -> int:
        return sum(1 for s in self.symbols.values() if s.kind == "class")

    @property
    def function_count(self) -> int:
        return sum(1 for s in self.symbols.values() if s.kind == "function")

    @property
    def cli_command_count(self) -> int:
        if not self.cli_commands:
            return 0
        return len(self.cli_commands.all_command_paths())

    def to_dict(self) -> dict:
        d: dict = {
            "version": self.version,
            "package_name": self.package_name,
            "symbols": {name: sym.to_dict() for name, sym in self.symbols.items()},
        }
        if self.cli_commands is not None:
            d["cli"] = self.cli_commands.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ApiSnapshot":
        cli = None
        if "cli" in d:
            cli = CliCommandInfo.from_dict(d["cli"])
        return cls(
            version=d["version"],
            package_name=d["package_name"],
            symbols={name: SymbolInfo.from_dict(sym) for name, sym in d.get("symbols", {}).items()},
            cli_commands=cli,
        )

    def save(self, path: Path) -> None:
        """Save this snapshot to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n")

    @classmethod
    def load(cls, path: Path) -> "ApiSnapshot":
        """Load a snapshot from a JSON file."""
        return cls.from_dict(json.loads(path.read_text()))


@dataclass
class CliChange:
    """A change to a CLI command between two versions."""

    command: str  # full command path, e.g. "build" or "check-links"
    change_type: str  # "added", "removed", "changed"
    details: list[str] = field(default_factory=list)
    is_breaking: bool = False


@dataclass
class ApiDiff:
    """Diff between two API snapshots."""

    old_version: str
    new_version: str
    package_name: str
    added: list[SymbolChange] = field(default_factory=list)
    removed: list[SymbolChange] = field(default_factory=list)
    changed: list[SymbolChange] = field(default_factory=list)
    cli_changes: list[CliChange] = field(default_factory=list)

    @property
    def breaking_changes(self) -> list[SymbolChange]:
        return [c for c in self.removed + self.changed if c.is_breaking]

    @property
    def has_breaking_changes(self) -> bool:
        if self.breaking_changes:
            return True
        return any(c.is_breaking for c in self.cli_changes)

    def to_dict(self) -> dict:
        d: dict = {
            "old_version": self.old_version,
            "new_version": self.new_version,
            "package_name": self.package_name,
            "summary": {
                "added": len(self.added),
                "removed": len(self.removed),
                "changed": len(self.changed),
                "breaking": len(self.breaking_changes),
                "cli_changes": len(self.cli_changes),
            },
            "added": [_symbol_change_to_dict(c) for c in self.added],
            "removed": [_symbol_change_to_dict(c) for c in self.removed],
            "changed": [_symbol_change_to_dict(c) for c in self.changed],
        }
        if self.cli_changes:
            d["cli_changes"] = [
                {
                    "command": c.command,
                    "change_type": c.change_type,
                    "details": c.details,
                    "is_breaking": c.is_breaking,
                }
                for c in self.cli_changes
            ]
        return d


@dataclass
class InheritanceEdge:
    """An edge in the class inheritance graph."""

    child: str
    parent: str


@dataclass
class CallEdge:
    """An edge representing a function/method reference relationship."""

    caller: str
    callee: str


@dataclass
class SymbolHistoryEntry:
    """One version's snapshot of a symbol (signature + diff from previous)."""

    version: str
    present: bool
    signature: str | None = None
    symbol_info: SymbolInfo | None = None
    change: SymbolChange | None = None  # None when unchanged from previous
    date: str | None = None  # tag date (YYYY-MM-DD)


@dataclass
class SymbolHistory:
    """Full history of a single symbol across tagged versions."""

    symbol_name: str
    package_name: str
    entries: list[SymbolHistoryEntry] = field(default_factory=list)

    @property
    def changed_entries(self) -> list[SymbolHistoryEntry]:
        """Only entries where the symbol was added, removed, or changed."""
        result: list[SymbolHistoryEntry] = []
        for i, entry in enumerate(self.entries):
            if i == 0 and entry.present:
                # First appearance is always interesting
                result.append(entry)
            elif entry.change is not None:
                result.append(entry)
            elif i > 0 and not entry.present and self.entries[i - 1].present:
                # Disappeared
                result.append(entry)
            elif i > 0 and entry.present and not self.entries[i - 1].present:
                # Reappeared
                result.append(entry)
        return result

    def to_dict(self, *, changes_only: bool = False) -> dict:
        entries = self.changed_entries if changes_only else self.entries
        return {
            "symbol": self.symbol_name,
            "package": self.package_name,
            "versions": [
                {
                    "version": e.version,
                    "present": e.present,
                    "signature": e.signature,
                    "change": _symbol_change_to_dict(e.change) if e.change else None,
                }
                for e in entries
            ],
        }


@dataclass
class DependencyGraph:
    """Dependency graph of classes and functions in an API snapshot."""

    inheritance: list[InheritanceEdge] = field(default_factory=list)
    calls: list[CallEdge] = field(default_factory=list)
    nodes: dict[str, str] = field(default_factory=dict)  # name -> kind

    def to_mermaid(self) -> str:
        """Render the graph as a Mermaid diagram."""
        lines = ["graph TD"]

        # Node declarations with shapes
        for name, kind in sorted(self.nodes.items()):
            safe = _mermaid_id(name)
            if kind == "class":
                lines.append(f'    {safe}["{name}"]')
            else:
                lines.append(f'    {safe}(["{name}"])')

        # Inheritance edges
        for edge in self.inheritance:
            parent_id = _mermaid_id(edge.parent)
            child_id = _mermaid_id(edge.child)
            lines.append(f"    {parent_id} --> {child_id}")

        # Call edges (dashed)
        for edge in self.calls:
            caller_id = _mermaid_id(edge.caller)
            callee_id = _mermaid_id(edge.callee)
            lines.append(f"    {caller_id} -.-> {callee_id}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mermaid_id(name: str) -> str:
    """Convert a dotted Python name to a valid Mermaid node id."""
    return name.replace(".", "_").replace("-", "_")


def _symbol_change_to_dict(change: SymbolChange) -> dict:
    d: dict = {
        "symbol": change.symbol,
        "change_type": change.change_type,
        "is_breaking": change.is_breaking,
    }
    if change.details:
        d["details"] = change.details
    if change.parameter_changes:
        d["parameter_changes"] = [
            {
                "parameter": pc.parameter,
                "change_type": pc.change_type,
                "old_value": pc.old_value,
                "new_value": pc.new_value,
                "is_breaking": pc.is_breaking,
            }
            for pc in change.parameter_changes
        ]
    if change.migration_hint:
        d["migration_hint"] = change.migration_hint
    return d


def _annotation_str(annotation) -> str | None:
    """Extract a string representation from a griffe annotation."""
    if annotation is None:
        return None
    # griffe annotations can be Name, Expression, or str
    try:
        return str(annotation)
    except Exception:
        return None


def _parameter_kind_str(param) -> str:
    """Get a string for the parameter kind."""
    try:
        return param.kind.name
    except Exception:
        return "POSITIONAL_OR_KEYWORD"


# ---------------------------------------------------------------------------
# Snapshot construction
# ---------------------------------------------------------------------------


def _extract_parameters(obj) -> list[ParameterInfo]:
    """Extract parameter info from a griffe callable."""
    params: list[ParameterInfo] = []
    try:
        for param in obj.parameters:
            # Skip 'self' and 'cls'
            if param.name in ("self", "cls"):
                continue
            params.append(
                ParameterInfo(
                    name=param.name,
                    annotation=_annotation_str(param.annotation),
                    default=str(param.default) if param.default is not None else None,
                    kind=_parameter_kind_str(param),
                )
            )
    except Exception:
        pass
    return params


def _extract_bases(obj) -> list[str]:
    """Extract base class names from a griffe class."""
    bases: list[str] = []
    try:
        for base in obj.bases:
            bases.append(str(base))
    except Exception:
        pass
    return bases


def _extract_decorators(obj) -> list[str]:
    """Extract decorator names from a griffe object."""
    decorators: list[str] = []
    try:
        for dec in obj.decorators:
            decorators.append(str(dec.value))
    except Exception:
        pass
    return decorators


def snapshot_from_griffe(
    package_name: str, version: str, search_paths: list[str] | None = None
) -> ApiSnapshot:
    """
    Build an API snapshot by loading a package with griffe.

    Parameters
    ----------
    package_name
        The Python package name (e.g., `"great_tables"`).
    version
        Version label for this snapshot.
    search_paths
        Additional paths to search for the package source. When loading a historical version
        extracted to a temp directory, pass its path here.

    Returns
    -------
    ApiSnapshot
    """
    import griffe

    normalized = package_name.replace("-", "_")

    loader_kwargs: dict = {}
    if search_paths:
        loader_kwargs["search_paths"] = search_paths

    pkg = griffe.load(normalized, **loader_kwargs)

    # Determine public exports
    exports: list[str] = []
    if hasattr(pkg, "exports") and pkg.exports is not None:
        exports = list(pkg.exports)
    elif "__all__" in pkg.members:
        try:
            all_obj = pkg.members["__all__"]
            if hasattr(all_obj, "value"):
                exports = list(all_obj.value)
        except Exception:
            pass

    if not exports:
        # Fallback: public members (no leading underscore)
        exports = [name for name in pkg.members if not name.startswith("_")]

    skip = {"__version__", "__author__", "__email__", "__all__"}
    symbols: dict[str, SymbolInfo] = {}

    for name in exports:
        if name in skip:
            continue
        if name not in pkg.members:
            continue

        try:
            obj = pkg.members[name]
            kind = obj.kind.value  # "class", "function", "module", "attribute"

            info = SymbolInfo(
                name=name,
                kind=kind,
                parameters=_extract_parameters(obj) if kind in ("function", "class") else [],
                bases=_extract_bases(obj) if kind == "class" else [],
                decorators=_extract_decorators(obj),
                is_async=getattr(obj, "is_async", False),
                return_annotation=_annotation_str(
                    getattr(obj, "annotation", None) or getattr(obj, "returns", None)
                ),
            )
            symbols[name] = info
        except Exception:
            # Skip symbols that fail to introspect (cyclic alias, etc.)
            continue

    return ApiSnapshot(version=version, package_name=normalized, symbols=symbols)


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def list_version_tags(project_root: Path) -> list[str]:
    """
    List git tags that look like version numbers, sorted oldest-first.

    Tags matching patterns like `v1.0.0`, `1.0.0`, `v0.12.3` are included. Non-version tags are
    excluded.
    """
    import re

    try:
        result = subprocess.run(
            ["git", "tag", "--sort=creatordate"],
            cwd=project_root,
            capture_output=True,
            **TEXT_MODE_KWARGS,
            timeout=10,
        )
        if result.returncode != 0:
            return []

        version_re = re.compile(r"^v?\d+\.\d+(\.\d+)?$")
        tags = []
        for line in result.stdout.strip().split("\n"):
            tag = line.strip()
            if tag and version_re.match(tag):
                tags.append(tag)
        return tags

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []


def _get_tag_date(project_root: Path, tag: str) -> str | None:
    """Return the date (YYYY-MM-DD) of a git tag, or None on failure."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ai", tag],
            cwd=project_root,
            capture_output=True,
            **TEXT_MODE_KWARGS,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Format is "2024-01-15 12:34:56 -0500" — take date part
            return result.stdout.strip().split(" ")[0]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def _extract_package_at_tag(
    project_root: Path,
    tag: str,
    package_name: str,
) -> Path | None:
    """
    Extract the package source at a given git tag into a temp directory.

    Uses `git archive` to avoid modifying the working tree. Returns the temp directory path (caller
    is responsible for cleanup), or `None` on failure.
    """
    normalized = package_name.replace("-", "_")

    # Determine the package directory path within the repo
    # Try common layouts: src/<pkg>, <pkg>/
    candidates = [normalized, f"src/{normalized}"]

    for candidate in candidates:
        try:
            # Check if this path exists at that tag
            check = subprocess.run(
                ["git", "ls-tree", "--name-only", tag, candidate + "/"],
                cwd=project_root,
                capture_output=True,
                **TEXT_MODE_KWARGS,
                timeout=10,
            )
            if check.returncode != 0 or not check.stdout.strip():
                continue

            # Extract the package source via git archive
            tmp_dir = tempfile.mkdtemp(prefix="gd_api_diff_")
            result = subprocess.run(
                ["git", "archive", tag, candidate],
                cwd=project_root,
                capture_output=True,
                timeout=30,
            )
            if result.returncode != 0:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                continue

            # Untar the archive into the temp directory
            subprocess.run(
                ["tar", "xf", "-"],
                cwd=tmp_dir,
                input=result.stdout,
                capture_output=True,
                timeout=30,
            )

            # For src-layout, move the package up one level so griffe can find it
            if candidate.startswith("src/"):
                src_pkg = Path(tmp_dir) / "src" / normalized
                dest_pkg = Path(tmp_dir) / normalized
                if src_pkg.exists():
                    shutil.move(str(src_pkg), str(dest_pkg))

            return Path(tmp_dir)

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            continue

    return None


def _read_cli_module_at_tag(
    project_root: Path,
    tag: str,
    package_name: str,
) -> str | None:
    """
    Read `pyproject.toml` at *tag* and return the `cli.module` setting.

    Falls back to `great-docs.yml` at *tag* if `pyproject.toml` doesn't contain CLI config. Returns
    `None` if not found.
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
                # Parse [tool.great-docs.cli] section
                try:
                    import tomllib
                except ImportError:
                    import tomli as tomllib  # type: ignore[no-redef]
                data = tomllib.loads(content)
                cli_cfg = data.get("tool", {}).get("great-docs", {}).get("cli", {})
                if cli_cfg.get("enabled"):
                    return cli_cfg.get("module")
            else:
                # great-docs.yml — simple yaml parse
                try:
                    import yaml

                    data = yaml.safe_load(content) or {}
                    cli_cfg = data.get("cli", {})
                    if cli_cfg.get("enabled"):
                        return cli_cfg.get("module")
                except Exception:
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


def _import_cli_from_source(
    tmp_dir: Path,
    cli_module: str,
) -> CliCommandInfo | None:
    """
    Import a Click CLI from an extracted source tree and snapshot it.

    Temporarily prepends *tmp_dir* to `sys.path`, imports *cli_module*, locates the Click command
    object, snapshots it, then restores `sys.path`.
    """
    import importlib
    import sys

    try:
        import click
    except ImportError:
        return None

    str_dir = str(tmp_dir)
    sys.path.insert(0, str_dir)
    try:
        # Invalidate cached modules that might shadow the extracted source
        parts = cli_module.split(".")
        for i in range(len(parts)):
            prefix = ".".join(parts[: i + 1])
            sys.modules.pop(prefix, None)

        module = importlib.import_module(cli_module)

        # Find Click command/group
        cli_obj = None
        for attr_name in ["cli", "main", "app", "command"]:
            obj = getattr(module, attr_name, None)
            if isinstance(obj, (click.Command, click.Group)):
                cli_obj = obj
                break

        if cli_obj is None:
            for attr_name in dir(module):
                if attr_name.startswith("_"):
                    continue
                obj = getattr(module, attr_name)
                if isinstance(obj, (click.Command, click.Group)):
                    cli_obj = obj
                    break

        if cli_obj is None:
            return None

        return snapshot_cli_from_click(cli_obj)
    except Exception:
        return None
    finally:
        # Restore sys.path and remove imported modules
        if str_dir in sys.path:
            sys.path.remove(str_dir)
        for key in list(sys.modules):
            if key == cli_module or key.startswith(cli_module + "."):
                sys.modules.pop(key, None)


def snapshot_at_tag(
    project_root: Path,
    tag: str,
    package_name: str,
) -> ApiSnapshot | None:
    """
    Build an API snapshot of a package at a specific git tag.

    Parameters
    ----------
    project_root
        Root of the git repository.
    tag
        Git tag name (e.g., `"v1.0.0"`).
    package_name
        Python package name.

    Returns
    -------
    ApiSnapshot | None
        The snapshot, or None if extraction failed.
    """
    tmp_dir = _extract_package_at_tag(project_root, tag, package_name)
    if tmp_dir is None:
        return None

    try:
        snap = snapshot_from_griffe(package_name, version=tag, search_paths=[str(tmp_dir)])

        # Attempt CLI introspection from the version-specific source
        cli_module = _read_cli_module_at_tag(project_root, tag, package_name)
        if cli_module:
            snap.cli_commands = _import_cli_from_source(tmp_dir, cli_module)

        return snap
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Diff logic
# ---------------------------------------------------------------------------


def diff_snapshots(old: ApiSnapshot, new: ApiSnapshot) -> ApiDiff:
    """
    Compute the diff between two API snapshots.

    Parameters
    ----------
    old
        The earlier API snapshot.
    new
        The later API snapshot.

    Returns
    -------
    ApiDiff
    """
    result = ApiDiff(
        old_version=old.version,
        new_version=new.version,
        package_name=new.package_name,
    )

    old_names = set(old.symbols)
    new_names = set(new.symbols)

    # Added symbols
    for name in sorted(new_names - old_names):
        sym = new.symbols[name]
        result.added.append(
            SymbolChange(
                symbol=name,
                change_type="added",
                details=[f"New {sym.kind}: {name}"],
            )
        )

    # Removed symbols — always breaking
    for name in sorted(old_names - new_names):
        sym = old.symbols[name]
        result.removed.append(
            SymbolChange(
                symbol=name,
                change_type="removed",
                details=[f"Removed {sym.kind}: {name}"],
                is_breaking=True,
                migration_hint=f"'{name}' was removed. Check the changelog for a replacement.",
            )
        )

    # Changed symbols
    for name in sorted(old_names & new_names):
        old_sym = old.symbols[name]
        new_sym = new.symbols[name]
        change = _diff_symbol(name, old_sym, new_sym)
        if change is not None:
            result.changed.append(change)

    # CLI changes
    result.cli_changes = _diff_cli(old.cli_commands, new.cli_commands)

    return result


def _diff_symbol(name: str, old: SymbolInfo, new: SymbolInfo) -> SymbolChange | None:
    """Compare two versions of the same symbol."""
    details: list[str] = []
    param_changes: list[ParameterChange] = []
    is_breaking = False
    migration_hints: list[str] = []

    # Kind changed (e.g., function -> class)
    if old.kind != new.kind:
        details.append(f"Kind changed: {old.kind} → {new.kind}")
        is_breaking = True
        migration_hints.append(f"'{name}' changed from {old.kind} to {new.kind}.")

    # Async changed
    if old.is_async != new.is_async:
        if new.is_async:
            details.append("Now async")
            is_breaking = True
            migration_hints.append(f"'{name}' is now async — callers must use 'await'.")
        else:
            details.append("No longer async")
            is_breaking = True

    # Return annotation changed
    if old.return_annotation != new.return_annotation:
        details.append(
            f"Return type: {old.return_annotation or '(none)'} → "
            f"{new.return_annotation or '(none)'}"
        )

    # Base classes changed (for classes)
    if old.bases != new.bases:
        removed_bases = set(old.bases) - set(new.bases)
        added_bases = set(new.bases) - set(old.bases)
        if removed_bases:
            details.append(f"Removed base(s): {', '.join(sorted(removed_bases))}")
            is_breaking = True
        if added_bases:
            details.append(f"Added base(s): {', '.join(sorted(added_bases))}")

    # Decorators changed
    if old.decorators != new.decorators:
        removed_decs = set(old.decorators) - set(new.decorators)
        added_decs = set(new.decorators) - set(old.decorators)
        if removed_decs:
            details.append(f"Removed decorator(s): {', '.join(sorted(removed_decs))}")
        if added_decs:
            details.append(f"Added decorator(s): {', '.join(sorted(added_decs))}")

    # Parameter changes (for functions / class constructors)
    if old.kind in ("function", "class") and new.kind in ("function", "class"):
        param_changes = _diff_parameters(old.parameters, new.parameters)
        for pc in param_changes:
            if pc.is_breaking:
                is_breaking = True
            details.append(_describe_param_change(pc))

    if not details:
        return None

    hint = " ".join(migration_hints) if migration_hints else None

    return SymbolChange(
        symbol=name,
        change_type="changed",
        details=details,
        parameter_changes=param_changes,
        is_breaking=is_breaking,
        migration_hint=hint,
    )


def _diff_parameters(
    old_params: list[ParameterInfo],
    new_params: list[ParameterInfo],
) -> list[ParameterChange]:
    """Diff two parameter lists and detect breaking changes."""
    changes: list[ParameterChange] = []

    old_by_name = {p.name: p for p in old_params}
    new_by_name = {p.name: p for p in new_params}

    old_names = [p.name for p in old_params]
    new_names = [p.name for p in new_params]

    old_set = set(old_names)
    new_set = set(new_names)

    # Removed parameters — breaking
    for name in old_names:
        if name not in new_set:
            changes.append(
                ParameterChange(
                    parameter=name,
                    change_type="removed",
                    old_value=name,
                    is_breaking=True,
                )
            )

    # Added parameters
    for name in new_names:
        if name not in old_set:
            new_p = new_by_name[name]
            # New parameter without a default is breaking (positional)
            has_default = new_p.default is not None
            is_keyword_only = new_p.kind == "KEYWORD_ONLY"
            breaking = not has_default and not is_keyword_only
            changes.append(
                ParameterChange(
                    parameter=name,
                    change_type="added",
                    new_value=name,
                    is_breaking=breaking,
                )
            )

    # Changed parameters (type, default, kind)
    for name in old_names:
        if name not in new_set:
            continue
        old_p = old_by_name[name]
        new_p = new_by_name[name]

        if old_p.annotation != new_p.annotation:
            changes.append(
                ParameterChange(
                    parameter=name,
                    change_type="retyped",
                    old_value=old_p.annotation,
                    new_value=new_p.annotation,
                    is_breaking=False,  # Type changes are risky but not always breaking
                )
            )

        if old_p.default != new_p.default:
            changes.append(
                ParameterChange(
                    parameter=name,
                    change_type="default_changed",
                    old_value=old_p.default,
                    new_value=new_p.default,
                    is_breaking=False,
                )
            )

        if old_p.kind != new_p.kind:
            changes.append(
                ParameterChange(
                    parameter=name,
                    change_type="kind_changed",
                    old_value=old_p.kind,
                    new_value=new_p.kind,
                    is_breaking=True,
                )
            )

    # Check for positional reorderings (breaking for positional args)
    old_positional = [
        n for n in old_names if n in new_set and old_by_name[n].kind != "KEYWORD_ONLY"
    ]
    new_positional = [
        n for n in new_names if n in old_set and new_by_name[n].kind != "KEYWORD_ONLY"
    ]
    if old_positional != new_positional and old_positional and new_positional:
        changes.append(
            ParameterChange(
                parameter="(order)",
                change_type="reordered",
                old_value=", ".join(old_positional),
                new_value=", ".join(new_positional),
                is_breaking=True,
            )
        )

    return changes


def _describe_param_change(pc: ParameterChange) -> str:
    """Human-readable description of a parameter change."""
    prefix = "⚠ " if pc.is_breaking else ""
    match pc.change_type:
        case "added":
            return f"{prefix}New parameter: {pc.parameter}"
        case "removed":
            return f"{prefix}Removed parameter: {pc.parameter}"
        case "retyped":
            return f"{prefix}Parameter '{pc.parameter}' type: {pc.old_value} → {pc.new_value}"
        case "default_changed":
            return f"{prefix}Parameter '{pc.parameter}' default: {pc.old_value} → {pc.new_value}"
        case "kind_changed":
            return f"{prefix}Parameter '{pc.parameter}' kind: {pc.old_value} → {pc.new_value}"
        case "reordered":
            return f"{prefix}Parameters reordered: [{pc.old_value}] → [{pc.new_value}]"
        case _:
            return f"{prefix}Parameter '{pc.parameter}': {pc.change_type}"


# ---------------------------------------------------------------------------
# CLI diffing
# ---------------------------------------------------------------------------


def _flatten_cli(cmd: CliCommandInfo | None, prefix: str = "") -> dict[str, CliCommandInfo]:
    """Flatten a CLI tree into `{full_path: CliCommandInfo}`."""
    if cmd is None:
        return {}
    path = f"{prefix} {cmd.name}".strip() if prefix else cmd.name
    result = {path: cmd}
    for sub in cmd.subcommands:
        result.update(_flatten_cli(sub, path))
    return result


def _diff_cli_command(path: str, old: CliCommandInfo, new: CliCommandInfo) -> CliChange | None:
    """Compare two versions of the same CLI command."""
    details: list[str] = []
    is_breaking = False

    # Options diff
    old_opts = {o.name: o for o in old.options}
    new_opts = {o.name: o for o in new.options}

    for name in sorted(set(new_opts) - set(old_opts)):
        details.append(f"New option: {name}")
    for name in sorted(set(old_opts) - set(new_opts)):
        details.append(f"Removed option: {name}")
        is_breaking = True
    for name in sorted(set(old_opts) & set(new_opts)):
        o, n = old_opts[name], new_opts[name]
        if o.is_flag != n.is_flag:
            details.append(f"Option '{name}' flag changed: {o.is_flag} → {n.is_flag}")
            is_breaking = True
        if o.required != n.required and n.required:
            details.append(f"Option '{name}' is now required")
            is_breaking = True
        if o.default != n.default:
            details.append(f"Option '{name}' default: {o.default!r} → {n.default!r}")

    # Group ↔ non-group change
    if old.is_group != new.is_group:
        details.append(f"Group status changed: {old.is_group} → {new.is_group}")
        is_breaking = True

    if not details:
        return None
    return CliChange(
        command=path,
        change_type="changed",
        details=details,
        is_breaking=is_breaking,
    )


def _diff_cli(old: CliCommandInfo | None, new: CliCommandInfo | None) -> list[CliChange]:
    """Diff two CLI command trees."""
    old_cmds = _flatten_cli(old)
    new_cmds = _flatten_cli(new)
    changes: list[CliChange] = []

    old_paths = set(old_cmds)
    new_paths = set(new_cmds)

    for path in sorted(new_paths - old_paths):
        changes.append(
            CliChange(command=path, change_type="added", details=[f"New command: {path}"])
        )

    for path in sorted(old_paths - new_paths):
        changes.append(
            CliChange(
                command=path,
                change_type="removed",
                details=[f"Removed command: {path}"],
                is_breaking=True,
            )
        )

    for path in sorted(old_paths & new_paths):
        change = _diff_cli_command(path, old_cmds[path], new_cmds[path])
        if change is not None:
            changes.append(change)

    return changes


# ---------------------------------------------------------------------------
# CLI snapshot from Click
# ---------------------------------------------------------------------------


def snapshot_cli_from_click(cli_obj: object) -> CliCommandInfo | None:
    """
    Build a :class:`CliCommandInfo` tree by introspecting a Click command.

    Parameters
    ----------
    cli_obj
        A `click.BaseCommand` instance (Command or Group).

    Returns
    -------
    CliCommandInfo or None
        The CLI snapshot, or `None` if `cli_obj` is not a Click command.
    """
    try:
        import click
    except ImportError:
        return None

    if not isinstance(cli_obj, (click.Command, click.Group)):
        return None

    return _snapshot_click_command(cli_obj)


def _snapshot_click_command(cmd: object) -> CliCommandInfo:
    """Recursively snapshot a Click command tree."""
    import click

    name = getattr(cmd, "name", "") or ""
    help_text = getattr(cmd, "help", "") or ""
    hidden = getattr(cmd, "hidden", False)
    deprecated = getattr(cmd, "deprecated", False)
    is_group = isinstance(cmd, click.Group)

    options: list[CliOptionInfo] = []
    for param in getattr(cmd, "params", []):
        if isinstance(param, click.Option):
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
        elif isinstance(param, click.Argument):
            options.append(
                CliOptionInfo(
                    name=param.name or "",
                    type="argument",
                    required=param.required,
                )
            )

    subcommands: list[CliCommandInfo] = []
    if is_group:
        for subcmd_name, subcmd in getattr(cmd, "commands", {}).items():
            if not getattr(subcmd, "hidden", False):
                subcommands.append(_snapshot_click_command(subcmd))

    return CliCommandInfo(
        name=name,
        help=help_text,
        options=options,
        subcommands=subcommands,
        is_group=is_group,
        hidden=hidden,
        deprecated=deprecated,
    )


# ---------------------------------------------------------------------------
# Dependency graph
# ---------------------------------------------------------------------------


def build_dependency_graph(snapshot: ApiSnapshot) -> DependencyGraph:
    """
    Build a dependency graph from an API snapshot.

    Includes class inheritance edges and records each symbol as a node.

    Parameters
    ----------
    snapshot
        An API snapshot to analyze.

    Returns
    -------
    DependencyGraph
    """
    graph = DependencyGraph()

    for name, info in snapshot.symbols.items():
        graph.nodes[name] = info.kind

        # Class inheritance
        if info.kind == "class":
            for base in info.bases:
                # Only include edges to symbols within the same package
                short_base = base.rsplit(".", 1)[-1]
                if short_base in snapshot.symbols:
                    graph.inheritance.append(InheritanceEdge(child=name, parent=short_base))

    return graph


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------


def build_timeline(
    project_root: Path,
    package_name: str,
    tags: list[str] | None = None,
) -> list[dict]:
    """
    Build a timeline showing API surface growth across tagged versions.

    Parameters
    ----------
    project_root
        Root of the git repository.
    package_name
        Python package name.
    tags
        Specific tags to include. If `None`, all version tags are used.

    Returns
    -------
    list[dict]
        Each entry has `version`, `symbols`, `classes`, `functions`.
    """
    if tags is None:
        tags = list_version_tags(project_root)

    timeline: list[dict] = []
    for tag in tags:
        snap = snapshot_at_tag(project_root, tag, package_name)
        if snap is None:
            continue
        timeline.append(
            {
                "version": tag,
                "symbols": snap.symbol_count,
                "classes": snap.class_count,
                "functions": snap.function_count,
            }
        )

    return timeline


def format_signature(info: SymbolInfo) -> str:
    """Render a human-readable signature string from a SymbolInfo."""
    if info.kind == "attribute":
        ann = f": {info.return_annotation}" if info.return_annotation else ""
        return f"{info.name}{ann}"

    if info.kind == "module":
        return info.name

    # Function or class
    parts: list[str] = []
    for p in info.parameters:
        piece = p.name
        if p.annotation:
            piece += f": {p.annotation}"
        if p.default is not None:
            piece += f" = {p.default}"
        parts.append(piece)
    params_str = ", ".join(parts)

    prefix = ""
    if info.is_async:
        prefix = "async "
    if info.kind == "class":
        bases = f"({', '.join(info.bases)})" if info.bases else ""
        return f"{prefix}class {info.name}{bases}({params_str})"

    ret = f" -> {info.return_annotation}" if info.return_annotation else ""
    return f"{prefix}def {info.name}({params_str}){ret}"


def symbol_history(
    project_root: Path,
    symbol_name: str,
    package_name: str | None = None,
    tags: list[str] | None = None,
) -> SymbolHistory | None:
    """
    Track a single symbol across all tagged versions.

    Parameters
    ----------
    project_root
        Root of the git repository.
    symbol_name
        Name of the symbol to track (e.g., `"GreatDocs"`).
    package_name
        Python package name. Auto-detected if omitted.
    tags
        Specific tags to scan. If `None`, all version tags are used.

    Returns
    -------
    SymbolHistory | None
        The history, or `None` if the package name cannot be determined.
    """
    if package_name is None:
        package_name = _detect_package_name(project_root)
        if package_name is None:
            return None

    if tags is None:
        tags = list_version_tags(project_root)

    history = SymbolHistory(symbol_name=symbol_name, package_name=package_name)
    prev_info: SymbolInfo | None = None

    for tag in tags:
        tag_date = _get_tag_date(project_root, tag)
        snap = snapshot_at_tag(project_root, tag, package_name)
        if snap is None:
            continue

        info = snap.symbols.get(symbol_name)
        if info is None:
            change = None
            if prev_info is not None:
                # Symbol was removed
                change = SymbolChange(
                    symbol=symbol_name,
                    change_type="removed",
                    details=[f"Removed in {tag}"],
                    is_breaking=True,
                )
            history.entries.append(
                SymbolHistoryEntry(
                    version=tag,
                    present=False,
                    signature=None,
                    symbol_info=None,
                    change=change,
                    date=tag_date,
                )
            )
            prev_info = None
            continue

        sig = format_signature(info)
        change = None
        if prev_info is None and history.entries:
            # Symbol appeared (wasn't in the previous version)
            change = SymbolChange(
                symbol=symbol_name,
                change_type="added",
                details=[f"Added in {tag}"],
            )
        elif prev_info is not None:
            change = _diff_symbol(symbol_name, prev_info, info)

        history.entries.append(
            SymbolHistoryEntry(
                version=tag,
                present=True,
                signature=sig,
                symbol_info=info,
                change=change,
                date=tag_date,
            )
        )
        prev_info = info

    return history


# ---------------------------------------------------------------------------
# Evolution table
# ---------------------------------------------------------------------------


def _augment_params_with_separators(
    params: list[ParameterInfo],
) -> list[ParameterInfo]:
    """Insert a synthetic `*` separator before keyword-only parameters.

    If the parameter list has `KEYWORD_ONLY` parameters but no `VAR_POSITIONAL` (`*args`) parameter,
    a `ParameterInfo(name="*")` entry is inserted at the boundary so that the evolution table can
    display the separator row.
    """
    has_var_positional = any(p.kind == "VAR_POSITIONAL" for p in params)
    if has_var_positional:
        return params  # *args already acts as the separator

    first_kw_idx: int | None = None
    for i, p in enumerate(params):
        if p.kind == "KEYWORD_ONLY":
            first_kw_idx = i
            break

    if first_kw_idx is None:
        return params  # no keyword-only params

    augmented = list(params[:first_kw_idx])
    augmented.append(
        ParameterInfo(name="*", annotation=None, default=None, kind="KEYWORD_ONLY_SEPARATOR")
    )
    augmented.extend(params[first_kw_idx:])
    return augmented


def _cell_text(param: ParameterInfo) -> str:
    """Render a parameter's type + default as file line 2 of a cell."""
    parts: list[str] = []
    if param.annotation:
        parts.append(param.annotation)
    if param.default is not None:
        parts.append(f"= {param.default}")
    return " ".join(parts) if parts else ""


def _cell_lines(param: ParameterInfo) -> tuple[str, str]:
    """Return (line1, line2) for a parameter cell.

    Line 1 is the parameter name, line 2 is `type (= default)`.
    """
    return (param.name, _cell_text(param))


def _escape_html(text: str) -> str:
    """Minimal HTML escaping for table cell content."""
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def evolution_table(
    history: SymbolHistory,
    *,
    changes_only: bool = True,
) -> list[list[tuple[str, str]]]:
    """
    Build a positional-slot table of a symbol's parameter evolution.

    Each cell is a `(line1, line2)` tuple where *line1* is the parameter name and *line2* is
    `type (= default)`. Parameters are laid out by **position** (row 0 is the first parameter in
    each version, row 1 is the second, etc.) so insertions, removals, and reorderings are visible.

    Parameters
    ----------
    history
        A `SymbolHistory` for the symbol.
    changes_only
        If `True` (default), only include versions where the symbol changed.

    Returns
    -------
    list[list[tuple[str, str]]]
        Row 0 is the header: `[("", version1), ("", version2), ...]`. Subsequent rows are positional
        parameter slots. A row with `line1 == "*"` marks the keyword-only boundary. A trailing row
        with `line1 == "Returns:"` is appended when any version has a return annotation. Empty slots
        use `("—", "")`.
    """
    entries = history.changed_entries if changes_only else history.entries
    present_entries = [e for e in entries if e.present and e.symbol_info is not None]

    if not present_entries:
        return []

    versions = [e.version for e in present_entries]
    header: list[tuple[str, str]] = [("", v) for v in versions]

    # Augment each version's params with * separators
    augmented_params = [
        _augment_params_with_separators(e.symbol_info.parameters)  # type: ignore[union-attr]
        for e in present_entries
    ]

    # Determine the maximum parameter count across all versions
    max_params = max(len(p) for p in augmented_params)

    rows: list[list[tuple[str, str]]] = [header]
    empty_cell: tuple[str, str] = ("\u2014", "")

    for slot in range(max_params):
        row: list[tuple[str, str]] = []
        for params in augmented_params:
            if slot < len(params):
                row.append(_cell_lines(params[slot]))
            else:
                row.append(empty_cell)
        rows.append(row)

    # Return-type row
    return_values: list[tuple[str, str]] = []
    has_return = False
    for entry in present_entries:
        assert entry.symbol_info is not None
        ann = entry.symbol_info.return_annotation
        if ann:
            has_return = True
            return_values.append(("Returns:", ann))
        else:
            return_values.append(("Returns:", "\u2014"))
    if has_return:
        rows.append(return_values)

    return rows


def evolution_table_text(
    history: SymbolHistory,
    *,
    changes_only: bool = True,
) -> str:
    """
    Render the evolution table as aligned plain-text (for terminal output).

    Each cell is two lines: the parameter name and its type/default.

    Parameters
    ----------
    history
        A `SymbolHistory` for the symbol.
    changes_only
        If `True` (default), only include versions where the symbol changed.

    Returns
    -------
    str
        A formatted text table.
    """
    rows = evolution_table(history, changes_only=changes_only)
    if not rows:
        return "(no data)"

    header = rows[0]
    body = rows[1:]
    n_cols = len(header)

    # Compute column widths (widest of: version label, any param name, any type line)
    widths = [0] * n_cols
    for _, version in header:
        for i in range(n_cols):
            widths[i] = max(widths[i], len(header[i][1]))
    for row in body:
        for i, (line1, line2) in enumerate(row):
            widths[i] = max(widths[i], len(line1), len(line2))

    col_sep = "  \u2502  "
    lines: list[str] = []

    # Header row (version labels)
    hdr_line = col_sep.join(header[i][1].center(widths[i]) for i in range(n_cols))
    lines.append(hdr_line)
    lines.append(col_sep.join("\u2500" * widths[i] for i in range(n_cols)))

    # Body rows — each logical row is two text lines
    for row_idx, row in enumerate(body):
        line1_parts = []
        line2_parts = []
        for i, (l1, l2) in enumerate(row):
            line1_parts.append(l1.ljust(widths[i]))
            line2_parts.append(l2.ljust(widths[i]))
        lines.append(col_sep.join(line1_parts))
        lines.append(col_sep.join(line2_parts))
        # Thin separator between parameter slots (not after the last)
        if row_idx < len(body) - 1:
            lines.append(col_sep.join("\u2504" * widths[i] for i in range(n_cols)))

    return "\n".join(lines)


def evolution_table_html(
    history: SymbolHistory,
    *,
    changes_only: bool = True,
    disclosure: bool = False,
    summary_text: str | None = None,
) -> str:
    """
    Render the evolution table as an HTML `<table>`.

    Each body cell contains the parameter name on one line and the type/default on a second line.
    When *disclosure* is True the table is wrapped in a `<details>` element so it starts collapsed.

    Parameters
    ----------
    history
        A `SymbolHistory` for the symbol.
    changes_only
        If True (default), only include versions where the symbol changed.
    disclosure
        Wrap the table in a `<details>/<summary>` element.
    summary_text
        Custom text for the `<summary>` label. Defaults to `"Signature evolution for <symbol>"`.

    Returns
    -------
    str
        An HTML string.
    """
    rows = evolution_table(history, changes_only=changes_only)
    if not rows:
        return "<!-- no evolution data -->"

    header = rows[0]
    body = rows[1:]

    # Build a version→date lookup from the history entries
    date_map: dict[str, str] = {}
    entries = history.changed_entries if changes_only else history.entries
    for entry in entries:
        if entry.date:
            date_map[entry.version] = entry.date

    parts: list[str] = []
    parts.append('<table class="gd-evolution-table">')

    # Header
    parts.append("  <thead>")
    parts.append("    <tr>")
    for _, version in header:
        date = date_map.get(version)
        title_attr = f' title="{_escape_html(date)}"' if date else ""
        parts.append(f"      <th{title_attr}>{_escape_html(version)}</th>")
    parts.append("    </tr>")
    parts.append("  </thead>")

    # Body
    parts.append("  <tbody>")
    for row in body:
        parts.append("    <tr>")
        for line1, line2 in row:
            is_absent = line1 == "\u2014" and not line2
            is_star = line1 == "*" and not line2
            is_return = line1 == "Returns:"
            if is_absent:
                parts.append('      <td class="gd-evo-absent">\u2014</td>')
            elif is_star:
                parts.append('      <td class="gd-evo-separator">*</td>')
            elif is_return:
                type_html = _escape_html(line2) if line2 else ""
                inner = '<span class="gd-evo-return-label">Returns:</span>'
                if type_html:
                    inner += f'<br><span class="gd-evo-type">{type_html}</span>'
                parts.append(f"      <td>{inner}</td>")
            else:
                name_html = _escape_html(line1)
                type_html = _escape_html(line2) if line2 else ""
                inner = f'<span class="gd-evo-name">{name_html}</span>'
                if type_html:
                    inner += f'<br><span class="gd-evo-type">{type_html}</span>'
                parts.append(f"      <td>{inner}</td>")
        parts.append("    </tr>")
    parts.append("  </tbody>")
    parts.append("</table>")

    table_html = "\n".join(parts)

    if disclosure:
        if summary_text:
            label = summary_text
        else:
            template = get_translation("evo_disclosure_summary")
            label = template.format(symbol=_escape_html(history.symbol_name))
        return (
            f'<details class="gd-evolution-disclosure">\n'
            f"  <summary>{label}</summary>\n"
            f"  {table_html}\n"
            f"</details>"
        )

    return table_html


# -- Embedded CSS for self-contained HTML output ---------------------------

_EVOLUTION_TABLE_CSS = """\
<style>
.gd-evolution-table {
  border-collapse: collapse;
  font-size: 0.8em;
  width: 100%;
  margin-top: 0.5em;
}
.gd-evolution-table th {
  background: var(--bs-tertiary-bg, #f0f0f0);
  padding: 0.5em 1em;
  text-align: center;
  border: 1px solid var(--bs-border-color, #dee2e6);
  font-family: var(--bs-font-monospace, monospace);
  font-weight: 600;
  cursor: help;
}
.gd-evolution-table td {
  padding: 0.5em 1em;
  border: 1px solid var(--bs-border-color, #dee2e6);
  vertical-align: top;
  min-width: 8em;
}
.gd-evo-name {
  font-family: var(--bs-font-monospace, monospace);
  font-weight: 600;
  color: var(--bs-emphasis-color, #212529);
}
.gd-evo-type {
  font-family: var(--bs-font-monospace, monospace);
  font-size: 0.88em;
  color: var(--bs-secondary-color, #6c757d);
}
.gd-evo-absent {
  text-align: center;
  color: var(--bs-secondary-color, #adb5bd);
  vertical-align: middle;
}
.gd-evo-separator {
  text-align: center;
  font-family: var(--bs-font-monospace, monospace);
  font-weight: 600;
  color: var(--bs-secondary-color, #6c757d);
  vertical-align: middle;
}
.gd-evo-return-label {
  font-weight: 600;
  font-style: italic;
  color: var(--bs-emphasis-color, #212529);
}
.gd-evolution-disclosure summary {
  cursor: pointer;
  font-weight: 600;
  margin-bottom: 0.5em;
}
</style>"""


def render_evolution_table(
    project_path: str | Path,
    symbol: str,
    *,
    package: str | None = None,
    old_version: str | None = None,
    new_version: str | None = None,
    changes_only: bool = True,
    disclosure: bool = False,
    summary_text: str | None = None,
    include_css: bool = True,
) -> str:
    """
    Generate a self-contained HTML block for a symbol's evolution table.

    This is the high-level entry point that combines git history lookup, parameter evolution
    analysis, and HTML rendering into a single call. The output is ready to be inserted into a
    documentation page (e.g., via a `%` directive or a Quarto shortcode).

    Parameters
    ----------
    project_path
        Root of the git repository.
    symbol
        Fully qualified or short name of the symbol to track (e.g., `"build"` or
        `"GreatDocs.build"`).
    package
        Python package name. Auto-detected from *project_path* if omitted.
    old_version
        Earliest version tag to include. If omitted, starts from the first tag where the symbol
        appears.
    new_version
        Latest version tag to include. If omitted, goes through the most recent tag.
    changes_only
        If `True` (default), only show versions where the signature actually changed.
    disclosure
        If `True` (default), wrap the table in a collapsible `<details>/<summary>` element.
    summary_text
        Custom label for the `<summary>` element. Defaults to
        `"Signature evolution for <symbol>()"`.
    include_css
        If `True` (default), prepend the CSS `<style>` block so the output is fully self-contained.
        Set to `False` when the page already includes the styles (e.g., multiple tables on one
        page).

    Returns
    -------
    str
        A complete HTML string (optionally with embedded CSS) that can be inserted directly into a
        page. Returns an HTML comment `<!-- no evolution data for <symbol> -->` when the symbol has
        no history.

    Examples
    --------
    >>> html = render_evolution_table(".", "build")  # doctest: +SKIP
    >>> print(html[:30])                             # doctest: +SKIP
    <style>
    .gd-evolution-table {
    """
    project_root = Path(project_path).resolve()

    # Resolve tags
    all_tags = list_version_tags(project_root)
    if not all_tags:
        return f"<!-- no version tags found for {_escape_html(symbol)} -->"

    # Filter tag range
    tags = _filter_tag_range(all_tags, old_version, new_version)
    if not tags:
        return f"<!-- no matching tags for {_escape_html(symbol)} -->"

    # Build history
    history = symbol_history(project_root, symbol, package_name=package, tags=tags)
    if history is None or not history.entries:
        return f"<!-- no evolution data for {_escape_html(symbol)} -->"

    # Render HTML table
    html = evolution_table_html(
        history,
        changes_only=changes_only,
        disclosure=disclosure,
        summary_text=summary_text,
    )

    if html.startswith("<!--"):
        return html

    if include_css:
        return f"{_EVOLUTION_TABLE_CSS}\n{html}"
    return html


def render_evolution_table_from_dict(
    data: dict,
    *,
    disclosure: bool = False,
    summary_text: str | None = None,
    include_css: bool = True,
) -> str:
    """
    Render an evolution table from a JSON-compatible dict.

    This accepts the same schema produced by :func:`evolution_table_to_dict` (or loaded from a
    `.json` file) and renders it as a self-contained HTML block. This is useful for demo tables,
    pre-computed snapshots, or CI-generated data where a live git repository is not available.

    Parameters
    ----------
    data
        A dict matching the `evolution_table_to_dict` schema::

            {
              "symbol": "build",
              "versions": ["v1.0", "v2.0"],
              "slots": [{"position": 0, "cells": [...]}],
              "returns": ["None", "int"],       // optional
              "dates": ["2024-01-15", null]     // optional
            }
    disclosure
        Wrap in a `<details>/<summary>` element.
    summary_text
        Custom `<summary>` label.
    include_css
        Prepend the `<style>` block.

    Returns
    -------
    str
        A complete HTML string.
    """
    versions: list[str] = data.get("versions", [])
    if not versions:
        return "<!-- no evolution data -->"

    symbol_name: str = data.get("symbol", "unknown")
    dates: list[str | None] = data.get("dates", [])
    n_cols = len(versions)

    # Build the rows structure: list[list[tuple[str, str]]]
    header: list[tuple[str, str]] = [("", v) for v in versions]
    rows: list[list[tuple[str, str]]] = [header]
    empty_cell: tuple[str, str] = ("\u2014", "")

    for slot in data.get("slots", []):
        # Handle * separator slots
        if "separator" in slot:
            row: list[tuple[str, str]] = [("*", "")] * n_cols
            rows.append(row)
            continue

        cells = slot.get("cells", [])
        row = []
        for cell in cells:
            if cell is None:
                row.append(empty_cell)
            else:
                name = cell.get("name", "")
                type_str = cell.get("type") or ""
                default = cell.get("default")
                line2_parts: list[str] = []
                if type_str:
                    line2_parts.append(type_str)
                if default is not None:
                    line2_parts.append(f"= {default}")
                row.append((name, " ".join(line2_parts)))
        # Pad if fewer cells than versions
        while len(row) < n_cols:
            row.append(empty_cell)
        rows.append(row)

    # Return-type row
    returns: list[str | None] | None = data.get("returns")
    if returns and any(r is not None for r in returns):
        ret_row: list[tuple[str, str]] = []
        for r in returns:
            ret_row.append(("Returns:", r if r else "\u2014"))
        while len(ret_row) < n_cols:
            ret_row.append(("Returns:", "\u2014"))
        rows.append(ret_row)

    # Build date map
    date_map: dict[str, str] = {}
    for i, v in enumerate(versions):
        if i < len(dates) and dates[i]:
            date_map[v] = dates[i]  # type: ignore[assignment]

    # Render HTML using the same logic as evolution_table_html
    body = rows[1:]
    parts: list[str] = []
    parts.append('<table class="gd-evolution-table">')
    parts.append("  <thead>")
    parts.append("    <tr>")
    for _, version in header:
        date = date_map.get(version)
        title_attr = f' title="{_escape_html(date)}"' if date else ""
        parts.append(f"      <th{title_attr}>{_escape_html(version)}</th>")
    parts.append("    </tr>")
    parts.append("  </thead>")

    parts.append("  <tbody>")
    for row in body:
        parts.append("    <tr>")
        for line1, line2 in row:
            is_absent = line1 == "\u2014" and not line2
            is_star = line1 == "*" and not line2
            is_return = line1 == "Returns:"
            if is_absent:
                parts.append('      <td class="gd-evo-absent">\u2014</td>')
            elif is_star:
                parts.append('      <td class="gd-evo-separator">*</td>')
            elif is_return:
                type_html = _escape_html(line2) if line2 else ""
                inner = '<span class="gd-evo-return-label">Returns:</span>'
                if type_html:
                    inner += f'<br><span class="gd-evo-type">{type_html}</span>'
                parts.append(f"      <td>{inner}</td>")
            else:
                name_html = _escape_html(line1)
                type_html = _escape_html(line2) if line2 else ""
                inner = f'<span class="gd-evo-name">{name_html}</span>'
                if type_html:
                    inner += f'<br><span class="gd-evo-type">{type_html}</span>'
                parts.append(f"      <td>{inner}</td>")
        parts.append("    </tr>")
    parts.append("  </tbody>")
    parts.append("</table>")

    table_html = "\n".join(parts)

    if disclosure:
        if summary_text:
            label = summary_text
        else:
            template = get_translation("evo_disclosure_summary")
            label = template.format(symbol=_escape_html(symbol_name))
        table_html = (
            f'<details class="gd-evolution-disclosure">\n'
            f"  <summary>{label}</summary>\n"
            f"  {table_html}\n"
            f"</details>"
        )

    if include_css:
        return f"{_EVOLUTION_TABLE_CSS}\n{table_html}"
    return table_html


def _filter_tag_range(
    tags: list[str],
    old_version: str | None,
    new_version: str | None,
) -> list[str]:
    """Return the sub-list of *tags* between *old_version* and *new_version*.

    Both bounds are inclusive. If a bound is `None`, the corresponding end of the list is used. If a
    bound is not found in *tags*, the full list is returned.
    """
    if old_version is None and new_version is None:
        return tags

    start = 0
    end = len(tags)

    if old_version is not None:
        for i, t in enumerate(tags):
            if t == old_version:
                start = i
                break

    if new_version is not None:
        for i, t in enumerate(tags):
            if t == new_version:
                end = i + 1
                break

    return tags[start:end]


def evolution_table_to_dict(
    history: SymbolHistory,
    *,
    changes_only: bool = True,
) -> dict:
    """
    Serialize the positional evolution table to a JSON-compatible dict.

    The returned structure captures everything needed to render the table in a documentation page,
    CI report, or external tool.

    Parameters
    ----------
    history
        A `SymbolHistory` for the symbol.
    changes_only
        If `True` (default), only include versions where the symbol changed.

    Returns
    -------
    dict
        Schema::

            {
              "symbol": "build",
              "package": "my_package",
              "versions": ["v1.0", "v2.0", "v3.0"],
              "slots": [
                {
                  "position": 0,
                  "cells": [
                    {"name": "src", "type": "str", "default": null},
                    {"name": "src", "type": "Path", "default": null},
                    ...
                  ]
                },
                ...
              ],
              "returns": ["None", "None", "int"]   // omitted if no return types
            }

        Each `cells` list is parallel to `versions`. A `null` entry in `cells` means the parameter
        slot did not exist in that version.
    """
    rows = evolution_table(history, changes_only=changes_only)
    if not rows:
        return {
            "symbol": history.symbol_name,
            "package": history.package_name,
            "versions": [],
            "slots": [],
        }

    header = rows[0]
    body = rows[1:]
    versions = [v for _, v in header]

    slots: list[dict] = []
    returns: list[str | None] = None  # type: ignore[assignment]

    for row in body:
        # Detect if this is the return-type row
        if any(line1 == "Returns:" for line1, _ in row):
            returns = []
            for line1, line2 in row:
                returns.append(line2 if line2 and line2 != "\u2014" else None)
            continue

        # Detect * separator row
        if any(line1 == "*" and not line2 for line1, line2 in row):
            slots.append({"position": len(slots), "separator": "*"})
            continue

        slot_cells: list[dict | None] = []
        for line1, line2 in row:
            if line1 == "\u2014" and not line2:
                slot_cells.append(None)
            else:
                # Parse line2 back into type and default
                cell: dict = {"name": line1}
                if line2:
                    if " = " in line2:
                        type_part, default_part = line2.split(" = ", 1)
                        cell["type"] = type_part if type_part else None
                        cell["default"] = default_part
                    else:
                        cell["type"] = line2
                        cell["default"] = None
                else:
                    cell["type"] = None
                    cell["default"] = None
                slot_cells.append(cell)

        slots.append(
            {
                "position": len(slots),
                "cells": slot_cells,
            }
        )

    result: dict = {
        "symbol": history.symbol_name,
        "package": history.package_name,
        "versions": versions,
        "slots": slots,
    }
    if returns is not None:
        result["returns"] = returns

    return result


def timeline_to_mermaid(timeline: list[dict]) -> str:
    """Render a timeline as a Mermaid bar chart."""
    lines = [
        "xychart-beta",
        '    title "API Surface Growth"',
        "    x-axis [{}]".format(", ".join(f'"{e["version"]}"' for e in timeline)),
        '    y-axis "Symbol count"',
        "    bar [{}]".format(", ".join(str(e["symbols"]) for e in timeline)),
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Top-level convenience
# ---------------------------------------------------------------------------


def api_diff(
    project_root: Path,
    old_version: str,
    new_version: str,
    package_name: str | None = None,
) -> ApiDiff | None:
    """
    High-level entry point: diff a package between two git tags.

    Parameters
    ----------
    project_root
        Root of the git repository.
    old_version
        Old git tag (e.g., `"v1.0.0"`).
    new_version
        New git tag (e.g., `"v2.0.0"`). Use `"HEAD"` for the working tree.
    package_name
        Python package name. Auto-detected from pyproject.toml if omitted.

    Returns
    -------
    ApiDiff | None
        The diff, or `None` if snapshots could not be built.
    """
    if package_name is None:
        package_name = _detect_package_name(project_root)
        if package_name is None:
            return None

    # Build snapshots
    if new_version.upper() == "HEAD":
        new_snap = snapshot_from_griffe(package_name, version="HEAD")
    else:
        new_snap = snapshot_at_tag(project_root, new_version, package_name)

    old_snap = snapshot_at_tag(project_root, old_version, package_name)

    if old_snap is None or new_snap is None:
        return None

    return diff_snapshots(old_snap, new_snap)


def _detect_package_name(project_root: Path) -> str | None:
    """Detect the package name from pyproject.toml."""
    pyproject = project_root / "pyproject.toml"
    if not pyproject.exists():
        return None

    try:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib

        with open(pyproject, "rb") as f:
            data = tomllib.load(f)

        name = data.get("project", {}).get("name")
        if name:
            return name.replace("-", "_")
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# QMD marker processing
# ---------------------------------------------------------------------------

import re as _re

_EVOLUTION_MARKER_RE = _re.compile(
    r"<!--\s*%evolution\b([^>]*?)-->",
    _re.DOTALL,
)

_MARKER_ATTR_RE = _re.compile(r"""(\w+)\s*=\s*(?:"([^"]*)"|'([^']*)'|(\S+))""")


def _parse_marker_attrs(attr_string: str) -> dict[str, str]:
    """Parse `key="value"` attributes from a marker body."""
    attrs: dict[str, str] = {}
    for m in _MARKER_ATTR_RE.finditer(attr_string):
        key = m.group(1)
        value = m.group(2) or m.group(3) or m.group(4) or ""
        attrs[key] = value
    return attrs


def process_evolution_markers(
    content: str,
    project_path: str | Path,
    *,
    package: str | None = None,
) -> str:
    """
    Replace `<!-- %evolution ... -->` markers in text with rendered tables.

    This function scans *content* (typically a `.qmd` file body) for HTML comment markers of the
    form::

        <!-- %evolution symbol="build" -->

    and replaces each one with the output of :func:`render_evolution_table`.

    Supported attributes
    --------------------
    symbol (required)
        Name of the symbol to track.
    old_version
        Earliest version tag (inclusive).
    new_version
        Latest version tag (inclusive).
    changes_only
        `"true"` (default) or `"false"`.
    disclosure
        `"true"` (default) or `"false"`.
    summary
        Custom `<summary>` text for the disclosure wrapper.
    css
        `"true"` (default) or `"false"`: whether to include the `<style>` block. Set to `"false"`
        when multiple tables appear on the same page and only the first needs the CSS.

    Parameters
    ----------
    content
        The text to scan (e.g., the body of a `.qmd` file).
    project_path
        Root of the git repository.
    package
        Python package name. Auto-detected if omitted.

    Returns
    -------
    str
        *content* with every `<!-- %evolution ... -->` marker replaced by the corresponding HTML
        table. Markers that fail to render (e.g., missing `symbol`) are replaced with an HTML
        comment explaining the error.

    Examples
    --------
    A `.qmd` file might contain::

        ## Build function

        The signature has evolved over time:

        <!-- %evolution symbol="build" changes_only="true" -->

    After processing, the marker line is replaced with the full HTML table (and optionally embedded
    CSS).
    """
    project_root = Path(project_path).resolve()

    def _replace(match: _re.Match) -> str:
        attrs = _parse_marker_attrs(match.group(1))

        symbol = attrs.get("symbol")
        if not symbol:
            return "<!-- %evolution error: missing symbol attribute -->"

        def _bool(key: str, default: bool = True) -> bool:
            val = attrs.get(key, "")
            if not val:
                return default
            return val.lower() not in ("false", "no", "0")

        try:
            return render_evolution_table(
                project_root,
                symbol,
                package=attrs.get("package") or package,
                old_version=attrs.get("old_version"),
                new_version=attrs.get("new_version"),
                changes_only=_bool("changes_only"),
                disclosure=_bool("disclosure"),
                summary_text=attrs.get("summary"),
                include_css=_bool("css"),
            )
        except Exception as exc:
            return f"<!-- %evolution error for {_escape_html(symbol)}: {_escape_html(str(exc))} -->"

    return _EVOLUTION_MARKER_RE.sub(_replace, content)


def process_evolution_markers_in_file(
    qmd_path: str | Path,
    project_path: str | Path,
    *,
    package: str | None = None,
    in_place: bool = False,
) -> str:
    """
    Process `<!-- %evolution ... -->` markers in a `.qmd` file.

    Parameters
    ----------
    qmd_path
        Path to the `.qmd` file.
    project_path
        Root of the git repository.
    package
        Python package name. Auto-detected if omitted.
    in_place
        If `True`, overwrite *qmd_path* with the processed content. If `False` (default), return the
        processed content without modifying the file.

    Returns
    -------
    str
        The processed file content.
    """
    path = Path(qmd_path)
    content = path.read_text(encoding="utf-8")
    result = process_evolution_markers(content, project_path, package=package)

    if in_place and result != content:
        path.write_text(result, encoding="utf-8")

    return result


# ---------------------------------------------------------------------------
# API diff annotations (version badges)
# ---------------------------------------------------------------------------


def compute_version_badges(
    current: ApiSnapshot,
    previous: ApiSnapshot | None,
) -> dict[str, dict]:
    """
    Compute version badges for each symbol in *current* based on a diff against *previous*.

    Parameters
    ----------
    current
        The API snapshot for the version being documented.
    previous
        The API snapshot for the preceding version, or None if this is the first version.

    Returns
    -------
    dict[str, dict]
        Mapping of symbol name to badge info. Each value has keys: `"badge"` (`"new"`, `"changed"`,
        or `"deprecated"`), `"version"` (the current snapshot's version label), and optionally
        `"details"` (list of change descriptions).
    """
    badges: dict[str, dict] = {}

    # Check for deprecation decorators in current
    for name, sym in current.symbols.items():
        if any("deprecated" in d.lower() for d in sym.decorators):
            badges[name] = {
                "badge": "deprecated",
                "version": current.version,
            }

    if previous is None:
        # Everything is new in the first version — don't badge
        return badges

    diff = diff_snapshots(previous, current)

    for change in diff.added:
        # Don't override a deprecation badge
        if change.symbol not in badges:
            badges[change.symbol] = {
                "badge": "new",
                "version": current.version,
            }

    for change in diff.changed:
        if change.symbol not in badges:
            badges[change.symbol] = {
                "badge": "changed",
                "version": current.version,
                "details": change.details,
            }

    return badges


def render_badge_html(badge_info: dict) -> str:
    """
    Render a single badge as an HTML `<span>` for embedding in QMD pages.

    Parameters
    ----------
    badge_info
        A dict with `"badge"` and `"version"` keys (as returned by :func:`compute_version_badges`).

    Returns
    -------
    str
        An HTML `<span>` element with appropriate CSS class.
    """
    badge = badge_info["badge"]
    version = _escape_html(badge_info["version"])

    if badge == "new":
        return f'<span class="gd-badge gd-badge-new">New in {version}</span>'
    elif badge == "changed":
        return f'<span class="gd-badge gd-badge-changed">Changed in {version}</span>'
    elif badge == "deprecated":
        return f'<span class="gd-badge gd-badge-deprecated">Deprecated in {version}</span>'
    return ""


def inject_badges_into_qmd(
    content: str,
    badges: dict[str, dict],
) -> str:
    """
    Inject version badges into QMD content for API reference pages.

    Looks for lines that define API symbols (e.g. `## SymbolName` or `### package.SymbolName`) and
    inserts the badge HTML immediately after the heading.

    Parameters
    ----------
    content
        The `.qmd` file content.
    badges
        Badge dict as returned by :func:`compute_version_badges`.

    Returns
    -------
    str
        The content with badge HTML injected after matching headings.
    """
    if not badges:
        return content

    lines = content.split("\n")
    result: list[str] = []

    for line in lines:
        result.append(line)
        # Match Markdown headings: ## Name or ### pkg.Name
        stripped = line.strip()
        if stripped.startswith("#"):
            # Extract the heading text (after the # marks)
            heading_text = stripped.lstrip("#").strip()
            # Check both the full qualified name and the short name
            symbol_name = heading_text.split(".")[-1] if "." in heading_text else heading_text
            # Also strip any { .class } suffixes from Quarto
            symbol_name = symbol_name.split("{")[0].strip()
            heading_text_clean = heading_text.split("{")[0].strip()

            badge_info = badges.get(symbol_name) or badges.get(heading_text_clean)
            if badge_info:
                result.append(render_badge_html(badge_info))

    return "\n".join(result)


def load_snapshots_for_annotations(
    snapshot_dir: Path,
    current_version: str,
    previous_version: str | None,
) -> tuple[ApiSnapshot | None, ApiSnapshot | None]:
    """
    Load current and previous snapshots from a directory.

    Parameters
    ----------
    snapshot_dir
        Directory containing `<version>.json` snapshot files.
    current_version
        Version tag for the current snapshot.
    previous_version
        Version tag for the previous snapshot, or None.

    Returns
    -------
    tuple[ApiSnapshot | None, ApiSnapshot | None]
        `(current, previous)` snapshot pair.
    """
    current = None
    previous = None

    current_path = snapshot_dir / f"{current_version}.json"
    if current_path.exists():
        current = ApiSnapshot.load(current_path)

    if previous_version:
        prev_path = snapshot_dir / f"{previous_version}.json"
        if prev_path.exists():
            previous = ApiSnapshot.load(prev_path)

    return current, previous
