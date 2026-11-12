"""
List the symbols a project's API reference documents without building the site
"""

from __future__ import annotations

import contextlib
import io
import sys
from collections.abc import Callable, Generator, Iterable
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any

from .._apiref.api_reference import APIReference
from .._apiref.resolve import ObjectNotFoundError

if TYPE_CHECKING:
    from .._apiref.inventory import InventoryItem
    from ..config import Config

CreateSections = Callable[[str], "list[Any] | None"]


def symbol_names(
    config: Config,
    *,
    importable_name: str,
    search_paths: Iterable[str | Path],
    create_sections: CreateSections,
) -> list[str]:
    """
    List the dotted page stems of the documented API

    Each stem names one published reference page: a top-level class or
    function, a submodule-qualified class (`scores.CosineScore`), or a method
    (`scores.CosineScore.fit`). The stems match the rendered reference, so
    versioned snapshots and the live build describe the same API surface.

    Parameters
    ----------
    config
        The documentation configuration.
    importable_name
        The package's import name, which may differ from its project name.
    search_paths
        Directories to add to `sys.path` before resolving the package.
    create_sections
        Callable that builds the reference sections for an importable name,
        as the site build does.

    Returns
    -------
    :
        Dotted stems, deduplicated and in first-occurrence order. Empty when the
        site has no API reference, the package documents nothing, or the package
        cannot be resolved.

    Raises
    ------
    BuildError
        If the configured reference names an object the installed package lacks.
    """
    with _resolved_reference(
        config,
        importable_name=importable_name,
        search_paths=search_paths,
        create_sections=create_sections,
    ) as ref:
        if ref is None:
            return []
        try:
            return ref.documented_symbols
        except (ObjectNotFoundError, ImportError, AttributeError):
            return []


def objects(
    config: Config,
    *,
    importable_name: str,
    search_paths: Iterable[str | Path],
    create_sections: CreateSections,
) -> list[InventoryItem]:
    """
    List the objects the reference publishes, each with its page, claims and docstring

    These inventory items describe exactly the objects the site build indexes.

    Parameters
    ----------
    config
        The documentation configuration.
    importable_name
        The package's import name, which may differ from its project name.
    search_paths
        Directories to add to `sys.path` before resolving the package.
    create_sections
        Callable that builds the reference sections for an importable name,
        as the site build does.

    Returns
    -------
    :
        The documented objects. Empty when the site has no API reference, the
        package documents nothing, or the package cannot be resolved.

    Raises
    ------
    BuildError
        If the configured reference names an object the installed package lacks.
    """
    with _resolved_reference(
        config,
        importable_name=importable_name,
        search_paths=search_paths,
        create_sections=create_sections,
    ) as ref:
        if ref is None:
            return []
        try:
            return ref.items
        except (ObjectNotFoundError, ImportError, AttributeError):
            return []


@contextlib.contextmanager
def _resolved_reference(
    config: Config,
    *,
    importable_name: str,
    search_paths: Iterable[str | Path],
    create_sections: CreateSections,
) -> Generator[APIReference | None]:
    """
    Yield the project's API reference and restore its import state on exit

    The query restores `sys.path` and the package's entries in `sys.modules`.
    It suppresses the section builder's output so callers control diagnostic
    reporting. In `dynamic` mode, reading the reference imports the package.

    Parameters
    ----------
    config
        The documentation configuration.
    importable_name
        The package's import name, which may differ from its project name.
    search_paths
        Directories to add to `sys.path` before resolving the package.
    create_sections
        Callable that builds the reference sections for an importable name,
        as the site build does.

    Yields
    ------
    :
        The reference, or `None` when the package documents nothing or the site
        has no API reference (`reference: false` or a project without a Python
        component).
    """
    # These projects publish no API reference, so their documented set is empty.
    if not config.reference_enabled or not config.is_python_project:
        yield None
        return

    added_paths: list[str] = []
    cached_modules: dict[str, ModuleType] = {}
    modules_evicted = False

    def package_modules() -> list[str]:
        return [
            key
            for key in sys.modules
            if key == importable_name or key.startswith(f"{importable_name}.")
        ]

    try:
        # Griffe resolves the reference through `sys.path`. Add the search paths
        # so it can find uninstalled packages, including `src/` checkouts.
        added_paths = [str(p) for p in search_paths if str(p) not in sys.path]
        sys.path[:0] = added_paths
        # Cached imports can refer to an earlier checkout. Evict the target
        # package's modules so dynamic resolution reads its current code.
        # Imported third-party packages retain their global state.
        cached_modules = {key: sys.modules[key] for key in package_modules()}
        for key in cached_modules:
            del sys.modules[key]
        modules_evicted = True
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            sections = create_sections(importable_name)
            if not sections:
                yield None
                return
            yield APIReference(
                {
                    "api-reference": {
                        "package": importable_name,
                        "sections": sections,
                        "parser": config.parser or "numpy",
                        "dynamic": config.dynamic,
                        "members_on_same_page": config.members_on_same_page,
                        "max_members_on_same_page": config.max_members_on_same_page,
                    }
                }
            )
    finally:
        if modules_evicted:
            for key in package_modules():
                del sys.modules[key]
            sys.modules.update(cached_modules)
        for p in added_paths:
            if p in sys.path:
                sys.path.remove(p)
