from __future__ import annotations

import dataclasses
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, cast

from ._walkable import Walkable

# Node -------------------------------------------------------------------------


@dataclass
class Node:
    """A position in the node tree during a traversal"""

    level: int = -1
    value: Any = None
    parent: Node | None = None


# Visitor context --------------------------------------------------------------

ctx_node: ContextVar[Node] = ContextVar("node")


# Visitor base classes ---------------------------------------------------------


class NodeVisitor:
    """A read-only traversal of a node tree"""

    def visit(self, el: object) -> object:
        """
        Enter and exit one node, with `ctx_node` set to its position in the tree

        Parameters
        ----------
        el
            The node to visit.

        Returns
        -------
        :
            The node that `exit` returns.
        """
        old_node = ctx_node.get(None) or Node()
        new_node = Node(level=old_node.level + 1, value=el, parent=old_node)
        token = ctx_node.set(new_node)
        try:
            return self.exit(self.enter(el))
        finally:
            ctx_node.reset(token)

    def enter(self, el: object) -> object:
        """
        Visit the children of a node before it exits

        Dataclass nodes visit their public fields and sequences visit their items. Other
        values have no children.

        Parameters
        ----------
        el
            The node to enter.

        Returns
        -------
        :
            The node to pass to `exit`.
        """
        if isinstance(el, Walkable):
            return self._enter_dataclass(el)
        if isinstance(el, (list, tuple)):
            return self._enter_sequence(cast("list[Any] | tuple[Any, ...]", el))
        return el

    def _enter_dataclass(self, el: Walkable) -> object:
        """
        Visit each public field of a dataclass node

        Parameters
        ----------
        el
            The dataclass node.

        Returns
        -------
        :
            The node itself.
        """
        for f in dataclasses.fields(el):
            if f.name.startswith("_"):
                continue
            _ = self.visit(getattr(el, f.name))
        return el

    def _enter_sequence(self, el: list[Any] | tuple[Any, ...]) -> object:
        """
        Visit each item of a list or tuple

        Parameters
        ----------
        el
            The sequence.

        Returns
        -------
        :
            The sequence itself.
        """
        for child in el:
            _ = self.visit(child)
        return el

    def exit(self, el: object) -> object:
        """
        Finish a node after its children are visited

        Parameters
        ----------
        el
            The node that `enter` returned.

        Returns
        -------
        :
            The visit's result, which is the node itself unless a subclass replaces it.
        """
        return el


class NodeTransformer(NodeVisitor):
    """A node tree rebuilt with only the changed nodes replaced"""

    def _enter_dataclass(self, el: Walkable) -> Walkable:
        """
        Visit each public field of a dataclass node and apply the changed results

        Parameters
        ----------
        el
            The dataclass node.

        Returns
        -------
        :
            A copy with the changed fields replaced, or the node itself when no visit
            changes a field.
        """
        changes: dict[str, object] = {}
        for f in dataclasses.fields(el):
            if f.name.startswith("_"):
                continue
            value = getattr(el, f.name)
            result = self.visit(value)
            if result is not value:
                changes[f.name] = result
        return el.replace(**changes) if changes else el

    def _enter_sequence(self, el: list[Any] | tuple[Any, ...]) -> list[Any] | tuple[Any, ...]:
        """
        Visit each item of a list or tuple

        Parameters
        ----------
        el
            The sequence.

        Returns
        -------
        :
            A new sequence of the same type holding the visit results.
        """
        return el.__class__([self.visit(child) for child in el])
