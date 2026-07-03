from __future__ import annotations

import copy
import dataclasses
from collections.abc import Generator
from dataclasses import dataclass
from dataclasses import fields as dc_fields
from typing import Self


@dataclass
class Walkable:
    """
    Base of every value in the API-reference model

    Membership marks a value as a node of the reference tree.
    """

    def copy(self) -> Self:
        """Return a shallow copy of this node"""
        return copy.copy(self)

    def replace(self, **changes: object) -> Self:
        """Return a copy of this node with the given fields replaced

        Subclasses that carry state outside their dataclass fields override
        this to preserve it.
        """
        return dataclasses.replace(self, **changes)

    def _iter_fields(self) -> Generator[tuple[str, object], None, None]:
        """Iterate (field_name, value) pairs for every dataclass field on this node"""
        for f in dc_fields(self):
            yield f.name, getattr(self, f.name)


@dataclass(eq=False)
class MissingType(Walkable):
    """Sentinel type for an unset optional value where `None` carries its own meaning

    Checks compare against the `MISSING` singleton with `is`. Identity
    hashing (`Walkable`'s dataclass `eq` sets `__hash__` to `None`) is what
    lets `MISSING` stand as a plain dataclass field default.
    """

    __hash__ = object.__hash__


MISSING = MissingType()
