"""
Direct import rules for shared content, configuration and public entry modules
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from importlib.util import resolve_name
from pathlib import Path
from typing import Literal

import pytest

PACKAGE = Path(__file__).resolve().parents[1] / "great_docs"
SHARED_CONTENT = {
    "great_docs._content.authored",
    "great_docs._content.homepage",
    "great_docs._content.metadata",
}

# Verified on 2026-11-12 against merged Phase 4 5544e0b6: the tool names are
# declarations; the separate notebook import only resolves a runtime version value.
CONFIG_IMPORTS = {
    "great_docs._website.ai_agents.webmcp_tools.TOOL_NAMES": "declaration",
    "great_docs._content.marimo.islands_runtime_version": "runtime value",
}


@dataclass(frozen=True)
class Import:
    """
    An imported name and the context in which its import executes
    """

    target: str
    context: Literal["runtime", "local runtime", "type-only"]
    line: int


def _imports(source: str, module: str, *, package: bool = False) -> list[Import]:
    imports: list[Import] = []
    parent = module if package else module.rpartition(".")[0]

    def guard(node: ast.expr, names: dict[str, str]) -> bool | None:
        if isinstance(node, ast.Name) and names.get(node.id) == "typing.TYPE_CHECKING":
            return True
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "TYPE_CHECKING"
            and isinstance(node.value, ast.Name)
            and names.get(node.value.id) == "typing"
        ):
            return True
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            value = guard(node.operand, names)
            return None if value is None else not value
        return None

    def visit(
        nodes: list[ast.stmt], names: dict[str, str], *, local: bool = False, typed: bool = False
    ) -> None:
        for node in nodes:
            context = "type-only" if typed else "local runtime" if local else "runtime"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(Import(alias.name, context, node.lineno))
                    names[alias.asname or alias.name.split(".")[0]] = alias.name
            elif isinstance(node, ast.ImportFrom):
                owner = node.module or ""
                if node.level:
                    owner = resolve_name("." * node.level + owner, parent)
                for alias in node.names:
                    target = f"{owner}.{alias.name}"
                    imports.append(Import(target, context, node.lineno))
                    names[alias.asname or alias.name] = target
            elif isinstance(node, ast.If):
                value = guard(node.test, names)
                visit(node.body, names.copy(), local=local, typed=typed or value is True)
                visit(node.orelse, names.copy(), local=local, typed=typed or value is False)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.pop(node.name, None)
                inner = names.copy()
                arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
                arguments.extend(arg for arg in [node.args.vararg, node.args.kwarg] if arg)
                for argument in arguments:
                    inner.pop(argument.arg, None)
                visit(node.body, inner, local=True, typed=typed)
            elif isinstance(node, ast.ClassDef):
                names.pop(node.name, None)
                visit(node.body, names.copy(), local=local, typed=typed)
            else:
                if isinstance(node, (ast.Assign, ast.AnnAssign, ast.For, ast.AsyncFor)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target in targets:
                        for child in ast.walk(target):
                            if isinstance(child, ast.Name):
                                names.pop(child.id, None)
                for _, value in ast.iter_fields(node):
                    if isinstance(value, list):
                        for child in value:
                            if isinstance(child, ast.stmt):
                                visit([child], names, local=local, typed=typed)
                            elif isinstance(child, (ast.ExceptHandler, ast.match_case)):
                                visit(child.body, names, local=local, typed=typed)

    visit(ast.parse(source).body, {})
    return imports


def _within(target: str, module: str) -> bool:
    return target == module or target.startswith(module + ".")


def _violations(module: str, imports: list[Import]) -> list[Import]:
    rejected: list[Import] = []
    for imported in imports:
        if imported.context == "type-only":
            continue
        target = imported.target
        if (_within(module, "great_docs._apiref") or module in SHARED_CONTENT) and _within(
            target, "great_docs._website"
        ):
            rejected.append(imported)
        elif (
            module == "great_docs.config"
            and (
                _within(target, "great_docs._website")
                or _within(target, "great_docs._build")
                or _within(target, "great_docs._content.marimo")
            )
            and (target not in CONFIG_IMPORTS or imported.context != "local runtime")
        ):
            rejected.append(imported)
        elif any(_within(module, family) for family in ["great_docs._cli", "great_docs._mcp"]):
            if any(_within(target, shim) for shim in ["great_docs.cli", "great_docs.mcp"]):
                rejected.append(imported)
    return rejected


def test_package_import_boundaries() -> None:
    rejected: list[tuple[str, Import]] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        module = ".".join(path.relative_to(PACKAGE.parent).with_suffix("").parts)
        package = path.name == "__init__.py"
        if package:
            module = module.removesuffix(".__init__")
        imports = _imports(path.read_text(encoding="utf-8"), module, package=package)
        rejected.extend((module, imported) for imported in _violations(module, imports))
    assert rejected == []


def test_configuration_imports_keep_distinct_local_roles() -> None:
    imports = _imports((PACKAGE / "config.py").read_text(), "great_docs.config")
    observed = {item.target: item.context for item in imports if item.target in CONFIG_IMPORTS}
    assert observed == dict.fromkeys(CONFIG_IMPORTS, "local runtime")


def test_project_and_evolution_initialisers_remain_bounded() -> None:
    project = _imports(
        (PACKAGE / "_project/__init__.py").read_text(), "great_docs._project", package=True
    )
    evolution = _imports(
        (PACKAGE / "_api_evolution/__init__.py").read_text(),
        "great_docs._api_evolution",
        package=True,
    )
    assert [item.target for item in project if item.context != "type-only"] == [
        "great_docs._project.model.Project"
    ]
    assert [item for item in evolution if item.context != "type-only"] == []


def test_builtin_registration_remains_eager() -> None:
    imports = _imports((PACKAGE / "__init__.py").read_text(), "great_docs", package=True)
    assert [
        (item.target, item.context) for item in imports if item.target == "great_docs._builtin"
    ] == [("great_docs._builtin", "runtime")]


@pytest.mark.parametrize(
    ("source", "target", "context"),
    [
        ("import great_docs._website as site", "great_docs._website", "runtime"),
        ("from great_docs import _website as site", "great_docs._website", "runtime"),
        ("from .._website import head as h", "great_docs._website.head", "runtime"),
        ("def f():\n from .._website import head", "great_docs._website.head", "local runtime"),
        (
            "from typing import TYPE_CHECKING as checking\nif checking:\n from .._website import head",
            "great_docs._website.head",
            "type-only",
        ),
        (
            "import typing as t\nif t.TYPE_CHECKING:\n from .._website import head",
            "great_docs._website.head",
            "type-only",
        ),
        (
            "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n pass\nelse:\n from .._website import head",
            "great_docs._website.head",
            "runtime",
        ),
        (
            "from typing import TYPE_CHECKING\nif not TYPE_CHECKING:\n from .._website import head",
            "great_docs._website.head",
            "runtime",
        ),
        (
            "from typing import TYPE_CHECKING\nif not TYPE_CHECKING:\n pass\nelse:\n from .._website import head",
            "great_docs._website.head",
            "type-only",
        ),
        (
            "import typing as t\ndef f(t):\n if t.TYPE_CHECKING:\n  from .._website import head",
            "great_docs._website.head",
            "local runtime",
        ),
        (
            "import typing as t\nt = object()\nif t.TYPE_CHECKING:\n from .._website import head",
            "great_docs._website.head",
            "runtime",
        ),
        (
            "try:\n pass\nexcept ImportError:\n from .._website import head",
            "great_docs._website.head",
            "runtime",
        ),
    ],
)
def test_import_contexts(source: str, target: str, context: str) -> None:
    observed = _imports(source, "great_docs._content.authored")
    assert [(item.target, item.context) for item in observed if item.target == target] == [
        (target, context)
    ]


@pytest.mark.parametrize(
    ("module", "source", "rejected"),
    [
        ("great_docs._apiref._render.api_page", "from ..._website import head", True),
        ("great_docs._content.metadata", "def f():\n from .._website import head", True),
        ("great_docs._content.authored", "from . import homepage", False),
        (
            "great_docs._content.homepage",
            "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n from ..config import Config",
            False,
        ),
        ("great_docs._content.custom_pages", "from .._website import head", False),
        ("great_docs._content.sections", "from .._website import navbar", False),
        (
            "great_docs.config",
            "def f():\n from ._website.ai_agents.webmcp_tools import TOOL_NAMES",
            False,
        ),
        (
            "great_docs.config",
            "def f():\n from ._content.marimo import islands_runtime_version",
            False,
        ),
        ("great_docs.config", "from ._website.ai_agents.webmcp_tools import TOOL_NAMES", True),
        (
            "great_docs.config",
            "def f():\n from ._website.ai_agents.webmcp_tools import for_config",
            True,
        ),
        ("great_docs.config", "def f():\n from ._content.marimo import build_notebooks", True),
        ("great_docs.config", "def f():\n from ._content import marimo", True),
        ("great_docs.config", "def f():\n from ._build import content", True),
        ("great_docs._cli.build", "from great_docs import cli as public", True),
        ("great_docs._mcp.tools", "def f():\n from ..mcp import mcp", True),
        ("great_docs._cli.build", "from . import options", False),
    ],
)
def test_import_rules(module: str, source: str, rejected: bool) -> None:
    assert bool(_violations(module, _imports(source, module))) is rejected
