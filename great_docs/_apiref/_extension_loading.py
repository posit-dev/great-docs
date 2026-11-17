"""
Project-local extension sources and their owned Python imports

Load each operation in a separate package namespace. Relative imports read current
source bytes; installed packages retain Python's ordinary import caching.
"""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import importlib.util
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from types import CodeType, ModuleType
from typing import TYPE_CHECKING

__all__ = ["_ExtensionSource", "_ImportOwner"]

if TYPE_CHECKING:
    from importlib.machinery import ModuleSpec

    from ..config import Config


@dataclass(frozen=True)
class _ExtensionSource:
    """An extension file and the project directories it was configured from"""

    entry_path: Path
    """The absolute path of the extension file"""
    config_root: Path
    """The directory of the configuration file that names the extension"""
    source_root: Path
    """The documentation source directory, not its staged copy"""

    @classmethod
    def make(cls, config: Config, source_root: Path) -> _ExtensionSource | None:
        """Resolve a configured entry while retaining the original project roots"""
        entry = config.api_reference_extension
        if entry is None:
            return None
        return cls(entry, config.config_path.parent.resolve(), source_root.resolve())


class _SourceLoader(importlib.machinery.SourceFileLoader):
    """A source loader that compiles the current file instead of reusing cached bytecode"""

    def __init__(self, name: str, path: Path, paths: set[Path]) -> None:
        super().__init__(name, str(path))
        self._paths = paths

    def get_code(self, fullname: str) -> CodeType:
        """
        Compile the module's current source and record its path

        Parameters
        ----------
        fullname
            The module's full name. The loader serves one file, so it ignores the name.

        Returns
        -------
        :
            The compiled module code.
        """
        path = Path(self.path)
        self._paths.add(path)
        return self.source_to_code(path.read_bytes(), str(path))


class _ImportOwner(importlib.abc.MetaPathFinder):
    """An import finder for one extension file and its helper modules, under a private namespace"""

    def __init__(self, source: _ExtensionSource) -> None:
        self.source = source
        self.namespace = f"_great_docs_extension_{uuid.uuid4().hex}"
        self._paths: set[Path] = set()
        self._closed = False

    @property
    def paths(self) -> frozenset[Path]:
        """The paths of the extension file and its helper modules, kept after closing"""
        return frozenset(self._paths)

    def find_spec(
        self,
        fullname: str,
        path: object = None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        """
        Find a module inside this owner's namespace and decline all others

        Parameters
        ----------
        fullname
            The full name of the module to import.
        path, target
            Unused arguments of the finder protocol.

        Returns
        -------
        :
            A specification for a module, package or directory beside the extension file,
            or `None` when the name is outside the namespace or nothing there matches it.
        """
        if not fullname.startswith(self.namespace + "."):
            return None
        relative = fullname[len(self.namespace) + 1 :].split(".")
        location = self.source.entry_path.parent.joinpath(*relative)
        if location.is_dir():
            init = location / "__init__.py"
            if not init.is_file():
                spec = importlib.machinery.ModuleSpec(fullname, loader=None, is_package=True)
                spec.submodule_search_locations = [str(location)]
                return spec
            return self._spec(fullname, init, package=True)
        module = location.with_suffix(".py")
        return self._spec(fullname, module) if module.is_file() else None

    def _spec(self, name: str, path: Path, *, package: bool = False) -> ModuleSpec:
        """
        Build a specification that loads a module from its current source

        Parameters
        ----------
        name
            The module's full name.
        path
            The module's source file, or the `__init__.py` of a package.
        package
            Whether the module is a package.

        Returns
        -------
        :
            A specification whose loader records `path` when it compiles the module.
        """
        spec = importlib.util.spec_from_file_location(
            name,
            path,
            loader=_SourceLoader(name, path, self._paths),
            submodule_search_locations=[str(path.parent)] if package else None,
        )
        assert spec is not None
        return spec

    def load(self) -> ModuleType:
        """
        Import the extension file as a package so its relative imports resolve

        Returns
        -------
        :
            The extension module.

        Raises
        ------
        RuntimeError
            If the owner is closed.
        """
        if self._closed:
            raise RuntimeError("The extension import owner is closed.")
        spec = self._spec(self.namespace, self.source.entry_path, package=True)
        module = importlib.util.module_from_spec(spec)
        sys.meta_path.insert(0, self)
        sys.modules[self.namespace] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    def close(self) -> None:
        """Release owned modules and observation without clearing imported packages"""
        if self._closed:
            return
        self._closed = True
        if self in sys.meta_path:
            sys.meta_path.remove(self)
        for name in list(sys.modules):
            if name == self.namespace or name.startswith(self.namespace + "."):
                del sys.modules[name]
