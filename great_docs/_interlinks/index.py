"""
Merge every inventory into the lookup table the filter reads
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.parse import urljoin

from .._sphinx_inventory import Inventory
from .sources import Source

if TYPE_CHECKING:
    from .._apiref.inventory import InventoryItem


@dataclass(frozen=True)
class AliasResolution:
    """Resolved short names and names claimed by multiple objects"""

    kept: dict[str, str] = field(default_factory=dict)
    dropped: dict[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class AliasClaims:
    """The short names a project's documented objects claim, and the names they may not shadow"""

    claimed: tuple[tuple[str, str], ...] = ()
    """`(short name, full name)` pairs"""

    published: frozenset[str] = frozenset()
    """Full names the project's own inventory publishes"""

    @classmethod
    def make(cls, items: Iterable[InventoryItem]) -> AliasClaims:
        """
        Build the claims from the objects a reference publishes

        Parameters
        ----------
        items :
            The documented objects, each carrying its full name and the short
            names it claims.

        Returns
        -------
        :
            The claims.
        """
        items = list(items)
        return cls(
            claimed=tuple((alias, item.name) for item in items for alias in item.aliases),
            published=frozenset(item.name for item in items),
        )


def resolve_aliases(claims: AliasClaims) -> AliasResolution:
    """
    Keep the short names that exactly one object claims

    A name claimed by two objects is ambiguous, so it is dropped rather than
    resolved to whichever object happens to sort first. A name that is already
    a real name the project publishes is skipped without being reported,
    because the real name resolves it.

    Only this project's own names arbitrate. An external project publishing the
    same spelling does not take a local short name; the local claim outranks it
    in the index instead.

    Parameters
    ----------
    claims :
        What the project's objects claim and what they may not shadow.

    Returns
    -------
    :
        The aliases that resolve, and the ambiguous ones with their claimants.
    """
    claimants: dict[str, set[str]] = {}
    for alias, target in claims.claimed:
        if alias in claims.published:
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


def _resolve_uri(base: str, uri: str) -> str:
    """
    Resolve an inventory uri against the url its source is served from

    A url carrying a scheme gets URL resolution, so an inventory entry that is
    already absolute wins and a root-relative one lands at the host root, which
    is what a consumer of that inventory is meant to do with each. A url naming
    a directory has no such algebra: `urljoin` would normalise a leading `../`
    away, so the two are joined as written and resolve from the reading page.

    Parameters
    ----------
    base :
        The source's url, with a trailing slash.
    uri :
        The uri as the inventory publishes it.

    Returns
    -------
    :
        Where the link points.
    """
    if "://" in base:
        return urljoin(base, uri)
    if "://" in uri:
        return uri
    return f"{base}{uri.lstrip('/')}"


def build_index(
    local: Inventory,
    claims: AliasClaims,
    external: Sequence[tuple[Source, Inventory]],
    *,
    add_function_parentheses: bool = True,
) -> Index:
    """
    Merge every inventory into one lookup table

    Candidates for a name are ordered so that this project wins over another,
    and a higher priority wins within a project. A short name claimed by
    exactly one object is added as a candidate ranked below this project's real
    names and above any other project's; ambiguous ones are reported instead.

    Parameters
    ----------
    local :
        This project's inventory.
    claims :
        The short names this project's documented objects claim.
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

    # Sorted ascending on (rank, -priority): a local real name (0, -priority)
    # first, then a local alias (0, 0), then an external real name
    # (1, -priority). Prose in this project means this project's object.
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
        base = f"{source.link_prefix}/"
        for e in inv.entries:
            add(
                e.name,
                1,
                e.priority,
                IndexEntry(
                    uri=_resolve_uri(base, e.uri),
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

    resolution = resolve_aliases(claims)
    for alias, target in resolution.kept.items():
        for entry in ordered.get(target, ()):
            found.setdefault(alias, []).append(((0, 0), entry))

    ordered = {
        name: tuple(entry for _, entry in sorted(items, key=lambda pair: pair[0]))
        for name, items in found.items()
    }

    return Index(
        names=ordered,
        prefixes=prefixes,
        dropped=resolution.dropped,
        add_function_parentheses=add_function_parentheses,
    )
