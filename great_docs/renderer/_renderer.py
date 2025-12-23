from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from quartodoc.renderers.base import Renderer as _Renderer

if TYPE_CHECKING:
    from quartodoc import Builder, layout

    from .typing import DisplayNameFormat


@dataclass
class Renderer(_Renderer):
    """
    Render strings to markdown

    This class provides a scafolding around quartodocs base
    renderer and it helps connect the rendering done by this
    package to the official quartodoc renderer API.
    """

    header_level: int = 1
    show_signature: bool = True
    display_name_format: DisplayNameFormat | Literal["auto"] = "auto"
    signature_name_format: DisplayNameFormat = "name"
    typing_module_paths: list[str] = field(default_factory=list)  # pyright: ignore[reportUnknownVariableType]

    style: str = field(init=False, default="q")

    def render(self, el: layout.Page):
        """
        Render a page
        """
        from . import RenderPage

        return str(RenderPage(el, self, self.header_level))

    def summarize(self, el: layout.Layout):
        """
        Summarize a Layout

        A Layout consists of a sequence of layout sections and/or layout pages
        """
        from . import RenderLayout

        return str(RenderLayout(el, self, self.header_level))

    def _pages_written(self, builder: Builder):
        self._write_typing_information(builder)

    def _write_typing_information(self, builder: Builder):
        """
        Render typing information and the interlinks
        """
        from .typing_information import TypeInformation

        for module_path in self.typing_module_paths:
            TypeInformation(module_path, self, builder).write()
