"""
A priority-ordered registry of hook handlers

Handlers with lower priorities run first, and handlers with equal priorities run in
registration order. Snapshots and copies duplicate the list of registrations but share
the handlers themselves. They let an API reference extension register its own handlers
and undo any change its code makes to the global registries.
"""

from __future__ import annotations

from typing import Callable, Generic, TypeVar

H = TypeVar("H", bound=Callable[..., object])


class HookRegistry(Generic[H]):
    """
    A priority-ordered collection of hook handlers

    Iterating the registry yields handlers in run order: lower priority first,
    ties in registration order. The run order is cached and rebuilt only when a
    new handler is registered.
    """

    def __init__(self) -> None:
        self._entries: list[tuple[int, int, H]] = []  # (priority, sequence, hook)
        self._sequence = 0
        self._ordered: list[H] | None = None

    def register(
        self,
        hook: H | None = None,
        *,
        priority: int = 0,
    ) -> H | Callable[[H], H]:
        """
        Register a handler, optionally with a priority

        Parameters
        ----------
        hook
            The handler to register. Omitted when used with arguments
            (`@registry.register(priority=...)`).
        priority
            Run order; lower runs first. Ties keep registration order.

        Returns
        -------
        :
            The handler when used bare, otherwise a decorator that registers the
            handler it receives. Either way the handler is returned unchanged.
        """

        def add(h: H) -> H:
            self._entries.append((priority, self._sequence, h))
            self._sequence += 1
            self._ordered = None
            return h

        return add(hook) if hook is not None else add

    def __iter__(self):
        """Iterate handlers by priority, preserving registration order for ties"""
        if self._ordered is None:
            self._ordered = [h for _, _, h in sorted(self._entries, key=lambda e: e[:2])]
        return iter(self._ordered)

    def __contains__(self, hook: object) -> bool:
        return any(h is hook for _, _, h in self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def snapshot(self) -> tuple[tuple[int, int, H], ...]:
        """
        Capture the current registrations without copying their handlers

        Returns
        -------
        :
            The `(priority, sequence, handler)` entries in registration order.
        """
        return tuple(self._entries)

    def restore(self, entries: tuple[tuple[int, int, H], ...]) -> None:
        """
        Replace the registrations with an earlier snapshot

        Handlers registered afterwards follow the snapshot's handlers in tie order.

        Parameters
        ----------
        entries
            The registrations that `snapshot` returned.
        """
        self._entries = list(entries)
        self._sequence = max((sequence for _, sequence, _ in entries), default=-1) + 1
        self._ordered = None

    def copy(self) -> HookRegistry[H]:
        """
        Copy the registrations into a new registry

        Both registries hold the same handler objects, but a later registration on
        one does not appear in the other.

        Returns
        -------
        :
            A registry with the same handlers in the same run order.
        """
        registry = HookRegistry[H]()
        registry.restore(self.snapshot())
        return registry

    def clear(self) -> None:
        """Drop all registered handlers"""
        self._entries.clear()
        self._sequence = 0
        self._ordered = None
