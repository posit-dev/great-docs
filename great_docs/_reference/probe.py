"""
Probes of a package that choose `great-docs.yml` settings and check what the renderer can document

`detect_docstring_style` reads docstrings statically. The other probes import the package, so
they run its code: an error that importing user code can raise is caught at this boundary and
counts as a failed probe.
"""

from __future__ import annotations

import importlib
import re
from typing import TYPE_CHECKING, Literal

import griffe as gf

from .._apiref.introspect import get_object, make_loader
from .._build.steps import USER_CODE_ERRORS

if TYPE_CHECKING:
    from collections.abc import Callable

DocstringStyle = Literal["numpy", "google", "sphinx"]


# The deepest level of members whose docstrings vote on the style; the package is level 0.
_STYLE_DEPTH = 2

_NUMPY_SECTION = re.compile(
    r"^\s*(Parameters|Returns|Yields|Raises|Examples|Attributes|Methods|See Also|Notes|References|Warnings)\s*\n\s*-{3,}",
    re.MULTILINE,
)
_GOOGLE_SECTION = re.compile(
    r"^\s*(Args|Arguments|Returns|Yields|Raises|Examples|Attributes|Note|Notes|Todo|Warning|Warnings):\s*$",
    re.MULTILINE,
)
_SPHINX_FIELD = re.compile(r"^\s*:(param|type|returns|rtype|raises|var|ivar|cvar)\s", re.MULTILINE)

# How many of the package's first members to consider, and how many of those to import.
_DYNAMIC_CANDIDATES = 10
_DYNAMIC_SAMPLES = 5
# How many members of each sampled object to resolve.
_DYNAMIC_MEMBER_SAMPLES = 3


def detect_docstring_style(package: gf.Module, *, report: Callable[[str], None]) -> DocstringStyle:
    """
    Choose the docstring style that most of a package's docstrings use

    The docstrings of the package and of its members two levels down vote, skipping aliases. A
    docstring votes NumPy when a section heading is underlined with dashes, Google when a
    heading ends in a colon and none is underlined, and Sphinx when it has a field such as
    `:param x:`. Sphinx wins only with more votes than each other style, and Google only with
    more than NumPy.

    Parameters
    ----------
    package
        The loaded package.
    report
        A callback that receives the vote and the chosen style.

    Returns
    -------
    :
        The chosen style, `"numpy"` when no docstring votes.
    """
    docstrings = _docstrings(package, depth=0)
    if not docstrings:
        report("No docstrings found, defaulting to numpy style")
        return "numpy"

    numpy = google = sphinx = 0
    for docstring in filter(None, docstrings):
        has_numpy = _NUMPY_SECTION.search(docstring) is not None
        numpy += has_numpy
        google += not has_numpy and _GOOGLE_SECTION.search(docstring) is not None
        sphinx += _SPHINX_FIELD.search(docstring) is not None

    if numpy + google + sphinx == 0:
        report("No clear docstring style detected, defaulting to numpy")
        return "numpy"

    report(f"Docstring style detection: numpy={numpy}, google={google}, sphinx={sphinx}")
    style: DocstringStyle
    if sphinx > numpy and sphinx > google:
        style = "sphinx"
    elif google > numpy:
        style = "google"
    else:
        style = "numpy"
    report(f"Detected {style} docstring style")
    return style


def _docstrings(obj: gf.Object, depth: int) -> list[str]:
    """
    Collect the docstrings of an object and its members

    Parameters
    ----------
    obj
        The object.
    depth
        The object's level below the package.

    Returns
    -------
    :
        The docstrings, the object's first, down to `_STYLE_DEPTH` levels below the package.
    """
    found = [obj.docstring.value] if obj.docstring else []
    if depth < _STYLE_DEPTH:
        for member in obj.members.values():
            if not isinstance(member, gf.Alias):
                found.extend(_docstrings(member, depth + 1))
    return found


def detect_dynamic_mode(package: gf.Module, *, report: Callable[[str], None]) -> bool:
    """
    Check whether the renderer can read a package by importing it

    Import a few of the package's public members, with a few of their own members, and resolve
    their aliases. Dynamic mode fails only when an alias forms a cycle; any other import error
    is ignored.

    Parameters
    ----------
    package
        The loaded package.
    report
        A callback that receives the verdict.

    Returns
    -------
    :
        `False` if a sampled alias forms a cycle, and `True` otherwise.
    """
    candidates = [
        name for name in list(package.members)[:_DYNAMIC_CANDIDATES] if not name.startswith("_")
    ]
    if not candidates:
        return True

    cycles = 0
    for name in candidates[:_DYNAMIC_SAMPLES]:
        try:
            obj = get_object(f"{package.path}:{name}", dynamic=True)
            _ = obj.kind
            for member in list(obj.members.values())[:_DYNAMIC_MEMBER_SAMPLES]:
                try:
                    _ = member.kind
                except gf.CyclicAliasError:
                    cycles += 1
                    break
        except gf.CyclicAliasError:
            cycles += 1
        except USER_CODE_ERRORS:
            pass

    if cycles:
        report(f"Detected {cycles} cyclic alias error(s), using dynamic: false")
        return False
    report("Dynamic introspection mode works for this package")
    return True


class RendererCheck:
    """
    A check whether the renderer can document an object, given its path

    The first check imports the package. While the package imports, each object is imported
    and its members resolved, as the renderer does in dynamic mode. When the import fails,
    the failure is reported once and each object only has to be found by static analysis, so
    a package that needs a missing dependency keeps its methods.

    All checks share a griffe loader, so each module is loaded once.

    Parameters
    ----------
    module_name
        The package's importable name.
    report
        A callback that receives the line reporting a failed import.
    """

    def __init__(self, module_name: str, *, report: Callable[[str], None]) -> None:
        self._module_name = module_name
        self._report = report
        self._loader = make_loader("numpy")
        self._imports: bool | None = None

    def __call__(self, path: str) -> bool:
        """
        Check whether the renderer can document an object

        Parameters
        ----------
        path
            The object's path, in the form `package:Class.method`.

        Returns
        -------
        :
            Whether the object, and its members, can be read. An error that importing user
            code can raise means it cannot.
        """
        if self._imports is None:
            self._imports = self._import_package()
        # Static analysis raises `KeyError` for a path it models nothing at.
        errors = USER_CODE_ERRORS if self._imports else (KeyError, *USER_CODE_ERRORS)
        try:
            obj = get_object(path, dynamic=self._imports, loader=self._loader)
            _ = obj.members
            _ = obj.kind
        except errors:
            return False
        return True

    def _import_package(self) -> bool:
        """
        Import the package, reporting a failure

        Returns
        -------
        :
            Whether the import succeeded.
        """
        try:
            _ = importlib.import_module(self._module_name)
        except USER_CODE_ERRORS as error:
            self._report(
                f"Warning: Could not import '{self._module_name}' "
                f"({type(error).__name__}: {error}); "
                "checking methods with static analysis instead"
            )
            return False
        return True
