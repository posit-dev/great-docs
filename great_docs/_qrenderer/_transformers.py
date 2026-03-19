from __future__ import annotations

import dataclasses
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Optional, Union

from .layout import _Base as LayoutBase

# Node -------------------------------------------------------------------------


@dataclass
class Node:
    level: int = -1
    value: Any = None
    parent: Optional[Node] = None


# Transformer -----------------------------------------------------------------

ctx_node: ContextVar[Node] = ContextVar("node")


class WorkaroundKeyError(Exception):
    """Represents a KeyError.

    Note that this is necessary to work around a bug in plum dispatch, which
    intercepts KeyErrors. Kept for API compatibility.
    """


class PydanticTransformer:
    LOG = False

    def _log(self, step: str, el: object) -> None:
        if self.LOG:
            print(f"{step}: {type(el)} {el}")

    def visit(self, el: object) -> object:
        self._log("PARENT VISITING", el)

        old_node = ctx_node.get(None)
        if old_node is None:
            old_node = Node()

        new_node = Node(level=old_node.level + 1, value=el, parent=old_node)

        token = ctx_node.set(new_node)

        try:
            result = self.enter(el)
            return self.exit(result)
        finally:
            ctx_node.reset(token)

    def enter(self, el: object) -> object:
        """Enter an element. Dispatches based on type."""
        self._log("GENERIC ENTER", el)

        if isinstance(el, LayoutBase):
            return self._enter_dataclass(el)
        elif isinstance(el, (list, tuple)):
            return self._enter_sequence(el)

        return el

    def _enter_dataclass(self, el: LayoutBase) -> LayoutBase:
        """Handle dataclass enter — iterates fields and visits children."""
        self._log("GENERIC ENTER", el)
        new_kwargs = {}

        has_change = False
        for f in dataclasses.fields(el):
            if f.name.startswith("_"):
                continue
            value = getattr(el, f.name)
            result = self.visit(value)
            if result is not value:
                has_change = True
                new_kwargs[f.name] = result
            else:
                new_kwargs[f.name] = value

        if has_change:
            return el.__class__(**new_kwargs)

        return el

    def _enter_sequence(self, el: Union[list, tuple]) -> Union[list, tuple]:
        """Handle list/tuple enter."""
        self._log("GENERIC ENTER", el)
        final = []

        for child in el:
            result = self.visit(child)
            if result is not child:
                final.append(result)
            else:
                final.append(child)

        return el.__class__(final)

    def exit(self, el: object) -> object:
        """Exit an element. Override in subclasses for type-specific behavior."""
        self._log("GENERIC EXIT", el)
        return el


# Implementations -------------------------------------------------------------


class _TypeExtractor(PydanticTransformer):
    def __init__(self, target_cls: type) -> None:
        self.target_cls = target_cls
        self.results: list[object] = []

    def exit(self, el: object) -> object:
        if isinstance(el, self.target_cls):
            self.results.append(el)

        return el

    @classmethod
    def run(cls, target_cls: type, el: object) -> list[object]:
        extractor = cls(target_cls)
        extractor.visit(el)

        return extractor.results


extract_type = _TypeExtractor.run
