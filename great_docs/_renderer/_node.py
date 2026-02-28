from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Node:
    level: int = -1
    value: Any = None
    parent: Optional[Node] = None
