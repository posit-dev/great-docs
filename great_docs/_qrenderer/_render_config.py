from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .typing import DisplayNameFormat


@dataclass
class RenderConfig:
    """Configuration for the rendering system"""

    header_level: int = 1
    show_signature: bool = True
    display_name_format: DisplayNameFormat = "doc"
    signature_name_format: DisplayNameFormat = "doc"
    typing_module_paths: list[str] = field(default_factory=list[str])
