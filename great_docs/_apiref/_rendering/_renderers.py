"""
The renderer classes that one API reference uses, and renderer construction from them

A project changes presentation by subclassing a renderer, never by modifying the
built-in classes. `object_renderer_mixin` comes before each default object renderer;
a replacement renderer chooses its own base classes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar, cast, overload

from .._settings import Settings
from ..content import DocAttribute, DocClass, DocFunction, DocModule, DocTypeAlias, Page, Section
from .api_pages import APIPageRenderer
from .attributes import AttributeRenderer
from .base import BaseRenderer
from .classes import ClassRenderer
from .functions import FunctionRenderer
from .modules import ModuleRenderer
from .reference_index import ReferenceIndexRenderer
from .reference_sections import ReferenceSectionRenderer
from .type_aliases import TypeAliasRenderer

if TYPE_CHECKING:
    from pathlib import Path

    from .._customisation import Extension
    from ..api_reference import APIReference


_Renderer = TypeVar("_Renderer", bound=BaseRenderer)


class Renderers:
    """
    Validated renderer classes for object, page and reference presentation

    Each omitted slot uses its built-in renderer. `doc_mixin` precedes default
    object renderers in their method resolution order. Explicit replacements
    include that mixin themselves when needed. Declaring or selecting a subclass
    never changes another renderer class.
    """

    def __init__(
        self,
        *,
        classes: type[ClassRenderer] | None = None,
        functions: type[FunctionRenderer] | None = None,
        attributes: type[AttributeRenderer] | None = None,
        type_aliases: type[TypeAliasRenderer] | None = None,
        modules: type[ModuleRenderer] | None = None,
        api_pages: type[APIPageRenderer] | None = None,
        reference_index: type[ReferenceIndexRenderer] | None = None,
        reference_sections: type[ReferenceSectionRenderer] | None = None,
        doc_mixin: type | None = None,
    ) -> None:
        if doc_mixin is not None and not isinstance(cast("object", doc_mixin), type):
            raise TypeError("`doc_mixin` must be a class.")
        self.classes = self._select("classes", classes, ClassRenderer, doc_mixin)
        self.functions = self._select("functions", functions, FunctionRenderer, doc_mixin)
        self.attributes = self._select("attributes", attributes, AttributeRenderer, doc_mixin)
        self.type_aliases = self._select("type_aliases", type_aliases, TypeAliasRenderer, doc_mixin)
        self.modules = self._select("modules", modules, ModuleRenderer, doc_mixin)
        self.api_pages = self._select("api_pages", api_pages, APIPageRenderer)
        self.reference_index = self._select(
            "reference_index", reference_index, ReferenceIndexRenderer
        )
        self.reference_sections = self._select(
            "reference_sections", reference_sections, ReferenceSectionRenderer
        )

    @staticmethod
    def _select(
        slot: str,
        replacement: type[_Renderer] | None,
        default: type[_Renderer],
        mixin: type | None = None,
    ) -> type[_Renderer]:
        if replacement is not None:
            if not isinstance(cast("object", replacement), type) or not issubclass(
                replacement, default
            ):
                raise TypeError(f"`{slot}` must be a subclass of {default.__name__}.")
            return replacement
        if mixin is None or issubclass(default, mixin):
            return default
        return cast(
            "type[_Renderer]", type(f"{mixin.__name__}{default.__name__}", (mixin, default), {})
        )

    @overload
    def make(
        self, node: DocClass, level: int = 1, *, settings: Settings | None = None, **kwargs: Any
    ) -> ClassRenderer: ...
    @overload
    def make(
        self, node: DocFunction, level: int = 1, *, settings: Settings | None = None, **kwargs: Any
    ) -> FunctionRenderer: ...
    @overload
    def make(
        self, node: DocAttribute, level: int = 1, *, settings: Settings | None = None, **kwargs: Any
    ) -> AttributeRenderer: ...
    @overload
    def make(
        self, node: DocTypeAlias, level: int = 1, *, settings: Settings | None = None, **kwargs: Any
    ) -> TypeAliasRenderer: ...
    @overload
    def make(
        self, node: DocModule, level: int = 1, *, settings: Settings | None = None, **kwargs: Any
    ) -> ModuleRenderer: ...
    @overload
    def make(
        self, node: Page, level: int = 1, *, settings: Settings | None = None, **kwargs: Any
    ) -> APIPageRenderer: ...
    @overload
    def make(
        self, node: Section, level: int = 1, *, settings: Settings | None = None, **kwargs: Any
    ) -> ReferenceSectionRenderer: ...
    @overload
    def make(
        self,
        node: APIReference,
        level: int = 1,
        *,
        sections: list[Section],
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> ReferenceIndexRenderer: ...

    def make(
        self,
        node: object,
        level: int = 1,
        *,
        settings: Settings | None = None,
        sections: list[Section] | None = None,
        extension: Extension | None = None,
        output_root: Path | None = None,
        context_page_path: str | None = None,
        **kwargs: Any,
    ) -> BaseRenderer:
        """
        Construct the selected renderer and propagate these choices to children

        Supply resolved `sections` for a reference index. An index uses its
        reference's settings and rejects conflicting explicit settings. Other
        nodes use the supplied settings, the active extension settings or standalone
        defaults. Conflicting operation settings raise. Pass `extension` to retain
        project roots; page context remains absent when
        no containing output is known.
        """
        from ..api_reference import APIReference

        if isinstance(node, APIReference):
            if sections is None:
                raise TypeError("A reference index requires resolved `sections`.")
            if settings is not None and settings != node.settings:
                raise ValueError("Renderer settings conflict with the API reference settings.")
            extension = extension or node.extension
            if extension.settings != node.settings:
                raise ValueError(
                    "Renderer extension settings conflict with the API reference settings."
                )
            return self.reference_index(
                node,
                sections,
                level,
                renderers=self,
                extension=extension,
                output_root=output_root if output_root is not None else node.output_root,
                context_page_path=context_page_path,
                **kwargs,
            )
        if sections is not None:
            raise TypeError("Only a reference index accepts `sections`.")
        if extension is not None:
            if settings is not None and settings != extension.settings:
                raise ValueError("Renderer settings conflict with the active extension settings.")
            settings = extension.settings
        options: dict[str, Any] = {
            "settings": settings or Settings(),
            "renderers": self,
            "extension": extension,
            "output_root": output_root,
            "context_page_path": context_page_path,
            **kwargs,
        }
        if isinstance(node, DocClass):
            return self.classes(node, level, **options)
        if isinstance(node, DocFunction):
            return self.functions(node, level, **options)
        if isinstance(node, DocAttribute):
            return self.attributes(node, level, **options)
        if isinstance(node, DocTypeAlias):
            return self.type_aliases(node, level, **options)
        if isinstance(node, DocModule):
            return self.modules(node, level, **options)
        if isinstance(node, Page):
            return self.api_pages(node, level, **options)
        if isinstance(node, Section):
            return self.reference_sections(node, level, **options)
        raise ValueError(f"Cannot document object of type {type(node)}")
