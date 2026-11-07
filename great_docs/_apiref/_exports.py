"""
Resolve declared module exports from griffe models
"""

from __future__ import annotations

import griffe as gf


def declared_exports(module: gf.Object | gf.Alias) -> list[str] | None:
    """
    Read statically resolved export names from a module

    Follow an imported `__all__` to its defining module. Omit expressions that griffe
    cannot expand. Return `None` when no names can be resolved, so callers can use their
    public-member fallback. A defined but empty `__all__` returns an empty list.

    Parameters
    ----------
    module
        The loaded module or an alias to it.

    Returns
    -------
    :
        Resolved names in export order, an empty list for an empty `__all__`, or `None`
        when no export names can be read.
    """
    exports = module.exports
    if exports is None:
        all_member = module.members.get("__all__")
        if isinstance(all_member, gf.Alias):
            try:
                exports = all_member.final_target.module.exports
            except (gf.AliasResolutionError, gf.CyclicAliasError):
                return None

    if exports is None:
        return None
    if not exports:
        return []

    names = list(dict.fromkeys(name for name in exports if isinstance(name, str)))
    return names or None
