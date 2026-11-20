"""
Conversion of Python objects and their members into documentation nodes

`Doc.from_griffe` builds each node. This module chooses which inherited and aliased
members to include and converts them recursively.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import griffe as gf

from ._parameter_docs import DataclassFields
from .content import Doc, DocAttribute

if TYPE_CHECKING:
    from .typing import DocType


def griffe_to_doc(
    obj: gf.Object | gf.Alias,
    *,
    deep: bool = True,
    inherited: bool = True,
    skip_aliases: bool = False,
    prepare: Callable[[gf.Object | gf.Alias], gf.Object | gf.Alias | None] | None = None,
) -> DocType | None:
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
        Whether to leave out imported and re-exported members. The members of an alias
        are kept when the object it points to defines them.
    prepare
        A function that prepares each object before conversion, or `None` to convert
        objects as they are. An object it excludes is left out with its members.

    Returns
    -------
    :
        The object's documentation node, with selected children when requested,
        or `None` when preparation excludes it. A dataclass node holds the fields its
        constructor parameters cover apart from its members.
    """
    if prepare is not None:
        prepared = prepare(obj)
        if prepared is None:
            return None
        obj = prepared
    members: list[DocType] | None = None
    fields: list[DocAttribute] = []
    if deep:
        members = []
        member_map = obj.all_members if inherited else obj.members
        canonical = obj.final_target if isinstance(obj, gf.Alias) else obj
        canonical_members = canonical.all_members if inherited else canonical.members
        for name, member in member_map.items():
            if skip_aliases and isinstance(member, gf.Alias):
                source_member = canonical_members.get(name)
                if isinstance(source_member, gf.Alias) or source_member is None:
                    continue
            child = griffe_to_doc(
                member, inherited=inherited, skip_aliases=skip_aliases, prepare=prepare
            )
            if child is not None:
                members.append(child)
        members, fields = DataclassFields.make(obj).separate(members)
    return Doc.from_griffe(obj.name, obj, members=members, fields=fields)
