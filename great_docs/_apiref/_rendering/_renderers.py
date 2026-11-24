"""
The renderer classes that one API reference uses, and renderer construction from them

A project changes presentation by subclassing a renderer, never by modifying the
built-in classes. `object_renderer_mixin` comes before each default object renderer;
a replacement renderer chooses its own base classes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar, cast, overload

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
    from .._customisation import Extension
    from ..api_reference import APIReference
    from ..typing import Documentable


_Renderer = TypeVar("_Renderer", bound=BaseRenderer)


class Renderers:
    """
    The renderer classes to use for each kind of object and page

    A kind left out uses the built-in renderer. `object_renderer_mixin` comes before
    each default object renderer in its method resolution order, while a replacement
    renderer chooses its own base classes. Defining or selecting a subclass never
    changes the built-in classes. Nested pages, members and summaries use the same
    choices.

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
    object_renderer_mixin
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
        object_renderer_mixin: type | None = None,
    ) -> None:
        """Validate the replacements and use the default renderer for each kind left out"""
        if object_renderer_mixin is not None and not isinstance(
            cast("object", object_renderer_mixin), type
        ):
            raise TypeError("`object_renderer_mixin` must be a class.")
        self.classes = self._select("classes", classes, ClassRenderer, object_renderer_mixin)
        self.functions = self._select(
            "functions", functions, FunctionRenderer, object_renderer_mixin
        )
        self.attributes = self._select(
            "attributes", attributes, AttributeRenderer, object_renderer_mixin
        )
        self.type_aliases = self._select(
            "type_aliases", type_aliases, TypeAliasRenderer, object_renderer_mixin
        )
        self.modules = self._select("modules", modules, ModuleRenderer, object_renderer_mixin)
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
        """
        Validate an explicit replacement or apply a mixin to the default renderer

        Parameters
        ----------
        slot
            The constructor argument that error messages name.
        replacement
            The project's renderer for this slot, or `None` to use the default.
        default
            The built-in renderer that a replacement must subclass.
        mixin
            The class to put before `default` when there is no replacement, or `None`.

        Returns
        -------
        :
            `replacement`, `default`, or a new subclass of `mixin` and `default` when
            `default` does not already inherit from `mixin`.

        Raises
        ------
        TypeError
            If `replacement` is not a subclass of `default`.
        """
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
        self, node: DocClass, level: int = 1, *, extension: Extension | None = None, **kwargs: Any
    ) -> ClassRenderer: ...
    @overload
    def make(
        self,
        node: DocFunction,
        level: int = 1,
        *,
        extension: Extension | None = None,
        **kwargs: Any,
    ) -> FunctionRenderer: ...
    @overload
    def make(
        self,
        node: DocAttribute,
        level: int = 1,
        *,
        extension: Extension | None = None,
        **kwargs: Any,
    ) -> AttributeRenderer: ...
    @overload
    def make(
        self,
        node: DocTypeAlias,
        level: int = 1,
        *,
        extension: Extension | None = None,
        **kwargs: Any,
    ) -> TypeAliasRenderer: ...
    @overload
    def make(
        self, node: DocModule, level: int = 1, *, extension: Extension | None = None, **kwargs: Any
    ) -> ModuleRenderer: ...
    @overload
    def make(
        self, node: Page, level: int = 1, *, extension: Extension | None = None, **kwargs: Any
    ) -> APIPageRenderer: ...
    @overload
    def make(
        self, node: Section, level: int = 1, *, extension: Extension | None = None, **kwargs: Any
    ) -> ReferenceSectionRenderer: ...
    @overload
    def make(
        self, node: APIReference, level: int = 1, *, sections: list[Section], **kwargs: Any
    ) -> ReferenceIndexRenderer: ...

    def make(
        self,
        node: Documentable | APIReference,
        level: int = 1,
        *,
        extension: Extension | None = None,
        sections: list[Section] | None = None,
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
        extension
            The extension that supplies settings and project directories, or `None`
            for default settings. A reference index uses its reference's extension.
        sections
            The resolved sections, which a reference index requires and every other
            kind of node rejects.
        **kwargs
            Further constructor arguments for the selected renderer, such as an object's
            summary-link `page_path`, its `contained` state, or the `context_page_path`
            of its containing page relative to the output directory.

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
            If the node kind is unsupported.
        """
        from ..api_reference import APIReference

        if isinstance(node, APIReference):
            if sections is None:
                raise TypeError("A reference index requires resolved `sections`.")
            return self.reference_index(node, sections, level, renderers=self, **kwargs)
        if sections is not None:
            raise TypeError("Only a reference index accepts `sections`.")
        options: dict[str, Any] = {"renderers": self, **kwargs}
        if extension is not None:
            options["extension"] = extension
        return self._renderer_for(node)(node, level, **options)

    def _renderer_for(self, node: Documentable) -> type[BaseRenderer]:
        """
        Select the renderer class for a node's kind

        Parameters
        ----------
        node
            The prepared object, resolved page or section to present.

        Returns
        -------
        :
            The class in the slot for the first kind the node is an instance of, so
            a subclass of `Page` uses the page slot.

        Raises
        ------
        ValueError
            If the node is of no supported kind.
        """
        slots: dict[type[Documentable], type[BaseRenderer]] = {
            DocClass: self.classes,
            DocFunction: self.functions,
            DocAttribute: self.attributes,
            DocTypeAlias: self.type_aliases,
            DocModule: self.modules,
            Page: self.api_pages,
            Section: self.reference_sections,
        }
        for kind, renderer in slots.items():
            if isinstance(node, kind):
                return renderer
        raise ValueError(f"Cannot document object of type {type(node)}")
