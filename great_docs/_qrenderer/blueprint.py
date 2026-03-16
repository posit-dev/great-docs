from __future__ import annotations

import logging
from enum import Enum
from functools import partial
from textwrap import indent

import yaml

from ._base_utils import PydanticTransformer, WorkaroundKeyError, ctx_node
from ._griffe import (
    AliasResolutionError,
    GriffeLoader,
    LinesCollection,
    ModulesCollection,
    Parser,
)
from ._griffe import dataclasses as dc
from ._griffe import docstrings as ds
from .layout import (
    MISSING,
    Auto,
    ChoicesChildren,
    Doc,
    Layout,
    Link,
    MemberPage,
    Page,
    Section,
    _Base,
)
from .parsers import get_parser_defaults

_log = logging.getLogger(__name__)


def _auto_package(mod: dc.Module) -> list[Section]:
    """Create default sections for the given package."""

    has_all = "__all__" in mod.members

    if not has_all:
        print(
            f"\nWARNING: the module {mod.name} does not define an __all__ attribute."
            " Generating documentation from all members of the module."
            " Define __all__ in your package's __init__.py to specify exactly which"
            " functions it exports (and should be documented).\n"
        )

    contents = []
    for name, member in mod.members.items():
        external_alias = _is_external_alias(member, mod)
        if (
            external_alias
            or member.is_module
            or name.startswith("__")
            or (has_all and not member.is_exported)
        ):
            continue

        contents.append(Auto(name=name))

    if mod.docstring and mod.docstring.parsed:
        mod_summary = mod.docstring.parsed[0]
        if isinstance(mod_summary, ds.DocstringSectionText):
            desc = mod_summary.value
        else:
            desc = ""
    else:
        desc = ""

    return [Section(title=mod.path, desc=desc, contents=contents)]


def _is_external_alias(obj: dc.Alias | dc.Object, mod: dc.Module):
    package_name = mod.path.split(".")[0]

    if not isinstance(obj, dc.Alias):
        return False

    crnt_target = obj

    while crnt_target.is_alias:
        if not crnt_target.target_path.startswith(package_name):
            return True

        try:
            new_target = crnt_target.modules_collection[crnt_target.target_path]

            if new_target is crnt_target:
                raise Exception(f"Cyclic Alias: {new_target}")

            crnt_target = new_target

        except KeyError:
            return True

    return False


def _to_simple_dict(el):
    """Recursively convert a dataclass tree to plain dicts/lists for YAML."""
    if isinstance(el, _Base):
        return {k: _to_simple_dict(v) for k, v in el._iter_fields()}
    if isinstance(el, list):
        return [_to_simple_dict(item) for item in el]
    if isinstance(el, tuple):
        return [_to_simple_dict(item) for item in el]
    if isinstance(el, Enum):
        return el.value
    return el


def _non_default_entries(el: Auto):
    return {k: getattr(el, k) for k in el._fields_specified}


def _resolve_alias(obj: dc.Alias | dc.Object, get_object):
    if not isinstance(obj, dc.Alias):
        return obj

    max_tries = 100

    new_obj = obj
    for ii in range(max_tries):
        if not new_obj.is_alias:
            break

        try:
            new_obj = new_obj.target
        except AliasResolutionError as e:
            new_obj = get_object(e.alias.target_path)

    return new_obj


class BlueprintTransformer(PydanticTransformer):
    def __init__(self, get_object=None, parser="numpy"):
        if get_object is None:
            from .introspection import get_object as _get_object

            loader = GriffeLoader(
                docstring_parser=Parser(parser),
                docstring_options=get_parser_defaults(parser),
                modules_collection=ModulesCollection(),
                lines_collection=LinesCollection(),
            )
            self.get_object = partial(_get_object, loader=loader)
        else:
            self.get_object = get_object

        self.crnt_package = None
        self.options = None
        self.dynamic = False

    @staticmethod
    def _append_member_path(path: str, new: str):
        if ":" in path:
            return f"{path}.{new}"
        return f"{path}:{new}"

    def get_object_fixed(self, path, **kwargs):
        try:
            return self.get_object(path, **kwargs)
        except KeyError as e:
            key_name = e.args[0]
            raise WorkaroundKeyError(
                f"Cannot find an object named: {key_name}."
                f" Does an object with the path {path} exist?"
            )

    @staticmethod
    def _clean_member_path(path, new):
        if ":" in new:
            return new.replace(":", ".")
        return new

    def visit(self, el):
        self._log("VISITING", el)

        # set package
        package = getattr(el, "package", MISSING())
        old = self.crnt_package

        if not isinstance(package, MISSING):
            self.crnt_package = package

        # set options
        options = getattr(el, "options", None)
        old_options = self.options

        if options is not None:
            self.options = options

        try:
            return super().visit(el)
        finally:
            self.crnt_package = old
            self.options = old_options

    def enter(self, el):
        # isinstance-based dispatch replacing plum @dispatch
        if isinstance(el, Auto):
            return self._enter_auto(el)
        if isinstance(el, Layout):
            return self._enter_layout(el)
        return super().enter(el)

    def exit(self, el):
        if isinstance(el, Section):
            return self._exit_section(el)
        return super().exit(el)

    def _enter_layout(self, el: Layout):
        if not el.sections:
            print("Autogenerating contents (since no contents specified in config)")

            package = el.package

            mod = self.get_object_fixed(package)
            sections = _auto_package(mod)

            if not sections:
                raise ValueError()

            new_el = el.copy()
            new_el.sections = sections

            print(
                "Use the following configuration to recreate the automatically",
                " generated site:\n\n\n",
                "api-reference:\n",
                indent(yaml.safe_dump(_to_simple_dict(new_el), sort_keys=False), " " * 2),
                "\n",
                sep="",
            )

            return super().enter(new_el)

        return super().enter(el)

    def _exit_section(self, el: Section):
        """Transform top-level sections, so their contents are all Pages."""

        node = ctx_node.get()

        if not isinstance(node.parent.parent.value, Layout):
            return el

        new = el.copy()
        contents = [
            Page(contents=[el], path=el.name) if not isinstance(el, Page) else el
            for el in new.contents
        ]

        new.contents = contents

        return new

    def _enter_auto(self, el: Auto):
        self._log("Entering", el)

        pkg = self.crnt_package
        if pkg is None:
            path = el.name
        elif ":" in pkg or ":" in el.name:
            path = f"{pkg}.{el.name}"
        else:
            path = f"{pkg}:{el.name}"

        # auto default overrides
        if self.options is not None:
            _option_dict = _non_default_entries(self.options)
            _el_dict = _non_default_entries(el)
            el = el.__class__(**{**_option_dict, **_el_dict})

        # fetching object
        _log.info(f"Getting object for {path}")

        dynamic = el.dynamic if el.dynamic is not None else self.dynamic

        obj = self.get_object_fixed(path, dynamic=dynamic)
        raw_members = self._fetch_members(el, obj)

        _defaults = {"dynamic": dynamic, "package": path}
        if el.member_options is not None:
            member_options = {**_defaults, **_non_default_entries(el.member_options)}
        else:
            member_options = _defaults

        children = []
        for entry in raw_members:
            relative_path = self._clean_member_path(path, entry)

            doc = self.visit(Auto(name=relative_path, **member_options))

            if doc.obj.kind.value == "module":
                continue

            if el.children == ChoicesChildren.separate:
                res = MemberPage(path=doc.obj.path, contents=[doc])
            elif el.children in {ChoicesChildren.embedded, ChoicesChildren.flat}:
                res = doc
            elif el.children == ChoicesChildren.linked:
                res = Link(name=doc.obj.path, obj=doc.obj)
            else:
                raise ValueError(f"Unsupported value of children: {el.children}")

            children.append(res)

        is_flat = el.children == ChoicesChildren.flat
        return Doc.from_griffe(
            el.name,
            obj,
            children,
            flat=is_flat,
            signature_name=el.signature_name,
        )

    def _fetch_members(self, el: Auto, obj: dc.Object | dc.Alias):
        if el.members is not None:
            return el.members

        options = obj.all_members if el.include_inherited else obj.members

        if obj.is_module and obj.exports is not None:
            options = {k: v for k, v in options.items() if v.is_exported}

        if not el.include_private:
            # Filter out private members (names starting with _), but keep
            # dunder methods that have docstrings — those are intentionally
            # documented (e.g. __enter__, __exit__, __getitem__).
            options = {
                k: v
                for k, v in options.items()
                if not k.startswith("_")
                or (k.startswith("__") and k.endswith("__") and v.docstring is not None)
            }

        if not el.include_imports and obj.is_module:
            options = {k: v for k, v in options.items() if not v.is_alias}

        if not el.include_inherited and obj.is_class:
            options = {k: v for k, v in options.items() if (v.parent is obj or not v.is_alias)}

        for obj in options.values():
            _resolve_alias(obj, self.get_object)

        if not el.include_empty:
            options = {k: v for k, v in options.items() if v.docstring is not None}

        if not el.include_attributes:
            options = {k: v for k, v in options.items() if not v.is_attribute}

        if not el.include_classes:
            options = {k: v for k, v in options.items() if not v.is_class}

        if not el.include_functions:
            options = {k: v for k, v in options.items() if not v.is_function}

        if el.include:
            raise NotImplementedError("include argument currently unsupported.")

        if el.exclude:
            options = {k: v for k, v in options.items() if k not in el.exclude}

        if el.member_order == "alphabetical":
            return sorted(options)
        elif el.member_order == "source":
            return list(options)
        else:
            raise ValueError(f"Unsupported value of member_order: {el.member_order}")


class _PagePackageStripper(PydanticTransformer):
    def __init__(self, package: str):
        self.package = package

    def exit(self, el):
        if isinstance(el, Page):
            return self._exit_page(el)
        return super().exit(el)

    def _exit_page(self, el: Page):
        parts = el.path.split(".")
        if parts[0] == self.package and len(parts) > 1:
            new_path = ".".join(parts[1:])
            new_el = el.copy()
            new_el.path = new_path
            return new_el
        return el


def blueprint(
    el: _Base, package: str = None, dynamic: "None | bool" = None, parser="numpy"
) -> _Base:
    """Convert a configuration element to something that is ready to render.

    Parameters
    ----------
    el:
        An element, like layout.Auto, to transform.
    package:
        A base package name. If specified, this is prepended to the names of any objects.
    dynamic:
        Whether to dynamically load objects. Defaults to using static analysis.

    """

    trans = BlueprintTransformer(parser=parser)

    if package is not None:
        trans.crnt_package = package

    if dynamic is not None:
        trans.dynamic = dynamic

    return trans.visit(el)


def strip_package_name(el: _Base, package: str):
    """Removes leading package name from layout Pages."""

    stripper = _PagePackageStripper(package)
    return stripper.visit(el)
