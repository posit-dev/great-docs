"""
Merge every inventory into the lookup table the filter reads
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Container, Iterable, Sequence
from dataclasses import dataclass, field
from urllib.parse import urljoin

from .._sphinx_inventory import Inventory
from .sources import Source


@dataclass(frozen=True)
class AliasResolution:
    """Resolved short names and names claimed by multiple objects"""

    kept: dict[str, str] = field(default_factory=dict)
    dropped: dict[str, tuple[str, ...]] = field(default_factory=dict)


def resolve_aliases(
    claims: Iterable[tuple[str, str]],
    *,
    taken: Container[str],
) -> AliasResolution:
    """
    Keep the short names that exactly one object claims

    A name claimed by two objects is ambiguous, so it is dropped rather than
    resolved to whichever object happens to sort first. A name that is already
    a real name in the inventory is skipped without being reported, because the
    real name resolves it.

    Parameters
    ----------
    claims :
        `(alias, target)` pairs, where target is the object's full name.
    taken :
        Real inventory names, which an alias may not shadow.

    Returns
    -------
    :
        The aliases that resolve, and the ambiguous ones with their claimants.
    """
    claimants: dict[str, set[str]] = {}
    for alias, target in claims:
        if alias in taken:
            continue
        claimants.setdefault(alias, set()).add(target)

    kept = {a: next(iter(t)) for a, t in claimants.items() if len(t) == 1}
    dropped = {a: tuple(sorted(t)) for a, t in claimants.items() if len(t) > 1}
    return AliasResolution(kept=kept, dropped=dropped)


@dataclass(frozen=True)
class IndexEntry:
    """A reference target and the page that documents it"""

    uri: str
    domain: str
    role: str
    source: str = ""
    is_local: bool = False


@dataclass(frozen=True)
class Index:
    """The names and targets needed to resolve references"""

    names: dict[str, tuple[IndexEntry, ...]] = field(default_factory=dict)
    prefixes: dict[str, tuple[str, ...]] = field(default_factory=dict)
    dropped: dict[str, tuple[str, ...]] = field(default_factory=dict)
    add_function_parentheses: bool = True
    """Whether a link to a function or method shows a trailing `()`"""


def root_modules(inv: Inventory) -> tuple[str, ...]:
    """
    Find the modules an inventory documents, most frequent first

    An alias is written against a module, not against the name the source is
    filed under, so a source keyed `scikit-learn` serving `sklearn.*` names
    still resolves. An entry outside the Python domain, such as a page in a
    source's narrative documentation, names no module and is not counted.

    Parameters
    ----------
    inv :
        The inventory to inspect.

    Returns
    -------
    :
        Root module names.
    """
    counts = Counter(e.name.split(".")[0] for e in inv.entries if e.domain == "py")
    return tuple(name for name, _ in counts.most_common())


def build_index(
    local: Inventory,
    claims: Iterable[tuple[str, str]],
    external: Sequence[tuple[Source, Inventory]],
    *,
    add_function_parentheses: bool = True,
) -> Index:
    """
    Merge every inventory into one lookup table

    Candidates for a name are ordered so that this project wins over another,
    and a higher priority wins within a project. Short names claimed by exactly
    one object are added as ordinary entries; ambiguous ones are reported
    instead.

    Parameters
    ----------
    local :
        This project's inventory.
    claims :
        `(alias, target)` pairs from the documented objects.
    external :
        Each source and the inventory read for it.
    add_function_parentheses :
        Whether a link to a function or method shows a trailing `()`.

    Returns
    -------
    :
        The index.
    """
    found: dict[str, list[tuple[tuple[int, int], IndexEntry]]] = {}

    def add(name: str, rank: int, priority: int, entry: IndexEntry) -> None:
        found.setdefault(name, []).append(((rank, -priority), entry))

    for e in local.entries:
        add(
            e.name,
            0,
            e.priority,
            IndexEntry(uri=f"/{e.uri.lstrip('/')}", domain=e.domain, role=e.role, is_local=True),
        )

    prefixes: dict[str, tuple[str, ...]] = {}
    for source, inv in external:
        # urljoin discards the last path segment of a base without a trailing
        # slash, and leaves an absolute or root-relative uri to win, which is
        # what a consumer of that inventory is meant to do with one.
        base = f"{source.link_prefix}/"
        for e in inv.entries:
            add(
                e.name,
                1,
                e.priority,
                IndexEntry(
                    uri=urljoin(base, e.uri),
                    domain=e.domain,
                    role=e.role,
                    source=source.name,
                ),
            )
        roots = root_modules(inv)
        for alias in source.aliases:
            prefixes[alias] = roots

    ordered = {
        name: tuple(entry for _, entry in sorted(items, key=lambda pair: pair[0]))
        for name, items in found.items()
    }

    resolution = resolve_aliases(claims, taken=ordered)
    for alias, target in resolution.kept.items():
        if target in ordered:
            ordered[alias] = ordered[target]

    return Index(
        names=ordered,
        prefixes=prefixes,
        dropped=resolution.dropped,
        add_function_parentheses=add_function_parentheses,
    )
