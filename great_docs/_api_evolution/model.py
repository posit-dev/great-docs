from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


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
