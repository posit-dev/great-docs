from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ._md_renderer import Renderer as _Renderer

if TYPE_CHECKING:
    from . import layout
    from .introspection import Builder
    from .typing import DisplayNameFormat


@dataclass
class Renderer(_Renderer):
    """Render strings to markdown"""

    header_level: int = 1
    show_signature: bool = True
    display_name_format: DisplayNameFormat = "doc"
    signature_name_format: DisplayNameFormat = "doc"
    typing_module_paths: list[str] = field(default_factory=list[str])

    style: str = field(init=False, default="q")

    def render(self, el: layout.Page) -> str:
        """
        Render a page
        """
        from . import RenderAPIPage

        return str(RenderAPIPage(el, self, self.header_level))

    def summarize(self, el: layout.Layout) -> str:
        """
        Summarize a Layout

        A Layout consists of a sequence of layout sections and/or layout pages
        """
        from . import RenderReferencePage

        return str(RenderReferencePage(el, self, self.header_level))

    def _pages_written(self, builder: Builder) -> None:
        self._write_typing_information(builder)

    def _write_typing_information(self, builder: Builder) -> None:
        """
        Render typing information and the interlinks
        """
        from .typing_information import TypeInformation

        for module_path in self.typing_module_paths:
            TypeInformation(module_path, self, builder).write()
