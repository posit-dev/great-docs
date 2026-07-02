from __future__ import annotations

import copy
from collections.abc import Generator
from dataclasses import dataclass
from dataclasses import fields as dc_fields


@dataclass
class _Walkable:
    """
    Base of every value in the API-reference model

    Membership marks a value as a node of the reference tree.
    """

    def copy(self) -> _Walkable:
        """Return a shallow copy of this node"""
        return copy.copy(self)

    def _iter_fields(self) -> Generator[tuple[str, object], None, None]:
        """Iterate (field_name, value) pairs for every dataclass field on this node"""
        for f in dc_fields(self):
            yield f.name, getattr(self, f.name)


@dataclass
class MISSING(_Walkable):
    """Sentinel for an unset optional value where `None` carries its own meaning"""
