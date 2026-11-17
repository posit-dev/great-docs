"""
Conversion of Python objects and their members into documentation nodes

`Doc.from_griffe` builds each node. This module chooses which inherited and aliased
members to include and converts them recursively.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import griffe as gf

from .content import Doc

if TYPE_CHECKING:
    from .typing import DocType


def griffe_to_doc(
    obj: gf.Object | gf.Alias,
    *,
    deep: bool = True,
    inherited: bool = True,
    skip_aliases: bool = False,
) -> DocType:
    """
    Convert a Python object and selected members into documentation nodes

    Parameters
    ----------
    obj
        The object, or the alias it is documented under.
    deep
        Whether to convert members recursively. `False` builds one node without members.
    inherited
        Whether to include inherited members.
    skip_aliases
        Whether recursive conversion excludes imported and re-exported members.

    Returns
    -------
    :
        The object's documentation node, with selected children when requested.
    """
    members: list[DocType] | None = None
    if deep:
        members = []
        member_map = obj.all_members if inherited else obj.members
        for member in member_map.values():
            if skip_aliases and isinstance(member, gf.Alias):
                continue
            members.append(griffe_to_doc(member, inherited=inherited, skip_aliases=skip_aliases))
    return Doc.from_griffe(obj.name, obj, members=members)
