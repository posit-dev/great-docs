from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field


@dataclass
class Exclusions:
    """Members left out of the generated documentation

    Each mapping is keyed by a parent object's path (as shown on the API
    page); the value names the member — or members — of that object to
    leave out: parameters of a callable, or attributes, functions, and
    classes of a class or module.
    """

    parameters: dict[str, str | Sequence[str]] = field(default_factory=dict[str, str | Sequence[str]])
    attributes: dict[str, str | Sequence[str]] = field(default_factory=dict[str, str | Sequence[str]])
    functions: dict[str, str | Sequence[str]] = field(default_factory=dict[str, str | Sequence[str]])
    classes: dict[str, str | Sequence[str]] = field(default_factory=dict[str, str | Sequence[str]])


EXCLUSIONS = Exclusions()
