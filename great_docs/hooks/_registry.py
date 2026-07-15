"""
A priority-ordered registry of event handlers, shared by the pipeline events

Holds handlers paired with a numeric priority and yields them in run order:
lower priority first, ties in registration order. Registration doubles as a
decorator, used bare or with a priority. The event modules each own one
instance and supply their own emit semantics.
"""

from __future__ import annotations

from typing import Callable, Generic, TypeVar

H = TypeVar("H", bound=Callable[..., object])


class HookRegistry(Generic[H]):
    """
    A priority-ordered collection of event handlers

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
        """Iterate the handlers in run order, sorted by `(priority, sequence)`"""
        if self._ordered is None:
            self._ordered = [h for _, _, h in sorted(self._entries, key=lambda e: e[:2])]
        return iter(self._ordered)

    def __contains__(self, hook: object) -> bool:
        return any(h is hook for _, _, h in self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def clear(self) -> None:
        """Drop all registered handlers"""
        self._entries.clear()
        self._sequence = 0
        self._ordered = None
