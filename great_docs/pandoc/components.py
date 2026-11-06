"""Pandoc element components.

Specification: https://pandoc.org/lua-filters.html#element-components-1
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Sequence

__all__ = ("Attr",)


@dataclass
class Attr:
    """
    A set of attributes (`Attr`)
    """

    identifier: str | None = None
    classes: Sequence[str] | None = None
    attributes: dict[str, str] | None = None

    def __str__(self) -> str:
        parts: list[str] = []
        if self.identifier:
            parts.append(f"#{self.identifier}")

        if self.classes:
            parts.append(" ".join(f".{c}" for c in self.classes))

        if self.attributes:
            parts.append(" ".join(f'{k}="{v}"' for k, v in self.attributes.items()))

        return " ".join(parts)

    @property
    def html(self) -> str:
        parts: list[str] = []

        if self.identifier:
            parts.append(f'id="{self.identifier}"')

        if self.classes:
            s = " ".join(c for c in self.classes)
            parts.append(f'class="{s}"')

        if self.attributes:
            parts.append(" ".join(f'{k}="{v}"' for k, v in self.attributes.items()))
        return " ".join(parts)

    @property
    def empty(self) -> bool:
        return not (self.identifier or self.classes or self.attributes)
