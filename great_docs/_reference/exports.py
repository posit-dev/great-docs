"""
Discover package exports and build API reference sections
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

import griffe as gf

from .._build.steps import USER_CODE_ERRORS, BuildError
from .._project.model import Project, locate_package_init
from ..config import Config
from . import discovery, probe
from . import sections as reference_sections

if TYPE_CHECKING:
    from .._project.layout import Layout
    from .discovery import Categories

__all__ = ["Exports"]


@dataclass(eq=False)
class Exports:
    """
    Package models and discovered exports for a project's API reference

    Each package is loaded once, and its exports are kept once found. Discovery progress
    goes to standard output and package-loading warnings to standard error.
    """

    config: Config
    """The configuration that selects the exports and the reference sections"""

    project: Project
    """The documented project, whose source directories are searched for packages"""

    _packages: dict[str, gf.Module] = field(default_factory=dict[str, gf.Module], init=False)
    _names: dict[str, list[str]] = field(default_factory=dict[str, list[str]], init=False)

    @classmethod
    def make(cls, layout: Layout) -> Exports:
        """
        Prepare export discovery from a project's configuration and packaging files

        Parameters
        ----------
        layout
            The project's directories.

        Returns
        -------
        :
            An export discovery object with no packages loaded or exports discovered.

        Raises
        ------
        ConfigError
            If the configuration names an unsupported docstring parser.
        """
        config = layout.load_config()
        return cls(config, Project.make(config, layout))

    def package(self, name: str) -> gf.Module:
        """
        Load a package with griffe and reuse it on later calls

        Parameters
        ----------
        name
            The package's importable name. Dashes count as underscores.

        Returns
        -------
        :
            griffe's model of the package.

        Raises
        ------
        ImportError, SyntaxError, AttributeError, RuntimeError, OSError, griffe.GriffeError
            If griffe cannot load the package.
        """
        name = name.replace("-", "_")
        if name not in self._packages:
            # Loading an importable name yields a module, including for dotted names.
            self._packages[name] = cast(
                "gf.Module", gf.load(name, search_paths=self.project.search_paths())
            )
        return self._packages[name]

    def names(self, name: str) -> list[str] | None:
        """
        Find a package's exported names and cache successful discoveries

        Use griffe's package model when available. If loading fails or `__all__` lists
        only undefined names, fall back to a literal `__all__` in `__init__.py`.
        Retry discovery on later calls when neither source yields a result.

        Parameters
        ----------
        name
            The package's importable name. Dashes count as underscores.

        Returns
        -------
        :
            The exported names, or `None` if neither source yields a result.
        """
        normalized = name.replace("-", "_")
        if normalized in self._names:
            return self._names[normalized]

        exports = None
        try:
            package = self.package(normalized)
        except USER_CODE_ERRORS as error:
            print(
                f"Warning: Could not load package with griffe ({type(error).__name__})",
                file=sys.stderr,
            )
            if name != normalized:
                print(
                    f"   (Looking for module '{normalized}' from project '{name}')",
                    file=sys.stderr,
                )
        else:
            exports = discovery.discover_exports(package, self.config, report=print)

        if exports is None:
            exports = self._dunder_all(name, normalized)
        if exports is not None:
            self._names[normalized] = exports
        return exports

    def _dunder_all(self, name: str, normalized: str) -> list[str] | None:
        """
        Read a literal `__all__` from a package's `__init__.py`

        Parameters
        ----------
        name
            The package's importable name as requested.
        normalized
            `name` with dashes replaced by underscores.

        Returns
        -------
        :
            The listed names, or `None` when the file or a literal `__all__` is missing.
        """
        print("Falling back to __all__ discovery", file=sys.stderr)
        root = self.project.source_roots[0]
        init_file = (
            self.project.package_init
            if name == self.project.importable_name
            else locate_package_init(root, self.project.manifest, name)
        )
        if init_file is None:
            print(
                f"Could not locate __init__.py for package '{name}'"
                + (f" (module name: '{normalized}')" if normalized != name else ""),
                file=sys.stderr,
            )
            if normalized != name:
                print(
                    f"Tip: Ensure a '{normalized}/' directory exists with an __init__.py file",
                    file=sys.stderr,
                )
            return None
        print(f"Found package __init__.py at: {init_file.relative_to(root)}")
        return discovery.parse_dunder_all(init_file, self.config, report=print)

    def categorise(self, name: str, exports: list[str]) -> Categories:
        """
        Group a package's exports by API reference category

        Keep a method, or a member of an exported module, when the renderer can document it
        after importing the package; when the package cannot be imported, keep it when static
        analysis finds it. If griffe cannot load the package, group all exports under
        `other`, except metadata names such as `__version__`.

        Parameters
        ----------
        name
            The package's importable name. Dashes count as underscores.
        exports
            The names to group.

        Returns
        -------
        :
            The exports grouped by category.
        """
        normalized = name.replace("-", "_")
        try:
            package = self.package(normalized)
        except USER_CODE_ERRORS as error:
            print(
                f"Warning: Could not load package with griffe ({type(error).__name__})",
                file=sys.stderr,
            )
            categories = discovery.empty_categories()
            categories["other"] = [
                export for export in exports if export not in discovery.METADATA_NAMES
            ]
            return categories

        return discovery.categorise_exports(
            package,
            exports,
            renderable=probe.RendererCheck(normalized, report=print),
            report=print,
        )

    def sections(self, name: str) -> list[dict[str, Any]] | None:
        """
        Build the API reference sections for a package

        Use sections from the `reference` setting when available. Otherwise, build
        sections from the package's discovered exports.

        Parameters
        ----------
        name
            The package's importable name. Dashes count as underscores.

        Returns
        -------
        :
            The sections, or `None` when neither source yields any.

        Raises
        ------
        BuildError
            If the `reference` setting names an object the loaded package lacks.
        """
        reference_config = self.config.reference
        if reference_config:
            print("Using explicit reference configuration from great-docs.yml")
            try:
                package = self.package(name)
            except USER_CODE_ERRORS:
                categories = discovery.empty_categories()
            else:
                try:
                    categories = discovery.categorise_references(package, reference_config)
                except BuildError as error:
                    print(f"ERROR: {error}", file=sys.stderr)
                    raise
            configured = reference_sections.from_explicit_config(
                self.config, reference_config, categories
            )
            if configured:
                return configured

        exports = [
            export for export in self.names(name) or () if export not in discovery.METADATA_NAMES
        ]
        if not exports:
            return None
        print(f"Found {len(exports)} exported names to document")
        return reference_sections.from_categories(self.config, self.categorise(name, exports))
