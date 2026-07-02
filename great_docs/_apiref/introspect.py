"""
Griffe object access

The located `Object` / `Alias` nodes that model a package's public API — the
source of truth for every documented object's signature and docstring, loaded
and normalized from griffe's static analysis (with an optional dynamic-import
mode).
"""

from __future__ import annotations

import inspect
from types import ModuleType
from typing import cast

import griffe as gf

# Parser defaults ==============================================================

DEFAULT_OPTIONS: dict[str, dict[str, object]] = {}


def get_parser_defaults(name: str) -> dict[str, object]:
    """Get the default parser options registered for the named docstring style.

    Returns an empty dict when no defaults have been registered for `name`.
    """
    return DEFAULT_OPTIONS.get(name, {})


# Docstring loading / parsing =================================================


def get_object(
    path: str,
    parser: str = "numpy",
    load_aliases: bool = True,
    dynamic: bool | str = False,
    loader: gf.GriffeLoader | None = None,
) -> gf.Object | gf.Alias:
    """Get the griffe object at the given import path.

    Parameters
    ----------
    path :
        An import path to the object. This should have the form `path.to.module:object`.
        For example, `my_package:get_object` or `my_package:MyClass.render`.
    parser :
        A docstring parser to use.
    load_aliases :
        For aliases that were imported from other modules, should we load that module?
    dynamic :
        Whether to dynamically import object. Useful if docstring is not hard-coded,
        but was set on object by running python code.
    loader :
        An existing griffe loader to reuse. A fresh loader is created when omitted.
    """
    if loader is None:
        from griffe import DocstringOptions

        raw_defaults = get_parser_defaults(parser)
        docstring_options = cast(DocstringOptions, raw_defaults) if raw_defaults else None
        loader = gf.GriffeLoader(
            docstring_parser=gf.Parser(parser),
            docstring_options=docstring_options,
            modules_collection=gf.ModulesCollection(),
            lines_collection=gf.LinesCollection(),
        )

    try:
        module, object_path = path.split(":", 1)
    except ValueError:
        module, object_path = path, None

    # load the module if it hasn't been already.
    root_mod = module.split(".", 1)[0]
    if root_mod not in loader.modules_collection:
        _ = loader.load(module)

    # griffe uses only periods for the path
    griffe_path = f"{module}.{object_path}" if object_path else module

    # Case 1: dynamic loading
    if dynamic:
        if isinstance(dynamic, str):
            return dynamic_alias(path, target=dynamic, loader=loader)

        return dynamic_alias(path, loader=loader)

    # Case 2: static loading an object
    f_parent = loader.modules_collection[griffe_path.rsplit(".", 1)[0]]
    f_data = loader.modules_collection[griffe_path]

    if isinstance(f_parent, gf.Alias) and isinstance(f_data, (gf.Function, gf.Attribute)):
        f_data = gf.Alias(f_data.name, f_data, parent=f_parent)

    if isinstance(f_data, gf.Alias) and load_aliases:
        target_mod = f_data.target_path.split(".")[0]
        if target_mod != module:
            _ = loader.load(target_mod)

    return f_data


def _resolve_target(obj: gf.Alias) -> gf.Object:
    """Resolve the alias chain to the concrete `Object` at its end.

    Follows `Alias.target` links until a non-alias node is reached.

    Raises
    ------
    ValueError
        When the chain appears to be infinitely recursive (> 100 hops).
    """
    target = obj.target

    count = 0
    while isinstance(target, gf.Alias):
        count += 1
        if count > 100:
            raise ValueError("Attempted to resolve target, but may be infinitely recursing?")

        target = target.target

    return target


def replace_docstring(obj: gf.Object | gf.Alias, f: object = None) -> None:
    """Replace the griffe object's docstring in place with the imported runtime docstring

    Callable attributes (the `method = some_function` pattern) are also
    promoted to functions so they render with a signature.

    Parameters
    ----------
    obj :
        Object whose docstring is replaced.
    f :
        The python object whose docstring to use in the replacement. If not
        specified, then attempt to import obj and use its docstring.
    """
    import importlib

    if isinstance(obj, gf.Alias):
        obj = _resolve_target(obj)

    if isinstance(obj, gf.Class):
        for child_obj in obj.members.values():
            replace_docstring(child_obj)

    if f is None:
        mod = importlib.import_module(obj.module.canonical_path)

        if isinstance(obj.parent, gf.Class):
            # Walk up the parent chain to resolve nested classes
            # e.g., for Node.add_child inside Tree, we need mod.Tree.Node
            parent_chain: list[str] = []
            p: gf.Object | gf.Alias | None = obj.parent
            while isinstance(p, gf.Class):
                parent_chain.append(p.name)
                p = p.parent
            parent_chain.reverse()

            try:
                parent_obj: object = mod
                for attr_name in parent_chain:
                    parent_obj = getattr(parent_obj, attr_name)
            except AttributeError:
                return

            try:
                f = getattr(parent_obj, obj.name)
            except AttributeError:
                return
        else:
            f = getattr(mod, obj.name)

    if getattr(f, "__doc__", None) is None:
        return

    doc: str = f.__doc__  # type: ignore[assignment]

    # Reclassify callable attributes as functions.
    # When a class uses `method = some_function` pattern, griffe sees it as
    # Kind.ATTRIBUTE. If the runtime value is actually a function, promote it
    # to a Function object so it gets proper function-style rendering.
    if (
        isinstance(obj, gf.Attribute)
        and callable(f)
        and hasattr(f, "__code__")
        and obj.parent is not None
    ):
        func_obj = gf.Function(
            name=obj.name,
            lineno=obj.lineno,
            endlineno=obj.endlineno,
            parent=obj.parent,
        )
        # Extract parameters from runtime signature
        try:
            sig = inspect.signature(cast("type", f))
            params: list[gf.Parameter] = []
            _kind_map = {
                inspect.Parameter.POSITIONAL_ONLY: gf.ParameterKind.positional_only,
                inspect.Parameter.POSITIONAL_OR_KEYWORD: gf.ParameterKind.positional_or_keyword,
                inspect.Parameter.VAR_POSITIONAL: gf.ParameterKind.var_positional,
                inspect.Parameter.KEYWORD_ONLY: gf.ParameterKind.keyword_only,
                inspect.Parameter.VAR_KEYWORD: gf.ParameterKind.var_keyword,
            }
            for pname, param in sig.parameters.items():
                kind = _kind_map.get(param.kind, gf.ParameterKind.positional_or_keyword)
                default = (
                    str(param.default) if param.default is not inspect.Parameter.empty else None
                )
                params.append(gf.Parameter(name=pname, kind=kind, default=default))
            func_obj.parameters = gf.Parameters(*params)
        except (ValueError, TypeError):
            pass

        old = obj.docstring
        func_obj.docstring = gf.Docstring(
            value=doc,
            lineno=getattr(old, "lineno", None),
            endlineno=getattr(old, "endlineno", None),
            parent=func_obj,
            parser=getattr(old, "parser", None),
            parser_options=getattr(old, "parser_options", None),
        )
        obj.parent.set_member(obj.name, func_obj)
        return

    old = obj.docstring
    new = gf.Docstring(
        value=doc,
        lineno=getattr(old, "lineno", None),
        endlineno=getattr(old, "endlineno", None),
        parent=getattr(old, "parent", None),
        parser=getattr(old, "parser", None),
        parser_options=getattr(old, "parser_options", None),
    )

    obj.docstring = new


def dynamic_alias(
    path: str,
    target: str | None = None,
    loader: gf.GriffeLoader | None = None,
) -> gf.Object | gf.Alias:
    """Resolve a griffe object for `path` via a dynamic import.

    Parameters
    ----------
    path :
        Full path to the object. E.g. `my_package.get_object`.
    target :
        Optional path to the ultimate alias target. By default, this is
        inferred using the `__module__` attribute of the imported object.
    loader :
        An existing griffe loader to reuse. A fresh loader is created when omitted.
    """
    import importlib

    try:
        mod_name, object_path = path.split(":", 1)
    except ValueError:
        mod_name, object_path = path, None

    mod = importlib.import_module(mod_name)

    attr_name: str = ""
    if object_path is None:
        attr: object = mod
        canonical_path: str | None = mod.__name__

    else:
        splits = object_path.split(".")

        canonical_path = None
        crnt_part: object = mod
        for ii, attr_name in enumerate(splits):
            try:
                _qualname = ".".join(splits[ii:])
                new_canonical_path = _canonical_path(crnt_part, _qualname)
            except AttributeError:
                new_canonical_path = None

            if new_canonical_path is not None:
                canonical_path = new_canonical_path

            try:
                crnt_part = getattr(crnt_part, attr_name)
            except AttributeError:
                if canonical_path:
                    obj = get_object(canonical_path, loader=loader)
                    if _is_valueless(obj):
                        return obj

                raise AttributeError(f"No attribute named `{attr_name}` in the path `{path}`.")

        try:
            _qualname = ""
            new_canonical_path = _canonical_path(crnt_part, _qualname)
        except AttributeError:
            new_canonical_path = None

        if new_canonical_path is not None:
            canonical_path = new_canonical_path

        if canonical_path is None:
            raise ValueError(f"Cannot find canonical path for `{path}`")

        attr = crnt_part

    if target:
        obj = get_object(target, loader=loader)
    else:
        try:
            obj = get_object(canonical_path, loader=loader)
        except (KeyError, ModuleNotFoundError, ImportError):
            # The canonical path computed via `__module__` doesn't refer to a
            # loadable Python module, which is typical for PyO3 classes whose Rust
            # `#[pyclass]` lacks `module = "..."` so `__module__` defaults
            # to `"builtins"`. Fall back to the access path the user actually
            # wrote, which by definition is importable.
            obj = get_object(path, loader=loader)
            canonical_path = path.replace(":", ".")

    replace_docstring(obj, attr)

    if obj.canonical_path == path.replace(":", "."):
        return obj
    else:
        if object_path:
            if "." in object_path:
                prev_member = object_path.rsplit(".", 1)[0]
                parent_path = f"{mod_name}:{prev_member}"
            else:
                parent_path = mod_name
        else:
            parent_path = mod_name.rsplit(".", 1)[0]

        parent = get_object(parent_path, loader=loader, dynamic=True)
        if isinstance(parent, (gf.Module, gf.Class, gf.Alias)):
            return gf.Alias(attr_name, obj, parent=parent)
        return gf.Alias(attr_name, obj)


def _canonical_path(crnt_part: object, qualname: str) -> str | None:
    """Canonical import path for `crnt_part`, extended by `qualname`.

    Returns `None` when no canonical path can be determined (e.g. for
    plain data objects that carry no `__module__` or `__qualname__`).
    """
    suffix = (":" + qualname) if qualname else ""
    if isinstance(crnt_part, ModuleType):
        return crnt_part.__name__ + suffix

    if inspect.isclass(crnt_part) or inspect.isfunction(crnt_part):
        _mod = getattr(crnt_part, "__module__", None)

        if _mod is None:
            return None

        qual_parts = [] if not qualname else qualname.split(".")
        return _mod + ":" + ".".join([crnt_part.__qualname__, *qual_parts])

    # PyO3 / C-extension callables (e.g. `builtin_function_or_method`,
    # `method-wrapper`) don't satisfy `inspect.isfunction` but they do carry
    # `__module__` / `__qualname__` attributes. Treat them as function-like
    # so `dynamic_alias` can resolve them to their canonical home rather than
    # building a self-referential alias on the re-exporting facade module
    # (which produces `CyclicAliasError` downstream).
    _mod = getattr(crnt_part, "__module__", None)
    _qn = getattr(crnt_part, "__qualname__", None)
    if _mod and _qn and callable(crnt_part):
        qual_parts = [] if not qualname else qualname.split(".")
        return _mod + ":" + ".".join([_qn, *qual_parts])

    return None


def _is_valueless(obj: gf.Object | gf.Alias) -> bool:
    """Whether `obj` is an attribute that carries no runtime value.

    True for class/module attributes with no assigned value, and for
    all instance attributes (which are declaration-only in griffe's static
    model).
    """
    if isinstance(obj, gf.Attribute):
        if obj.labels & {"class-attribute", "module-attribute"} and obj.value is None:
            return True
        elif "instance-attribute" in obj.labels:
            return True

    return False
