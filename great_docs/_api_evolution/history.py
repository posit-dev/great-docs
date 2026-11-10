"""API timelines, symbol histories and dependency graphs"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from great_docs._api_evolution.compare import _diff_symbol
from great_docs._api_evolution.model import (
    ApiSnapshot,
    SymbolChange,
    SymbolInfo,
    _symbol_change_to_dict,
)
from great_docs._api_evolution.snapshot import (
    _detect_package_name,
    _get_tag_date,
    list_version_tags,
    snapshot_at_tag,
)


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


def _mermaid_id(name: str) -> str:
    """Convert a dotted Python name to a valid Mermaid node id."""
    return name.replace(".", "_").replace("-", "_")


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


def build_timeline(
    project_root: Path,
    package_name: str | None = None,
    tags: list[str] | None = None,
) -> list[dict]:
    """
    Build a timeline showing API surface growth across tagged versions.

    Parameters
    ----------
    project_root
        Root of the git repository.
    package_name
        Importable module name. Detect it from the project when omitted.
    tags
        Specific tags to include. If `None`, all version tags are used.

    Returns
    -------
    list[dict]
        Each entry has `version`, `symbols`, `classes`, `functions`.
    """
    if package_name is None:
        package_name = _detect_package_name(project_root)
        if package_name is None:
            return []

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
