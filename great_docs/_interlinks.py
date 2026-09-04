"""
Build the index that the interlinks filter resolves links against
"""

from __future__ import annotations

from collections.abc import Container, Iterable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AliasResolution:
    """Which short names resolve, and which are claimed by more than one object"""

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
