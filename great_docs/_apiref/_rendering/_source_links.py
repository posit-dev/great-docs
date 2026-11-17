"""
Links from API documentation to an object's source in the repository

Links follow the repository's layout, whether flat, `src/` or a monorepo with an
explicit source path. Objects that only a stub declares link to the stub, and an
installed stub links to the repository's copy, or not at all when there is none.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import griffe as gf

from great_docs._translations import translate
from great_docs.pandoc.components import Attr
from great_docs.pandoc.inlines import Link

if TYPE_CHECKING:
    from .._settings import SourceLinks


_INSTALL_DIRS = frozenset({"site-packages", "dist-packages"})


def source_link(obj: gf.Object | gf.Alias, links: SourceLinks, lang: str) -> Link | None:
    """
    Build a link to the object's source code

    Returns
    -------
    :
        The source link, or `None` when no repository URL or source path is
        available, the file is a compiled extension, or the starting line
        is unknown.
    """
    if links.repository is None:
        return None
    rel_str = source_relative_path(obj, links)
    if rel_str is None:
        return None
    # Suppress source links for compiled extensions (PyO3, Cython,
    # pybind11, C extensions). The file path points at a binary
    # artifact and `lineno` is None, producing broken `#LNone` anchors.
    if rel_str.endswith((".so", ".pyd", ".dylib", ".abi3.so")):
        return None
    start, end = obj.lineno, obj.endlineno
    if start is None:
        return None
    url = links.repository.file_url(rel_str, links.ref, start, end)
    return Link(
        translate("source", lang),
        url,
        attr=Attr(attributes={"target": "_blank", "rel": "noopener"}),
    )


def source_relative_path(obj: gf.Object | gf.Alias, links: SourceLinks) -> str | None:
    """
    Resolve the object's source path for a repository link

    Griffe's `relative_package_filepath` is relative to the package's parent
    directory, a Griffe search path. For `src/` and other non-flat layouts,
    it drops the leading directory, producing repository URLs that return
    404. Resolve the path in this order to preserve the repository layout:

    1. Honour an explicit `source.path` override for monorepos.
    2. Compute the path relative to the repository root from the object's
       absolute file path, preserving directories such as `src/`.
    3. Fall back to Griffe's package-parent-relative path when the override
       and repository root cannot resolve a path.

    Objects that only a stub declares, such as the classes and functions
    of a PyO3 or other compiled extension, take their line numbers from the
    `.pyi` file but report the module's `.py` file. They link to the stub
    instead. An installed stub, outside the repository, links to the
    repository's copy, and to nothing when there is none.

    Returns
    -------
    :
        The source path, or `None` when no path can be determined.
    """
    # Griffe raises `ValueError` for objects without a parent module, such
    # as synthetic objects. A `getattr` default only handles missing attributes.
    try:
        filepath = obj.filepath
    except (ValueError, AttributeError):
        filepath = None

    # A namespace package can span several directories and has no single
    # source file. Use Griffe's package-relative path in step 3.
    if isinstance(filepath, list):
        filepath = None

    if filepath is not None and Path(filepath).suffix == ".py" and _declared_in_stub(obj):
        stub = Path(filepath).with_suffix(".pyi")
        if stub.is_file():
            filepath = stub
    if filepath is not None and Path(filepath).suffix == ".pyi":
        return stub_relative_path(obj, Path(filepath), links)

    # 1. Explicit override for monorepos: `<source.path>/<filename>`.
    if links.path and filepath is not None:
        return f"{links.path}/{Path(filepath).name}"

    # 2. Path relative to the repository root, preserving the real layout.
    if links.package_root and filepath is not None:
        try:
            rel = Path(filepath).resolve().relative_to(links.package_root.resolve())
            return rel.as_posix()
        except (ValueError, OSError):
            pass

    # 3. Legacy fallback: griffe's package-parent-relative path.
    try:
        return Path(obj.relative_package_filepath).as_posix()
    except (ValueError, AttributeError):
        return None


def stub_relative_path(obj: gf.Object | gf.Alias, stub: Path, links: SourceLinks) -> str | None:
    """
    Resolve a stub file's path for a repository link

    A stub inside the repository keeps its path. An installed stub,
    including one in a virtual environment within the repository, is
    looked up in the repository under its package-relative path, also
    within `src/` and `python/`. A package's `__init__.pyi` is also looked
    up as `<package>.pyi`, where maturin keeps the stub of a Rust-only
    project.

    Parameters
    ----------
    stub
        The absolute path of the stub file.

    Returns
    -------
    :
        The stub's path relative to the repository root, or `None` when the
        repository has no copy of an installed stub.
    """
    if links.path:
        return f"{links.path}/{stub.name}"

    try:
        rel = Path(obj.relative_package_filepath).with_suffix(".pyi")
    except (ValueError, AttributeError):
        rel = None

    if links.package_root is None:
        return rel.as_posix() if rel else None

    root = links.package_root.resolve()
    try:
        inside = stub.resolve().relative_to(root)
    except (ValueError, OSError):
        inside = None
    # A virtual environment within the repository holds installed copies.
    if inside is not None and not _INSTALL_DIRS.intersection(inside.parts):
        return inside.as_posix()

    if rel is None:
        return None
    names = [rel]
    if rel.name == "__init__.pyi" and rel.parent != Path():
        names.append(rel.parent.with_suffix(".pyi"))
    for name in names:
        for candidate in (name, "src" / name, "python" / name):
            if (root / candidate).is_file():
                return candidate.as_posix()
    return None


def _declared_in_stub(obj: gf.Object | gf.Alias) -> bool:
    """
    Whether an object comes from a stub that griffe merged into its module

    Griffe marks the objects a stub adds to a module as not available at
    runtime, so an object declared in a stub, or a member of a class that
    is, reports the `.py` module file but has the stub's line numbers.
    Objects inside `if TYPE_CHECKING:` are also marked, so callers check that
    the stub file exists.
    """
    current: gf.Object | None
    try:
        current = obj.final_target if isinstance(obj, gf.Alias) else obj
    except (gf.AliasResolutionError, gf.CyclicAliasError):
        return False
    while current is not None and not getattr(current, "is_module", True):
        if getattr(current, "runtime", True) is False:
            return True
        current = getattr(current, "parent", None)
    return False
