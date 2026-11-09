"""
Export discovery and categorisation for the generated API reference

Every function reads a package that griffe has already loaded, so none of them imports the
package. A caller that needs to know whether the renderer can document a path passes that check
in.
"""

from __future__ import annotations

import ast
import importlib.metadata
from typing import TYPE_CHECKING, Literal, TypedDict, cast

import griffe as gf

from .._apiref._exports import declared_exports
from .._apiref._type_checks import ClassKind, attribute_kind, class_kind, function_kind
from .._apiref.introspect import get_object
from .._build.steps import BuildError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator
    from pathlib import Path

    from ..config import Config

AUTO_EXCLUDE = frozenset(
    {
        # CLI and entry points
        "main",
        "cli",
        # Version and metadata
        "version",
        "VERSION",
        "VERSION_INFO",
        # Common module re-exports
        "core",
        "utils",
        "helpers",
        "constants",
        "config",
        "settings",
        # Standard library re-exports
        "PackageNotFoundError",
        "typing",
        "annotations",
        "TYPE_CHECKING",
        # Logging
        "logger",
        "log",
        "logging",
    }
)
"""Names that discovery drops unless `auto_include` or `no_auto_exclude` keeps them"""

METADATA_NAMES = frozenset({"__version__", "__author__", "__email__", "__all__"})
"""Module metadata that no reference section lists"""

ClassGroup = Literal[
    "classes",
    "dataclasses",
    "enums",
    "exceptions",
    "namedtuples",
    "typeddicts",
    "protocols",
    "abstract_classes",
]

_CLASS_GROUPS: dict[ClassKind, ClassGroup] = {
    "dataclass": "dataclasses",
    "enum": "enums",
    "exception": "exceptions",
    "namedtuple": "namedtuples",
    "typeddict": "typeddicts",
    "protocol": "protocols",
    "abc": "abstract_classes",
    "class": "classes",
}

# Constructor dunders are left out of a class's methods: the class signature already shows
# their parameters.
_CONSTRUCTOR_DUNDERS = frozenset({"__init__", "__new__", "__init_subclass__"})

_ALIAS_ERRORS = (gf.CyclicAliasError, gf.AliasResolutionError)


class Categories(TypedDict):
    """
    A package's exports sorted into the groups of the API reference

    Each group lists names as the reference refers to them: `Widget` for an export, and
    `models.Model` for a member of an exported module.
    """

    classes: list[str]
    dataclasses: list[str]
    enums: list[str]
    exceptions: list[str]
    namedtuples: list[str]
    typeddicts: list[str]
    protocols: list[str]
    abstract_classes: list[str]
    functions: list[str]
    async_functions: list[str]
    constants: list[str]
    type_aliases: list[str]
    other: list[str]
    class_methods: dict[str, int]
    """The number of documentable methods of each class"""
    class_method_names: dict[str, list[str]]
    """The documentable methods of each class, in source order"""
    cyclic_alias_count: int
    """The number of exports left out because their aliases form a cycle"""


def empty_categories() -> Categories:
    """
    Create categories with every group empty

    Returns
    -------
    :
        New categories that share no lists with any others.
    """
    return {
        "classes": [],
        "dataclasses": [],
        "enums": [],
        "exceptions": [],
        "namedtuples": [],
        "typeddicts": [],
        "protocols": [],
        "abstract_classes": [],
        "functions": [],
        "async_functions": [],
        "constants": [],
        "type_aliases": [],
        "other": [],
        "class_methods": {},
        "class_method_names": {},
        "cyclic_alias_count": 0,
    }


def parse_dunder_all(
    init_file: Path, config: Config, *, report: Callable[[str], None]
) -> list[str] | None:
    """
    Read export names from a package's `__init__.py` without executing it

    Read module-scope assignments to `__all__` in source order, including annotated assignments
    and `+=` extensions. Traverse compound statements such as `if` and `try` without evaluating
    conditions or entering function or class bodies.

    Collect string literals from list and tuple literals, including those joined with `+`.
    Ignore non-string elements and dynamic operands, such as names, attributes, calls and
    comprehensions. A wholly dynamic value leaves the previously collected names unchanged.

    Apply automatic and configured exclusions, with `auto_include` and `no_auto_exclude`
    controlling the automatic exclusions.

    Parameters
    ----------
    init_file
        The package's `__init__.py`.
    config
        The configuration whose `exclude`, `auto_include` and `no_auto_exclude` settings apply.
    report
        A callback that receives progress lines and the reason for a failure.

    Returns
    -------
    :
        The remaining names in `__all__` order. Return `None` if the file cannot be read or
        parsed, or no names are collected before exclusions. Return an empty list if
        exclusions remove every collected name.
    """
    try:
        tree = ast.parse(init_file.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError) as error:
        # `ValueError` covers undecodable bytes and, before Python 3.12, a null byte.
        report(f"Error parsing __all__: {type(error).__name__}: {error}")
        return None

    exports: list[str] | None = None
    for node in _module_statements(tree):
        if isinstance(node, ast.Assign) and any(map(_is_dunder_all, node.targets)):
            names = _literal_names(node.value)
        elif isinstance(node, ast.AnnAssign) and _is_dunder_all(node.target) and node.value:
            names = _literal_names(node.value)
        elif (
            isinstance(node, ast.AugAssign)
            and isinstance(node.op, ast.Add)
            and _is_dunder_all(node.target)
        ):
            names = _literal_names(node.value)
            if names is not None:
                names = [*(exports or []), *names]
        else:
            continue
        if names is not None:
            exports = names

    if not exports:
        report("No __all__ definition found in __init__.py")
        return None

    report(f"Successfully parsed __all__ with {len(exports)} exports")
    return _drop_excluded(exports, config, report=report)


def _module_statements(node: ast.AST) -> Iterator[ast.stmt]:
    """
    Yield module-scope statements without entering function or class bodies

    Traverse compound statements such as `if` and `try` in source order without evaluating
    their conditions.

    Parameters
    ----------
    node
        The parsed module, or a node within it.

    Yields
    ------
    :
        Each statement, including function and class definitions but excluding their bodies.
    """
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.stmt):
            yield child
        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield from _module_statements(child)


def _is_dunder_all(target: ast.expr) -> bool:
    """
    Check whether an assignment target is the name `__all__`

    Parameters
    ----------
    target
        The target of an assignment.

    Returns
    -------
    :
        Whether the target is `__all__`.
    """
    return isinstance(target, ast.Name) and target.id == "__all__"


def _literal_names(value: ast.expr) -> list[str] | None:
    """
    Collect string literals from lists, tuples and `+` expressions

    Ignore non-string elements of list and tuple literals and dynamic operands of `+`.

    Parameters
    ----------
    value
        The value assigned to `__all__`.

    Returns
    -------
    :
        The collected strings in source order. An empty list or tuple literal yields an empty
        list. Return `None` if no list or tuple literal is recognised.
    """
    if isinstance(value, (ast.List, ast.Tuple)):
        return [
            element.value
            for element in value.elts
            if isinstance(element, ast.Constant) and isinstance(element.value, str)
        ]
    if isinstance(value, ast.BinOp) and isinstance(value.op, ast.Add):
        left = _literal_names(value.left)
        right = _literal_names(value.right)
        if left is None and right is None:
            return None
        return [*(left or []), *(right or [])]
    return None


def _drop_excluded(names: list[str], config: Config, *, report: Callable[[str], None]) -> list[str]:
    """
    Remove exported names covered by automatic or configured exclusions

    Apply automatic exclusions unless `auto_include` keeps individual names or
    `no_auto_exclude` disables them all. Always remove names in `exclude`, even if they also
    appear in `auto_include`.

    Parameters
    ----------
    names
        The exported names.
    config
        The configuration whose `exclude`, `auto_include` and `no_auto_exclude` settings apply.
    report
        A callback that receives exclusion settings and groups of excluded or included names.

    Returns
    -------
    :
        The remaining names, in their original order.
    """
    exclude = set(config.exclude)
    auto_include = set(config.auto_include)
    if config.no_auto_exclude:
        auto_exclude: frozenset[str] = frozenset()
        report("Auto-exclude list bypassed (no_auto_exclude: true)")
    else:
        auto_exclude = AUTO_EXCLUDE - auto_include
        forced = auto_include & AUTO_EXCLUDE
        if forced:
            report(
                f"Force-including {len(forced)} auto-excluded name(s): {', '.join(sorted(forced))}"
            )

    auto_excluded = [name for name in names if name in auto_exclude]
    if auto_excluded:
        report(f"Auto-excluding {len(auto_excluded)} item(s): {', '.join(sorted(auto_excluded))}")
    user_excluded = [name for name in names if name in exclude and name not in auto_exclude]
    if user_excluded:
        report(
            f"Filtered out {len(user_excluded)} item(s) from great-docs.yml exclude: "
            f"{', '.join(sorted(user_excluded))}"
        )
    return [name for name in names if name not in auto_exclude and name not in exclude]


def discover_exports(
    package: gf.Module, config: Config, *, report: Callable[[str], None]
) -> list[str] | None:
    """
    Find the names a package exports that the reference can document

    Use a package's statically resolved `__all__` when available. Otherwise, consider its
    public members. If the package has no `__all__` and at least one public submodule declares
    exports, omit sibling submodules without `__all__`. An imported `__all__` uses the defining
    module's exports. Unresolved expressions in `__all__` are omitted; when no names can be
    resolved, discovery falls back to public members. The names in `AUTO_EXCLUDE`
    and in the `exclude` setting are dropped. `auto_include` keeps names from
    `AUTO_EXCLUDE`, and `no_auto_exclude` keeps them all. Aliases that cannot be resolved,
    and aliases to objects outside the package, are dropped too, as is a name in
    `__all__` that the package does not define statically, such as one a module
    `__getattr__` provides.

    Parameters
    ----------
    package
        The loaded package.
    config
        The configuration whose `exclude`, `auto_include` and `no_auto_exclude` settings apply.
    report
        A callback that receives a line for each group of dropped names.

    Returns
    -------
    :
        The exported names in `__all__` order, or in the order the package defines them
        when no export names can be resolved. `None` if `__all__` lists only names the
        package does not define.
    """
    members = package.members
    declared = declared_exports(package)
    if declared is not None:
        candidates = declared
        report(f"Using __all__ with {len(candidates)} exports")
        if candidates and not any(name in members for name in candidates):
            return None
    else:
        candidates = [name for name in members if not name.startswith("_")]
        if package.exports is None and "__all__" not in members:
            submodules: dict[str, bool] = {}
            for name in candidates:
                member = members[name]
                try:
                    if member.kind is gf.Kind.MODULE:
                        submodules[name] = member.exports is not None or "__all__" in member.members
                except (gf.CyclicAliasError, gf.AliasResolutionError, KeyError):
                    continue
            if any(submodules.values()):
                skipped = {name for name, declares in submodules.items() if not declares}
                candidates = [name for name in candidates if name not in skipped]
                if skipped:
                    report(
                        f"Skipping {len(skipped)} submodule(s) without __all__: "
                        f"{', '.join(sorted(skipped))}"
                    )
        report(f"Discovered {len(candidates)} public names")

    exports: list[str] = []
    dropped: dict[str, list[str]] = {}
    for name in _drop_excluded(candidates, config, report=report):
        member = members.get(name)
        if member is None:
            reason = "not found by static analysis"
        else:
            reason = _undocumentable_reason(package, member)
        if reason is None:
            exports.append(name)
        else:
            dropped.setdefault(reason, []).append(name)

    for reason, names in sorted(dropped.items()):
        report(f"Excluding {len(names)} object(s) ({reason}): {', '.join(sorted(names))}")
    return exports


def _undocumentable_reason(package: gf.Module, obj: gf.Object | gf.Alias) -> str | None:
    """
    Explain why the reference cannot document a package member

    Parameters
    ----------
    package
        The package the member belongs to.
    obj
        The member.

    Returns
    -------
    :
        The reason, or `None` if the reference can document the member.
    """
    try:
        if obj.kind is gf.Kind.MODULE:
            return None
        _ = obj.members
    except gf.CyclicAliasError:
        return "cyclic alias"
    except gf.AliasResolutionError:
        return "unresolvable alias"
    except KeyError:
        # griffe has no static model of a compiled (Rust or PyO3) member.
        return "not found (likely Rust/PyO3)"
    if isinstance(obj, gf.Alias) and not obj.canonical_path.startswith(package.path + "."):
        return "external re-export"
    return None


def categorise_exports(
    package: gf.Module,
    exports: Iterable[str],
    *,
    renderable: Callable[[str], bool],
    report: Callable[[str], None],
) -> Categories:
    """
    Sort a package's exports into the groups of the API reference

    Classes are grouped by kind, functions by whether they are asynchronous, and attributes by
    whether they declare a type alias or type variable. An exported module contributes names in
    its `__all__`, or its public members when `__all__` is absent, under qualified names. Members
    the package exports itself are left out. A module with none goes under `other`, as does a
    name the package does not define. Metadata names such as `__version__` are dropped, as are
    aliases that form a cycle or cannot be resolved.

    For each class, the result also lists its public methods and documented dunder methods in
    source order. A method, or a member of an exported module, stays only if the renderer can
    document it; for a module member, finding it by static analysis is enough.

    Parameters
    ----------
    package
        The loaded package.
    exports
        The names to sort.
    renderable
        A check whether the renderer can document an object, given its path in the form
        `package:Class.method`.
    report
        A callback that receives a line for each class and for each name left out.

    Returns
    -------
    :
        The sorted exports.
    """
    exports = list(exports)
    exported = set(exports)
    categories = empty_categories()
    unresolved: list[str] = []
    cyclic: list[str] = []

    for name in exports:
        if name in METADATA_NAMES:
            continue
        if name not in package.members:
            categories["other"].append(name)
            unresolved.append(name)
            continue
        try:
            _categorise_export(
                package, name, exported, categories, renderable=renderable, report=report
            )
        except gf.CyclicAliasError:
            report(f"  Warning: Cyclic alias detected for '{name}', excluding from docs")
            cyclic.append(name)
        except gf.AliasResolutionError:
            report(f"  Warning: Could not resolve alias for '{name}', excluding from docs")
            unresolved.append(name)

    if cyclic:
        report(f"Note: Excluded {len(cyclic)} cyclic alias(es) from documentation")
        categories["cyclic_alias_count"] = len(cyclic)
    if unresolved:
        report(f"Note: Could not introspect {len(unresolved)} item(s), categorizing as 'Other'")
    return categories


def _categorise_export(
    package: gf.Module,
    name: str,
    exported: set[str],
    categories: Categories,
    *,
    renderable: Callable[[str], bool],
    report: Callable[[str], None],
) -> None:
    """
    Add one export to the categories

    Parameters
    ----------
    package
        The loaded package.
    name
        The export, which the package defines.
    exported
        All the package's exports, whose names an exported module does not repeat.
    categories
        The categories to add to.
    renderable
        A check whether the renderer can document an object, given its path.
    report
        A callback that receives the line describing a class.
    """
    obj = package.members[name]
    kind = obj.kind
    if kind is gf.Kind.CLASS:
        categories[_class_group(obj)].append(name)
        methods, skipped = _exported_class_methods(package, name, obj, renderable)
        if skipped:
            shown = ", ".join(skipped[:3]) + ("..." if len(skipped) > 3 else "")
            report(
                f"{name}: class with {len(methods)} public methods "
                f"(skipped {len(skipped)} undocumentable method(s): {shown})"
            )
        else:
            report(f"{name}: class with {len(methods)} public methods")
        categories["class_methods"][name] = len(methods)
        categories["class_method_names"][name] = methods
    elif kind is gf.Kind.MODULE:
        if not _categorise_module(package, name, obj, exported, categories, renderable, report):
            categories["other"].append(name)
    else:
        _add_flat(name, obj, categories)


def _categorise_module(
    package: gf.Module,
    name: str,
    module: gf.Object | gf.Alias,
    exported: set[str],
    categories: Categories,
    renderable: Callable[[str], bool],
    report: Callable[[str], None],
) -> bool:
    """
    Add an exported module's declared exports or public members under qualified names

    Parameters
    ----------
    package
        The loaded package.
    name
        The module's export name.
    module
        The module.
    exported
        All the package's exports; a member with one of these names is left out.
    categories
        The categories to add to.
    renderable
        A check whether the renderer can document an object, given its path.
    report
        A callback that receives the line describing each class.

    Returns
    -------
    :
        Whether the module contributed any member.
    """
    contributed = False
    try:
        members = _module_export_members(module)
    except _ALIAS_ERRORS:
        return False

    for member_name, member in members:
        if member_name in exported:
            continue
        try:
            kind = member.kind
        except _ALIAS_ERRORS:
            continue
        qualified = f"{name}.{member_name}"
        path = f"{package.path}:{qualified}"
        if not renderable(path) and not _found_statically(path):
            continue

        if kind is gf.Kind.CLASS:
            categories[_class_group(member)].append(qualified)
            methods = _module_class_methods(package, qualified, member, renderable)
            categories["class_methods"][qualified] = len(methods)
            categories["class_method_names"][qualified] = methods
            report(f"{qualified}: class with {len(methods)} public methods")
            contributed = True
        elif kind is gf.Kind.FUNCTION or kind in (gf.Kind.ATTRIBUTE, gf.Kind.TYPE_ALIAS):
            _add_flat(qualified, member, categories)
            contributed = True
    return contributed


def _module_export_members(module: gf.Object | gf.Alias) -> list[tuple[str, gf.Object | gf.Alias]]:
    """
    List a module's exported members, or its public members without `__all__`

    A defined but empty `__all__` exports no members. An undefined name in `__all__` cannot be
    documented and is omitted.

    Parameters
    ----------
    module
        The module whose members are listed.

    Returns
    -------
    :
        Members in `__all__` order, or in the module's definition order when no export
        names can be resolved.
    """
    members = module.members
    exports = declared_exports(module)
    if exports is None:
        return [(name, member) for name, member in members.items() if not name.startswith("_")]
    return [(name, members[name]) for name in exports if name in members]


def _add_flat(name: str, obj: gf.Object | gf.Alias, categories: Categories) -> None:
    """
    Add a function, attribute or other non-class object to the categories

    Parameters
    ----------
    name
        The name the reference lists the object under.
    obj
        The object.
    categories
        The categories to add to.
    """
    kind = obj.kind
    if kind is gf.Kind.FUNCTION:
        is_async = function_kind(cast("gf.Function | gf.Alias", obj)) == "async"
        categories["async_functions" if is_async else "functions"].append(name)
    elif kind in (gf.Kind.ATTRIBUTE, gf.Kind.TYPE_ALIAS):
        sub = attribute_kind(cast("gf.Attribute | gf.TypeAlias | gf.Alias", obj))
        is_type = sub in ("typealias", "typevar")
        categories["type_aliases" if is_type else "constants"].append(name)
    else:
        categories["other"].append(name)


def _class_group(obj: gf.Object | gf.Alias) -> ClassGroup:
    """
    Choose the reference group for a class

    Parameters
    ----------
    obj
        A class, or an alias to one.

    Returns
    -------
    :
        The group the class's kind belongs to.
    """
    return _CLASS_GROUPS[class_kind(cast("gf.Class | gf.Alias", obj))]


def _exported_class_methods(
    package: gf.Module,
    name: str,
    cls: gf.Object | gf.Alias,
    renderable: Callable[[str], bool],
) -> tuple[list[str], list[str]]:
    """
    List the documentable methods of an exported class

    Public methods count, and so do dunder methods other than the constructor's.

    Parameters
    ----------
    package
        The loaded package.
    name
        The class's export name.
    cls
        The class.
    renderable
        A check whether the renderer can document a method, given its path.

    Returns
    -------
    :
        The methods in source order, and the methods left out because their aliases cannot
        be resolved or the renderer cannot document them. `<members>` stands for all of them
        when the class's members cannot be read.
    """
    found: list[tuple[str, float]] = []
    skipped: list[str] = []
    try:
        members = list(cls.members.items())
    except _ALIAS_ERRORS:
        return [], ["<members>"]

    for member_name, member in members:
        is_dunder = member_name.startswith("__") and member_name.endswith("__")
        if member_name in _CONSTRUCTOR_DUNDERS or (member_name.startswith("_") and not is_dunder):
            continue
        try:
            is_function = member.kind is gf.Kind.FUNCTION
        except _ALIAS_ERRORS:
            skipped.append(member_name)
            continue
        if not is_function:
            continue
        if renderable(f"{package.path}:{name}.{member_name}"):
            found.append((member_name, _line_number(member)))
        else:
            skipped.append(member_name)
    return _in_source_order(found), skipped


def _module_class_methods(
    package: gf.Module,
    qualified: str,
    cls: gf.Object | gf.Alias,
    renderable: Callable[[str], bool],
) -> list[str]:
    """
    List the documentable public methods of a class in an exported module

    Parameters
    ----------
    package
        The loaded package.
    qualified
        The class's name qualified by its module's export name.
    cls
        The class.
    renderable
        A check whether the renderer can document a method, given its path. A method that
        fails it stays if static analysis finds it.

    Returns
    -------
    :
        The methods in source order.
    """
    found: list[tuple[str, float]] = []
    try:
        members = list(cls.members.items())
    except _ALIAS_ERRORS:
        return []

    for member_name, member in members:
        if member_name.startswith("_"):
            continue
        try:
            is_function = member.kind is gf.Kind.FUNCTION
        except _ALIAS_ERRORS:
            continue
        path = f"{package.path}:{qualified}.{member_name}"
        if is_function and (renderable(path) or _found_statically(path)):
            found.append((member_name, _line_number(member)))
    return _in_source_order(found)


def _line_number(obj: gf.Object | gf.Alias) -> float:
    """
    Find where an object starts in its source file

    Parameters
    ----------
    obj
        The object.

    Returns
    -------
    :
        The line number, or infinity for an object griffe inspected at runtime, which has none.
    """
    return obj.lineno if obj.lineno is not None else float("inf")


def _in_source_order(entries: Iterable[tuple[str, float]]) -> list[str]:
    """
    Order named entries by their line numbers

    Parameters
    ----------
    entries
        Names with their line numbers.

    Returns
    -------
    :
        The names, earliest line first; names on the same line keep their order.
    """
    return [name for name, _ in sorted(entries, key=lambda entry: entry[1])]


def _found_statically(path: str) -> bool:
    """
    Check whether griffe's static analysis finds an object

    Parameters
    ----------
    path
        The object's path, in the form `package:Class.method`.

    Returns
    -------
    :
        Whether a fresh static load of the package models the object.
    """
    try:
        _ = get_object(path, parser="numpy").kind
    except (KeyError, gf.GriffeError, ImportError):
        return False
    return True


def categorise_references(
    package: gf.Module,
    reference: Iterable[object],
) -> Categories:
    """
    Sort the names a `reference:` setting lists into the groups of the API reference

    Only the listed objects are classified: `Class.method` counts as `Class`, and a listed
    module contributes names in its `__all__`, or public members when `__all__` is absent,
    under qualified names. A class's method count
    includes its properties, and no method is checked with the renderer.

    Parameters
    ----------
    package
        The loaded package.
    reference
        The sections of the `reference:` setting. Items other than mappings are ignored.

    Returns
    -------
    :
        The sorted names. A listed name the package does not define goes under `other` when
        the package is not installed.

    Raises
    ------
    BuildError
        When the package is installed and does not define a listed name.
    """
    listed: set[str] = set()
    for section in reference:
        if not isinstance(section, dict):
            continue
        contents = cast("dict[str, object]", section).get("contents", [])
        for item in cast("list[object]", contents):
            if isinstance(item, str):
                listed.add(item)
            elif isinstance(item, dict):
                item_name = cast("dict[str, object]", item).get("name", "")
                if isinstance(item_name, str) and item_name:
                    listed.add(item_name)

    categories = empty_categories()
    missing: list[str] = []
    for name in sorted({name.split(".", 1)[0] for name in listed}):
        if name not in package.members:
            missing.append(name)
            continue
        obj = package.members[name]
        try:
            kind = obj.kind
        except _ALIAS_ERRORS:
            categories["other"].append(name)
            continue

        if kind is gf.Kind.CLASS:
            categories[_class_group(obj)].append(name)
            methods = _referenced_class_methods(obj)
            categories["class_methods"][name] = len(methods)
            if methods:
                categories["class_method_names"][name] = methods
        elif kind is gf.Kind.MODULE:
            _add_module_members(name, obj, categories)
        else:
            _add_flat(name, obj, categories)

    if missing:
        package_version = _installed_version(package.path)
        if package_version is None:
            # Without an installed distribution the names may be about to exist, as when a
            # package documents itself during development.
            categories["other"].extend(missing)
        else:
            items = ", ".join(f"`{name}`" for name in missing)
            raise BuildError(
                f"Configured reference item(s) not found in "
                f"`{package.path}` v{package_version}: {items}\n"
                f"Check that the correct version of `{package.path}` is installed "
                f"and that these names exist in the package's public API."
            )
    return categories


def _installed_version(distribution: str) -> str | None:
    """
    Look up the installed version of a distribution

    Parameters
    ----------
    distribution
        The distribution's name.

    Returns
    -------
    :
        The version, or `None` if the distribution is not installed.
    """
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def _referenced_class_methods(cls: gf.Object | gf.Alias) -> list[str]:
    """
    List the public methods and properties of a class that a `reference:` setting lists

    Parameters
    ----------
    cls
        The class.

    Returns
    -------
    :
        The names in the order griffe lists the members.
    """
    methods: list[str] = []
    try:
        members = list(cls.members.items())
    except _ALIAS_ERRORS:
        return methods

    for member_name, member in members:
        is_dunder = member_name.startswith("__") and member_name.endswith("__")
        if member_name in _CONSTRUCTOR_DUNDERS or (member_name.startswith("_") and not is_dunder):
            continue
        try:
            kind = member.kind
        except _ALIAS_ERRORS:
            continue
        # A dataclass field is an attribute too, so only properties count.
        if kind is gf.Kind.FUNCTION or (kind is gf.Kind.ATTRIBUTE and "property" in member.labels):
            methods.append(member_name)
    return methods


def _add_module_members(name: str, module: gf.Object | gf.Alias, categories: Categories) -> None:
    """
    Add a listed module's declared exports or public members under qualified names

    Classes are grouped by kind; every function is a plain function and every attribute a
    constant.

    Parameters
    ----------
    name
        The module's name in the `reference:` setting.
    module
        The module.
    categories
        The categories to add to.
    """
    try:
        members = _module_export_members(module)
    except _ALIAS_ERRORS:
        return

    for member_name, member in members:
        try:
            kind = member.kind
        except _ALIAS_ERRORS:
            continue
        qualified = f"{name}.{member_name}"
        if kind is gf.Kind.CLASS:
            categories[_class_group(member)].append(qualified)
        elif kind is gf.Kind.FUNCTION:
            categories["functions"].append(qualified)
        elif kind in (gf.Kind.ATTRIBUTE, gf.Kind.TYPE_ALIAS):
            categories["constants"].append(qualified)
