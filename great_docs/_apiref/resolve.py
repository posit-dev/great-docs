"""
Resolution of the configured API sections into documentation nodes

One loader and one extension serve every section and member, so each object is prepared
once. Member selection filters candidates by name and origin before loading them, and by
their documentation after preparing them. The resulting tree keeps the configured names
and page placement, and rendering, inventories and the text export all read it.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from textwrap import indent
from typing import TYPE_CHECKING, Any, Callable, cast

import griffe as gf
from yaml12 import format_yaml

from great_docs._translations import DEFAULT_LANGUAGE

from ._customisation import Extension
from ._exports import declared_exports
from ._settings import Settings
from ._type_checks import is_enum
from ._walkable import MISSING, MissingType, Walkable
from .content import Doc, MemberPage, Page, Section, Text
from .spec import SpecObject, SpecOptions, SpecSection, SpecText

# Dunder members inherited from `object`/`type` (or PyO3 metaclasses) that carry docstrings but are
# never useful API documentation. Filtered out unconditionally so they do not pollute reference
# pages for compiled extensions (PyO3, Cython, pybind11, C extensions, etc.).
_BUILTIN_NOISE_DUNDERS = frozenset(
    {
        "__doc__",
        "__module__",
        "__dict__",
        "__weakref__",
        "__hash__",
        "__class__",
        "__class_getitem__",
        "__init_subclass__",
        "__subclasshook__",
        "__match_args__",
        "__slots__",
        "__annotations__",
        "__abstractmethods__",
        "__dictoffset__",
        "__flags__",
        "__basicsize__",
        "__itemsize__",
        "__mro_entries__",
        "__orig_bases__",
        "__parameters__",
    }
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from .spec import SpecEntry

_log = logging.getLogger(__name__)

# The language of the API reference whose objects are being resolved. An
# `object_resolved` handler receives only the object, yet the version callouts
# translate their titles while it runs; this variable is the one way the
# language reaches them.
resolution_lang: ContextVar[str] = ContextVar("resolution_lang", default=DEFAULT_LANGUAGE)

# Type alias for the griffe object loader callable used throughout this module.
_GetObject = Callable[..., gf.Object | gf.Alias]


class ObjectNotFoundError(Exception):
    """A configured object path that the loaded package does not contain"""


def _is_external_alias(obj: gf.Alias | gf.Object, mod: gf.Module) -> bool:
    """Check whether an object is an alias to something outside the module's package"""
    package_name = mod.path.split(".")[0]

    if not isinstance(obj, gf.Alias):
        return False

    current_target: gf.Alias | gf.Object = obj

    while current_target.is_alias:
        assert isinstance(current_target, gf.Alias)
        if not current_target.target_path.startswith(package_name):
            return True

        try:
            new_target = current_target.modules_collection[current_target.target_path]

            if new_target is current_target:
                raise ValueError(f"Cyclic Alias: {new_target}")

            current_target = new_target

        except KeyError:
            return True

    return False


def _is_documented_dunder(name: str, obj: gf.Object | gf.Alias) -> bool:
    """
    Check whether a member is a dunder that belongs to the documented API

    Dunders with docstrings (e.g. `__enter__`, `__getitem__`) are documented
    even when private members are excluded.
    """
    return name.startswith("__") and name.endswith("__") and obj.docstring is not None


def _sections_from_package(mod: gf.Module) -> list[SpecSection]:
    """
    Derive default API sections from a package module's exported members

    Use declared export names when they can be resolved, including names from an
    imported `__all__`. When an `__all__` expression cannot be resolved, use public
    members without treating the expression's variable name as an export.
    """

    has_all = "__all__" in mod.members
    declared = declared_exports(mod)

    if not has_all:
        print(
            f"\nWARNING: the module {mod.name} does not define an __all__ attribute."
            " Generating documentation from all members of the module."
            " Define __all__ in your package's __init__.py to specify exactly which"
            " functions it exports (and should be documented).\n"
        )

    if declared is None:
        names = [name for name in mod.members if not has_all or not name.startswith("_")]
    else:
        names = declared

    contents: list[SpecObject] = []
    for name in names:
        member = mod.members.get(name)
        if member is None:
            continue
        external_alias = _is_external_alias(member, mod)
        if external_alias or member.is_module or name.startswith("__"):
            continue

        contents.append(SpecObject(name=name))

    if mod.docstring and mod.docstring.parsed:
        mod_summary = mod.docstring.parsed[0]
        if isinstance(mod_summary, gf.DocstringSectionText):
            desc = mod_summary.value
        else:
            desc = ""
    else:
        desc = ""

    return [SpecSection(title=mod.path, desc=desc, contents=cast("list[SpecEntry]", contents))]


def _to_simple_dict(el: object) -> object:
    """
    Convert reference nodes to YAML-compatible mappings

    Leave unspecified options out so a later build can still choose their
    values automatically.
    """
    if isinstance(el, SpecOptions):
        return {name: _to_simple_dict(value) for name, value in el.specified_options().items()}
    if isinstance(el, Walkable):
        return {k: _to_simple_dict(v) for k, v in el.iter_fields()}
    if isinstance(el, (list, tuple)):
        return [_to_simple_dict(item) for item in el]  # type: ignore[var-annotated]
    return el


def _join_path(pkg: str | None, name: str) -> str:
    """
    Build a Griffe lookup path from a package and a relative or qualified name

    A lookup path carries at most one `:` (separating the module from the
    object within it), so once either part already has one, the remaining
    components join with `.`.
    """
    if pkg is None:
        return name
    name = name.removeprefix(f"{pkg}.")
    if ":" in pkg or ":" in name:
        return f"{pkg}.{name}"
    return f"{pkg}:{name}"


class Resolver:
    """
    A translator from the configured sections to the resolved documentation tree

    Translate authored object selections into shallow documentation nodes with
    selected children. Inherit package and options through nested sections and
    members. A reference supplies its active extension; standalone resolution
    creates default preparation state lazily.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Configure shared acquisition without activating extension setup"""
        from .introspect import get_object as _get_object
        from .introspect import make_loader

        self.settings = settings if settings is not None else Settings()
        loader = make_loader(self.settings.parser)
        self.extension: Extension | None = None

        def acquire(path: str, **kwargs: Any) -> gf.Object | gf.Alias:
            preserve = self.extension.is_prepared if self.extension is not None else None
            return _get_object(path, loader=loader, preserve=preserve, **kwargs)

        self.get_object: _GetObject = acquire

        self.current_package: str | None = None
        self.options: SpecOptions | None = None
        self.dynamic: bool = (
            settings.dynamic if (settings is not None and settings.dynamic is not None) else False
        )
        self.members_on_same_page = settings.members_on_same_page if settings is not None else None
        self.max_members_on_same_page = (
            settings.max_members_on_same_page if settings is not None else 5
        )

    def prepare(self, obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias | None:
        """
        Prepare a loaded object's documentation, once per underlying object

        Aliases of an object share its prepared result or exclusion, so the object and
        docstring hooks run only once.

        Parameters
        ----------
        obj
            The loaded object or alias.

        Returns
        -------
        :
            The prepared object, under the alias's name when `obj` is an alias, or `None`
            when an object hook excludes it.
        """
        if self.extension is None:
            self.extension = Extension(self.settings)
        return self.extension.prepare(obj, get_object=self.get_object)

    def get_object_or_raise(self, path: str, **kwargs: object) -> gf.Object | gf.Alias:
        """Get the Griffe object at `path`, raising `ObjectNotFoundError` if absent"""
        try:
            return self.get_object(path, **kwargs)
        except KeyError as e:
            key_name = e.args[0]
            raise ObjectNotFoundError(
                f"Cannot find an object named: {key_name}."
                f" Does an object with the path {path} exist?"
            )

    def resolve_sections(self, sections: list[SpecSection]) -> list[Section]:
        """
        Resolve the `spec` sections into `content.Section`s, dropping any left empty

        A section whose entries all resolve away (e.g. every entry is `%nodoc`)
        carries no documentation and is omitted, matching the pre-existing
        config-level behaviour.
        """
        resolved = [self._resolve_section(s) for s in sections]
        return [section for section in resolved if section.contents]

    @contextmanager
    def _scoped(
        self,
        *,
        package: str | MissingType | None = MISSING,
        options: SpecOptions | None = None,
    ) -> Generator[None]:
        """
        Scope entries to resolve under the given package and options

        Entries inherit `current_package` and `options` from the enclosing
        context unless the section or object carries its own.
        """
        old_package = self.current_package
        old_options = self.options

        if not isinstance(package, MissingType):
            self.current_package = package
        if options is not None:
            self.options = options

        try:
            yield
        finally:
            self.current_package = old_package
            self.options = old_options

    def _resolve_section(self, el: SpecSection) -> Section:
        """Rebuild a top-level `spec` section with each entry wrapped in a `Page`"""
        with self._scoped(package=el.package, options=el.options):
            contents: list[Any] = [
                resolved
                for entry in el.contents
                if (resolved := self._resolve_entry(entry)) is not None
            ]

        return Section(
            kind=el.kind,
            title=el.title,
            subtitle=el.subtitle,
            desc=el.desc,
            contents=contents,
        )

    def _resolve_entry(self, el: SpecEntry) -> Page | Text | None:
        """
        Rebuild a single section entry as its resolved `content` counterpart

        A documented object becomes its own single-object `Page`; a free-text
        block stays inline as a `Text`. A skipped object yields `None`.
        """
        if isinstance(el, SpecObject):
            doc = self._resolve_object(el)
            if doc is None:
                return None
            return Page(contents=cast("list[Any]", [doc]), path=el.page_path)
        if isinstance(el, SpecText):
            return self._resolve_text(el)
        raise TypeError(f"Cannot resolve section entry of type: {type(el)}")

    def _resolve_text(self, el: SpecText) -> Text:
        """Rebuild a `spec` free-text block as a `content.Text`"""
        return Text(kind=el.kind, contents=el.contents)

    def _resolve_object(self, el: SpecObject) -> Doc | None:
        """Resolve a `SpecObject` to a concrete `Doc`, or skip it"""
        # A member `SpecObject` carries its parent's path as `package`; adopt it
        # so the member's full path is computed relative to the parent.
        with self._scoped(package=el.package):
            return self._resolve_documented_object(el)

    def entry_object(self, section: SpecSection, el: SpecObject) -> gf.Object | gf.Alias:
        """
        Load the object that a section entry documents, without preparing it

        Look the object up exactly as resolving the section would, but skip the hooks,
        docstring parsing and members, so reading the configured sections never runs the
        extension file.
        """
        with self._scoped(package=section.package, options=section.options):
            with self._scoped(package=el.package):
                path, el, dynamic = self._locate(el)
                return self.get_object_or_raise(path, dynamic=dynamic)

    def _locate(self, el: SpecObject) -> tuple[str, SpecObject, bool]:
        """Determine an entry's lookup path, inherited options and dynamic setting"""
        path = _join_path(self.current_package, el.name)

        # Merge inherited section-level options under the entry's own settings.
        el = el.with_defaults(self.options)

        dynamic = el.dynamic if el.dynamic is not None else self.dynamic
        return path, el, dynamic

    def _resolve_documented_object(self, el: SpecObject) -> Doc | None:
        """Locate the subject object in griffe and rebuild it with its resolved members"""
        path, el, dynamic = self._locate(el)

        _log.info(f"Getting object for {path}")

        # The subject object being documented (the class/module/function itself).
        obj = self.prepare(self.get_object_or_raise(path, dynamic=dynamic))
        if obj is None:
            return None
        children = self._resolve_members(el, obj, path=path, dynamic=dynamic)

        return Doc.from_griffe(
            el.name,
            obj,
            children,
            signature_name=el.signature_name,
        )

    def _resolve_members(
        self,
        el: SpecObject,
        obj: gf.Object | gf.Alias,
        *,
        path: str,
        dynamic: bool,
    ) -> list[object]:
        """Resolve selected members on their parent page or separate pages"""
        # Global placement applies only to top-level entries. Nested members
        # share their immediate parent's page unless `member_options` sets placement.
        member_defaults = SpecOptions(dynamic=dynamic, package=path, members_on_same_page=True)

        children: list[Doc] = []
        for entry in self._fetch_members(el, obj, path=path, dynamic=dynamic):
            member_spec = (
                SpecObject(name=entry)
                .with_defaults(el.member_options)
                .with_defaults(member_defaults)
            )
            member_doc = self._resolve_object(member_spec)
            if member_doc is None:
                continue
            # A doc resolved from griffe always carries its object.
            member_obj = member_doc.obj

            if member_obj.kind.value == "module":
                continue

            children.append(member_doc)

        if "members_on_same_page" in el.specified_options():
            same_page = el.members_on_same_page
        elif self.members_on_same_page is not None:
            same_page = self.members_on_same_page
        else:
            same_page = len(children) <= self.max_members_on_same_page

        if same_page:
            return list(children)
        return [MemberPage(path=child.obj.path, contents=[child]) for child in children]

    def _fetch_members(
        self,
        el: SpecObject,
        obj: gf.Object | gf.Alias,
        *,
        path: str,
        dynamic: bool,
    ) -> list[str]:
        """
        Select the names of the members to document

        Use an explicit member list as it is. Otherwise filter candidates by name and
        origin, then load and prepare the rest, importing each one in dynamic mode before
        the object and docstring hooks run. Filters that read documentation see the
        prepared members.

        Parameters
        ----------
        el :
            The entry whose options, or explicit member list, select the members.
        obj :
            The prepared parent object.
        path :
            The parent's lookup path, which prefixes each dynamic member lookup.
        dynamic :
            Whether to load each candidate by importing it.

        Returns
        -------
        :
            The selected member names in the entry's member order.
        """
        if el.members is not None:
            return el.members

        candidates: dict[str, gf.Object | gf.Alias] = (
            dict(obj.all_members) if el.include_inherited else dict(obj.members)
        )

        # Exclude built-in noise before preparing candidates.
        # Always filter built-in noise dunders inherited from `object`/`type`
        # (e.g. `__doc__`, `__module__`). These show up on every PyO3 /
        # C-extension class because their docstrings are inherited from str.
        candidates = {k: v for k, v in candidates.items() if k not in _BUILTIN_NOISE_DUNDERS}

        if obj.is_module and obj.exports is not None:
            candidates = {k: v for k, v in candidates.items() if v.is_exported}

        if not el.include_private:
            candidates = {
                k: v
                for k, v in candidates.items()
                if not k.startswith("_") or (k.startswith("__") and k.endswith("__"))
            }

        if not el.include_imports and obj.is_module:
            candidates = {k: v for k, v in candidates.items() if not v.is_alias}

        if not el.include_inherited and obj.is_class:
            candidates = {
                k: v for k, v in candidates.items() if (v.parent is obj or not v.is_alias)
            }

        # Filtering by name and origin first keeps the dropped imports and private names
        # from being loaded or passed to hooks.
        prepared_candidates: dict[str, gf.Object | gf.Alias] = {}
        for name, member in candidates.items():
            if dynamic:
                member = self.get_object_or_raise(_join_path(path, name), dynamic=True)
            prepared = self.prepare(member)
            if prepared is not None:
                prepared_candidates[name] = prepared
        candidates = prepared_candidates

        if not el.include_private:
            candidates = {
                k: v
                for k, v in candidates.items()
                if not k.startswith("_") or _is_documented_dunder(k, v)
            }

        # The remaining filters read the prepared documentation. Enum members are always
        # shown: their names and values document them even without a docstring.
        if not el.include_empty and not is_enum(obj):
            candidates = {k: v for k, v in candidates.items() if v.docstring is not None}

        if not el.include_attributes:
            candidates = {k: v for k, v in candidates.items() if not v.is_attribute}

        if not el.include_classes:
            candidates = {k: v for k, v in candidates.items() if not v.is_class}

        if not el.include_functions:
            candidates = {k: v for k, v in candidates.items() if not v.is_function}

        if el.include:
            raise NotImplementedError("include argument currently unsupported.")

        if el.exclude:
            candidates = {k: v for k, v in candidates.items() if k not in el.exclude}

        if el.member_order == "alphabetical":
            return sorted(candidates)
        elif el.member_order == "source":
            return list(candidates)
        else:
            raise ValueError(f"Unsupported value of member_order: {el.member_order}")

    def autogenerate_sections(self, package: str | None) -> list[SpecSection]:
        """Generate default API sections and print the equivalent configuration"""
        print("Autogenerating contents (since no contents specified in config)")

        assert isinstance(package, str)

        mod = self.get_object_or_raise(package)
        assert isinstance(mod, gf.Module)
        sections = _sections_from_package(mod)

        if not sections:
            raise ValueError(f"No API sections could be generated for package: {package}")

        recreate_config = {
            "title": "API Reference",
            "description": None,
            "sections": _to_simple_dict(sections),
            "package": package,
            "options": None,
        }
        print(
            "Use the following configuration to recreate the automatically",
            " generated site:\n\n\n",
            "api-reference:\n",
            indent(format_yaml(recreate_config), " " * 2),
            "\n",
            sep="",
        )

        return sections
