from __future__ import annotations

import dataclasses
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, cast

from ._walkable import _Walkable as NodeBase  # pyright: ignore[reportPrivateUsage]

# Node -------------------------------------------------------------------------


@dataclass
class Node:
    """A position in the node tree during a traversal"""

    level: int = -1
    value: Any = None
    parent: Node | None = None


# Visitor context --------------------------------------------------------------

ctx_node: ContextVar[Node] = ContextVar("node")


# Exceptions -------------------------------------------------------------------


class ObjectNotFoundError(Exception):
    """Raised when an object path cannot be resolved to a griffe object"""


# Visitor base classes ---------------------------------------------------------


class NodeVisitor:
    """A read-only traversal of a node tree"""

    LOG = False

    def _log(self, step: str, el: object) -> None:
        if self.LOG:
            print(f"{step}: {type(el)} {el}")

    def visit(self, el: object) -> object:
        old_node = ctx_node.get(None) or Node()
        new_node = Node(level=old_node.level + 1, value=el, parent=old_node)
        token = ctx_node.set(new_node)
        try:
            return self.exit(self.enter(el))
        finally:
            ctx_node.reset(token)

    def enter(self, el: object) -> object:
        if isinstance(el, NodeBase):
            return self._enter_dataclass(el)
        if isinstance(el, (list, tuple)):
            return self._enter_sequence(cast("list[Any] | tuple[Any, ...]", el))
        return el

    def _enter_dataclass(self, el: NodeBase) -> object:
        for f in dataclasses.fields(el):
            if f.name.startswith("_"):
                continue
            _ = self.visit(getattr(el, f.name))
        return el

    def _enter_sequence(self, el: list[Any] | tuple[Any, ...]) -> object:
        for child in el:
            _ = self.visit(child)
        return el

    def exit(self, el: object) -> object:
        return el


class NodeTransformer(NodeVisitor):
    """A node tree rebuilt with only the changed nodes replaced"""

    def _enter_dataclass(self, el: NodeBase) -> NodeBase:
        new_kwargs: dict[str, object] = {}
        changed = False
        for f in dataclasses.fields(el):
            if f.name.startswith("_"):
                continue
            value = getattr(el, f.name)
            result = self.visit(value)
            new_kwargs[f.name] = result
            if result is not value:
                changed = True
        return el.__class__(**new_kwargs) if changed else el

    def _enter_sequence(self, el: list[Any] | tuple[Any, ...]) -> list[Any] | tuple[Any, ...]:
        return el.__class__([self.visit(child) for child in el])
