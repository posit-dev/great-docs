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
    The renderer classes to use for each kind of object and page

    Each omitted slot uses its built-in class. `doc_mixin` precedes default object
    renderers in their method resolution order; explicit replacements control their
    own inheritance. Declaring or selecting a subclass never changes shared classes.
    Nested pages, members and summaries retain the same choices.

    Parameters
    ----------
    classes
        The renderer for classes.
    functions
        The renderer for functions and methods.
    attributes
        The renderer for attributes, properties and PEP 613 type aliases.
    type_aliases
        The renderer for PEP 695 type aliases.
    modules
        The renderer for modules.
    api_pages
        The renderer for pages that document one or more objects.
    reference_index
        The renderer for the whole reference index.
    reference_sections
        The renderer for each section of the reference index.
    doc_mixin
        A class whose methods apply to every default object renderer. A replacement
        renderer gets them only by inheriting from the mixin. Page and section
        renderers never get them.

    Raises
    ------
    TypeError
        If a replacement does not subclass the matching built-in renderer, or the
        mixin is not a class.
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
        """Validate the replacements and use the default renderer for each kind left out"""
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
        """Validate an explicit replacement or apply a mixin to the default renderer"""
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
        Construct the selected renderer for a node and pass these choices on

        Parameters
        ----------
        node
            The prepared object, resolved page or section, or reference index to render.
        level
            The heading depth of this appearance.
        settings
            Explicit operation settings. Omit these to use the supplied extension's
            settings, the index reference's settings or standalone defaults.
        sections
            The resolved sections, which a reference index requires and every other
            kind of node rejects.
        extension
            The extension that supplies the project context. A reference index uses its
            reference's extension.
        output_root
            The documentation output root, or `None` outside a known build.
        context_page_path
            The output-relative containing page destination when known. Absolute paths
            require an enclosing explicit output root before appearing in the renderer context.
        **kwargs
            Additional constructor arguments for the selected kind, such as an object's
            summary-link `page_path` or `contained` state.

        Returns
        -------
        :
            A renderer whose nested appearances use the same choices.

        Raises
        ------
        TypeError
            If index sections are absent, sections are supplied to another kind, or
            constructor arguments are invalid.
        ValueError
            If the node kind is unsupported or explicit settings conflict with its operation.
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
