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
    Build a repository source link for a Python object or authored alias

    Parameters
    ----------
    obj
        The prepared object whose source location to use.
    links
        The repository, Git ref and source-path settings.
    lang
        The language of the visible link label.

    Returns
    -------
    :
        The source link, or `None` when there is no repository, usable source path or
        starting line. Compiled extension files never get a link.
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
    Resolve an object's source path relative to the repository root

    Griffe's package-relative path drops leading directories such as `src/`, so try
    an explicit `source.path` override for monorepos first, then the path relative to
    the repository root, and only then Griffe's path. Objects that only a merged stub
    declares link to the stub, and an installed stub links to the repository's copy.

    Parameters
    ----------
    obj
        The prepared object or authored alias.
    links
        The repository and source-directory settings.

    Returns
    -------
    :
        The repository path, or `None` when no suitable source location is available.
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
    Resolve a stub file's path relative to the repository root

    A stub inside the repository keeps its path. An installed stub, including one in
    a virtual environment inside the repository, is looked up under its
    package-relative path, also within `src/` and `python/`. A package's
    `__init__.pyi` is also looked up as `<package>.pyi`, where maturin keeps the stub
    of a Rust-only project.

    Parameters
    ----------
    obj
        The prepared object whose package-relative location to use.
    stub
        The absolute path of the stub file.
    links
        The repository and source-directory settings.

    Returns
    -------
    :
        The matching repository path, or `None` when no repository copy is found.
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
    Check whether a definition or its containing class is absent at runtime

    Definitions that a merged stub adds keep the stub's line numbers but may report
    the module's `.py` path. Definitions under `TYPE_CHECKING` are also absent at
    runtime, so a source lookup also requires the stub file to exist.

    Parameters
    ----------
    obj
        The object, or an alias to it.

    Returns
    -------
    :
        Whether the object or a class containing it is absent at runtime. `False` for an
        alias that does not resolve.
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
