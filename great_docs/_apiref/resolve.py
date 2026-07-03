from __future__ import annotations

import logging
from contextlib import contextmanager
from enum import Enum
from functools import partial
from textwrap import indent
from typing import TYPE_CHECKING, Any, Callable, cast

import griffe as gf
from yaml12 import format_yaml

from ._walkable import MISSING, MissingType, Walkable
from .content import Doc, Link, MemberPage, Page, Section, Text
from .introspect import resolve_alias
from .spec import ChildrenStyle, SpecObject, SpecSection, SpecText

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
    from collections.abc import Iterator

    from .api_reference import Settings
    from .spec import SpecEntry, SpecOptions

_log = logging.getLogger(__name__)

# Type alias for the griffe object loader callable used throughout this module.
_GetObject = Callable[..., gf.Object | gf.Alias]


class ObjectNotFoundError(Exception):
    """Raised when an object path cannot be resolved to a griffe object"""


def _is_external_alias(obj: gf.Alias | gf.Object, mod: gf.Module) -> bool:
    """Whether an object is an alias whose target lives outside the given module's package"""
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


def _sections_from_package(mod: gf.Module) -> list[SpecSection]:
    """Derive default API sections from a package module's exported members"""

    has_all = "__all__" in mod.members

    if not has_all:
        print(
            f"\nWARNING: the module {mod.name} does not define an __all__ attribute."
            " Generating documentation from all members of the module."
            " Define __all__ in your package's __init__.py to specify exactly which"
            " functions it exports (and should be documented).\n"
        )

    contents: list[SpecObject] = []
    for name, member in mod.members.items():
        external_alias = _is_external_alias(member, mod)
        if (
            external_alias
            or member.is_module
            or name.startswith("__")
            or (has_all and not member.is_exported)
        ):
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
    """Recursively convert a spec node tree to a plain-dict representation, suitable for YAML"""
    if isinstance(el, Walkable):
        return {
            k: _to_simple_dict(v)
            for k, v in el._iter_fields()  # pyright: ignore[reportPrivateUsage]
        }
    if isinstance(el, (list, tuple)):
        return [_to_simple_dict(item) for item in el]  # type: ignore[var-annotated]
    if isinstance(el, Enum):
        return el.value
    return el


def _non_default_entries(el: SpecOptions) -> dict[str, Any]:
    """Fields of a `SpecOptions` element that were explicitly set by the caller"""
    fields = el._fields_specified  # pyright: ignore[reportPrivateUsage]
    return {k: getattr(el, k) for k in fields}


def _join_path(pkg: str | None, name: str) -> str:
    """The griffe lookup path for `name` under `pkg`

    A lookup path carries at most one `:` (separating the module from the
    object within it), so once either part already has one, the remaining
    components join with `.`.
    """
    if pkg is None:
        return name
    if ":" in pkg or ":" in name:
        return f"{pkg}.{name}"
    return f"{pkg}:{name}"


class _Resolver:
    """
    A translator from the `spec` tree to the resolved `content` tree

    Each `SpecObject` is located in griffe and rebuilt as a concrete
    `Doc`; sections and their entries become their `content` counterparts.
    Package, options, and dynamic-mode settings are inherited from a section
    by the objects nested under it.
    """

    def __init__(
        self,
        get_object: _GetObject | None = None,
        parser: str = "numpy",
    ) -> None:
        if get_object is None:
            from .introspect import get_object as _get_object
            from .introspect import make_loader

            loader = make_loader(parser)
            self.get_object: _GetObject = cast("_GetObject", partial(_get_object, loader=loader))
        else:
            self.get_object = get_object

        self.current_package: str | None = None
        self.options: SpecOptions | None = None
        self.dynamic: bool = False

    def get_object_or_raise(self, path: str, **kwargs: object) -> gf.Object | gf.Alias:
        """Get the griffe object at `path`, raising `ObjectNotFoundError` if absent"""
        try:
            return self.get_object(path, **kwargs)
        except KeyError as e:
            key_name = e.args[0]
            raise ObjectNotFoundError(
                f"Cannot find an object named: {key_name}."
                f" Does an object with the path {path} exist?"
            )

    @staticmethod
    def _clean_member_path(new: str) -> str:
        if ":" in new:
            return new.replace(":", ".")
        return new

    def resolve_sections(self, sections: list[SpecSection]) -> list[Section]:
        """Resolve the `spec` sections into `content.Section`s"""
        return [self._resolve_section(s) for s in sections]

    @contextmanager
    def _scoped(
        self,
        *,
        package: str | MissingType | None = MISSING,
        options: SpecOptions | None = None,
    ) -> Iterator[None]:
        """Scope entries to resolve under the given package and options

        Entries inherit `current_package` and `options` from the enclosing
        context unless the section or object carries its own.
        """
        old_package = self.current_package
        old_options = self.options

        if package is not MISSING:
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
            contents: list[Any] = [self._resolve_entry(entry) for entry in el.contents]

        return Section(
            kind=el.kind,
            title=el.title,
            subtitle=el.subtitle,
            desc=el.desc,
            contents=contents,
        )

    def _resolve_entry(self, el: SpecEntry) -> Page | Text:
        """
        Rebuild a single section entry as its resolved `content` counterpart

        A documented object becomes its own single-object `Page`; a free-text
        block stays inline as a `Text`.
        """
        if isinstance(el, SpecObject):
            doc = self._resolve_object(el)
            return Page(contents=cast("list[Any]", [doc]), path=doc.name)
        if isinstance(el, SpecText):
            return self._resolve_text(el)
        raise TypeError(f"Cannot resolve section entry of type: {type(el)}")

    def _resolve_text(self, el: SpecText) -> Text:
        """Rebuild a `spec` free-text block as a `content.Text`"""
        return Text(kind=el.kind, contents=el.contents)

    def _resolve_object(self, el: SpecObject) -> Doc:
        """Locate a `SpecObject` in griffe and rebuild it as a concrete `Doc`"""
        # A member `SpecObject` carries its parent's path as `package`; adopt it
        # so the member's full path is computed relative to the parent.
        with self._scoped(package=el.package):
            return self._resolve_documented_object(el)

    def _resolve_documented_object(self, el: SpecObject) -> Doc:
        """Locate the subject object in griffe and rebuild it with its resolved members"""
        path = _join_path(self.current_package, el.name)

        # Merge inherited section-level options under the entry's own settings.
        if self.options is not None:
            _option_dict = _non_default_entries(self.options)
            _el_dict = _non_default_entries(el)
            el = el.__class__(**{**_option_dict, **_el_dict})

        _log.info(f"Getting object for {path}")

        dynamic = el.dynamic if el.dynamic is not None else self.dynamic

        # The subject object being documented (the class/module/function itself).
        obj = self.get_object_or_raise(path, dynamic=dynamic)
        raw_members = self._fetch_members(el, obj)

        _defaults: dict[str, Any] = {"dynamic": dynamic, "package": path}
        if el.member_options is not None:
            member_options: dict[str, Any] = {
                **_defaults,
                **_non_default_entries(el.member_options),
            }
        else:
            member_options = _defaults

        children: list[object] = []
        for entry in raw_members:
            relative_path = self._clean_member_path(entry)

            member_doc = self._resolve_object(SpecObject(name=relative_path, **member_options))
            # A doc resolved from griffe always carries its object.
            member_obj = member_doc.obj

            if member_obj.kind.value == "module":
                continue

            if el.children == ChildrenStyle.separate:
                res: object = MemberPage(path=member_obj.path, contents=[member_doc])
            elif el.children in {ChildrenStyle.embedded, ChildrenStyle.flat}:
                res = member_doc
            elif el.children == ChildrenStyle.linked:
                res = Link(name=member_obj.path, obj=member_obj)
            else:
                raise ValueError(f"Unsupported value of children: {el.children}")

            children.append(res)

        is_flat = el.children == ChildrenStyle.flat
        return Doc.from_griffe(
            el.name,
            obj,
            children,
            flat=is_flat,
            signature_name=el.signature_name,
        )

    def _fetch_members(self, el: SpecObject, obj: gf.Object | gf.Alias) -> list[str]:
        """Fetch the member paths to document for a given `SpecObject` element and its resolved object"""
        if el.members is not None:
            return el.members

        candidates: dict[str, gf.Object | gf.Alias] = (
            dict(obj.all_members) if el.include_inherited else dict(obj.members)
        )

        # Always filter built-in noise dunders inherited from `object`/`type`
        # (e.g. `__doc__`, `__module__`). These show up on every PyO3 /
        # C-extension class because their docstrings are inherited from str.
        candidates = {k: v for k, v in candidates.items() if k not in _BUILTIN_NOISE_DUNDERS}

        if obj.is_module and obj.exports is not None:
            candidates = {k: v for k, v in candidates.items() if v.is_exported}

        if not el.include_private:
            # Filter out private members (names starting with _), but keep
            # dunder methods that have docstrings — those are intentionally
            # documented (e.g. __enter__, __exit__, __getitem__).
            candidates = {
                k: v
                for k, v in candidates.items()
                if not k.startswith("_")
                or (k.startswith("__") and k.endswith("__") and v.docstring is not None)
            }

        if not el.include_imports and obj.is_module:
            candidates = {k: v for k, v in candidates.items() if not v.is_alias}

        if not el.include_inherited and obj.is_class:
            candidates = {k: v for k, v in candidates.items() if (v.parent is obj or not v.is_alias)}

        for member in candidates.values():
            _ = resolve_alias(member, self.get_object)

        if not el.include_empty:
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


def resolve(
    sections: list[SpecSection],
    *,
    package: str | None = None,
    settings: Settings | None = None,
) -> list[Section]:
    """Resolve the `spec` tree into sections ready for rendering"""

    parser = settings.parser if settings is not None else "numpy"
    dynamic = settings.dynamic if settings is not None else None

    r = _Resolver(parser=parser)

    if package is not None:
        r.current_package = package

    if dynamic is not None:
        r.dynamic = dynamic

    if not sections:
        sections = _autogenerate_sections(r, package)

    return r.resolve_sections(sections)


def _autogenerate_sections(r: _Resolver, package: str | None) -> list[SpecSection]:
    """Introspect default sections from `package`, echoing the equivalent config to stdout"""
    print("Autogenerating contents (since no contents specified in config)")

    assert isinstance(package, str)

    mod = r.get_object_or_raise(package)
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
