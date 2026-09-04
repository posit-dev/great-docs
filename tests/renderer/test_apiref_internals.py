"""Targeted branch-coverage tests for _visitor, _type_checks, _tools, _docstring_sections, content."""

from __future__ import annotations

import dataclasses
import sys
import textwrap

import griffe as gf
import pytest

from great_docs._apiref import content
from great_docs._apiref._docstring_sections import _DocstringSectionPatched, transform
from great_docs._apiref._tools import render_code_variable, render_type_object
from great_docs._apiref._type_checks import is_typealias, is_typevar
from great_docs._apiref._visitor import NodeVisitor


# ---------------------------------------------------------------------------
# content.Doc.from_griffe — unknown kind raises TypeError
# ---------------------------------------------------------------------------


def test_doc_from_griffe_unknown_kind_raises():
    """Doc.from_griffe raises TypeError for non-function/class/module/attribute/alias kinds."""
    # Build a TypeVar attribute — treat it as an unsupported kind by patching kind
    attr = gf.Attribute("X")
    attr.annotation = gf.ExprName("int")

    # Patch kind to something the factory doesn't handle
    attr.__dict__["kind"] = type("K", (), {"value": "unknown"})()
    with pytest.raises(TypeError, match="Cannot document"):
        content.Doc.from_griffe(attr.name, attr)


# ---------------------------------------------------------------------------
# content.Page.obj — more-than-one content item raises ValueError
# ---------------------------------------------------------------------------


def test_page_obj_multiple_contents_raises():
    """Page.obj raises ValueError when the page has more than one content item."""
    fn = gf.Function("f")
    doc = content.Doc.from_griffe(fn.name, fn)
    page = content.Page(contents=[doc, doc])  # type: ignore[list-item]
    with pytest.raises(ValueError):
        _ = page.obj


# ---------------------------------------------------------------------------
# _type_checks.is_typealias — string annotation branch
# ---------------------------------------------------------------------------


def test_is_typealias_string_annotation_returns_true():
    """is_typealias returns True when annotation is a plain string 'TypeAlias'."""
    attr = gf.Attribute("MyAlias")
    attr.annotation = "TypeAlias"

    assert is_typealias(attr) is True


def test_is_typealias_non_typealias_expr_returns_false():
    """is_typealias returns False when annotation is an Expr that is not TypeAlias."""
    attr = gf.Attribute("NotAlias")
    attr.annotation = gf.ExprName("int")  # ExprName, name != "TypeAlias"

    assert is_typealias(attr) is False


def test_is_typealias_other_annotation_type_returns_false():
    """is_typealias returns False for annotation types other than ExprName or str."""
    attr = gf.Attribute("WeirdAlias")
    # Subscript expression is neither ExprName nor str
    attr.annotation = gf.ExprSubscript(gf.ExprName("List"), gf.ExprName("int"))

    assert is_typealias(attr) is False


# ---------------------------------------------------------------------------
# _type_checks — classification through a re-exported name
# ---------------------------------------------------------------------------


def _reexported(source: str, name: str) -> gf.Alias:
    """Return the alias created when a package re-exports `name`"""
    modules = {
        "__init__.py": f"from ._defs import {name}\n",
        "_defs.py": textwrap.dedent(source),
    }
    with gf.temporary_visited_package("package", modules) as package:
        member = package[name]
    assert isinstance(member, gf.Alias)
    return member


@pytest.mark.skipif(
    sys.version_info < (3, 12),
    reason="PEP 695 `type` statement requires Python 3.12+",
)
def test_is_typealias_follows_a_reexported_pep695_alias():
    """Preserve a PEP 695 alias's kind under its exported name"""
    assert is_typealias(_reexported("type Contract = int | str\n", "Contract")) is True


def test_is_typealias_follows_a_reexported_annotated_alias():
    """Preserve an annotated alias's kind under its exported name"""
    source = """
    from typing import TypeAlias

    Contract: TypeAlias = int
    """

    assert is_typealias(_reexported(source, "Contract")) is True


def test_is_typevar_follows_a_reexported_typevar():
    """Preserve a TypeVar's kind under its exported name"""
    source = """
    from typing import TypeVar

    T = TypeVar("T")
    """

    assert is_typevar(_reexported(source, "T")) is True


def test_classification_of_an_unloadable_target_is_false():
    """Return `False` when an alias target cannot be loaded"""
    modules = {"__init__.py": "from never_imported_package import Contract\n"}
    with gf.temporary_visited_package("package", modules) as package:
        alias = package["Contract"]

    with pytest.raises(gf.AliasResolutionError):
        _ = alias.final_target

    assert is_typealias(alias) is False
    assert is_typevar(alias) is False


# ---------------------------------------------------------------------------
# _visitor.Visitor — private field skip
# ---------------------------------------------------------------------------


def test_visitor_skips_private_dataclass_fields():
    """Visitor._enter_dataclass skips fields whose names start with '_'."""

    @dataclasses.dataclass
    class _Inner:
        public: int = 1
        _private: int = 2  # should be skipped

    visited: list[object] = []

    class TrackingVisitor(NodeVisitor):
        def visit(self, el: object) -> object:
            visited.append(el)
            return el

    v = TrackingVisitor()
    v._enter_dataclass(_Inner(public=10, _private=99))

    # The private field value (99) should NOT appear in visited
    assert 99 not in visited
    assert 10 in visited


# ---------------------------------------------------------------------------
# _tools.render_type_object — non-string path
# ---------------------------------------------------------------------------


def test_render_type_object_with_type_input():
    """render_type_object accepts a type object (not a str) and renders it."""
    from pathlib import Path as _Path

    # _canonical_path(Path) → "pathlib.Path"; render_type_object resolves via griffe
    result = render_type_object(_Path)

    assert isinstance(result, str)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# _docstring_sections — duplicate registration raises KeyError
# ---------------------------------------------------------------------------


def test_docstring_section_patched_duplicate_registration_raises():
    """Registering two _DocstringSectionPatched subclasses with the same kind raises KeyError."""
    from great_docs._apiref._docstring_sections import DocstringSectionKindPatched

    # Use the see_also kind which is already registered — registering again must raise
    with pytest.raises(KeyError):

        class _Duplicate(_DocstringSectionPatched):
            kind = DocstringSectionKindPatched.see_also  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# _render/doctypealias._format_alias_value — non-Expr value
# and HAS_RUFF long expression
# ---------------------------------------------------------------------------


def test_render_value_non_expr_uses_format_value():
    """RenderDocTypeAlias._render_value uses format_value when value is not a gf.Expr."""
    from unittest.mock import MagicMock, patch

    from great_docs._apiref._render.doctypealias import RenderDocTypeAlias
    from great_docs._apiref.content import DocTypeAlias

    # Build a minimal mock griffe object with a plain-string value
    mock_obj = MagicMock(spec=gf.Attribute)
    mock_obj.name = "X"
    mock_obj.path = "package.X"
    mock_obj.canonical_path = "package.X"
    mock_obj.kind.value = "type alias"
    mock_obj.annotation = None
    mock_obj.value = "int | str"  # plain str, not gf.Expr
    mock_obj.type_parameters = []

    doc = DocTypeAlias(name="X", obj=mock_obj)  # type: ignore[arg-type]
    renderer = RenderDocTypeAlias(doc)

    with patch(
        "great_docs._apiref._render.doctypealias.format_value", return_value="int | str"
    ) as mock_fv:
        result = renderer._render_value("plain string")

    mock_fv.assert_called_once_with("plain string")

    assert result == "int | str"


def test_render_value_long_expr_with_ruff():
    """RenderDocTypeAlias._render_value calls render_formatted_expr when HAS_RUFF and expr is long."""
    from unittest.mock import MagicMock, patch

    from great_docs._apiref._render import doctypealias as dta
    from great_docs._apiref._render.doctypealias import RenderDocTypeAlias
    from great_docs._apiref.content import DocTypeAlias

    # Build an expression that stringifies to > 79 chars
    # e.g. "int | str | bytes | float | bool | complex | list | dict | tuple | set | frozenset"
    def _chain(names: list[str]) -> gf.Expr:
        result: gf.Expr = gf.ExprName(names[0])
        for n in names[1:]:
            result = gf.ExprBinOp(result, "|", gf.ExprName(n))
        return result

    long_expr = _chain(
        [
            "int",
            "str",
            "bytes",
            "float",
            "bool",
            "complex",
            "list",
            "dict",
            "tuple",
            "set",
            "frozenset",
        ]
    )

    assert len(str(long_expr)) > 79, "expression must be > 79 chars for this test to be meaningful"

    mock_obj = MagicMock(spec=gf.Attribute)
    mock_obj.name = "Y"
    mock_obj.path = "package.Y"
    mock_obj.canonical_path = "package.Y"
    mock_obj.kind.value = "type alias"
    mock_obj.annotation = None
    mock_obj.value = long_expr
    mock_obj.type_parameters = []

    doc = DocTypeAlias(name="Y", obj=mock_obj)  # type: ignore[arg-type]
    renderer = RenderDocTypeAlias(doc)

    with (
        patch.object(dta, "HAS_RUFF", True),
        patch(
            "great_docs._apiref._render.doctypealias.render_formatted_expr",
            return_value="formatted",
        ) as mock_rfe,
    ):
        result = renderer._render_value(long_expr)

    mock_rfe.assert_called_once_with(long_expr)

    assert result == "formatted"


# ---------------------------------------------------------------------------
# _docstring_sections.transform — non-text/admonition passthrough
# ---------------------------------------------------------------------------


def test_docstring_section_transform_non_text_admonition_passthrough():
    """_DocstringSectionPatched.transform returns [el] for non-text/admonition section types."""
    # A Parameters section is neither DocstringSectionText nor DocstringSectionAdmonition
    params_section = gf.DocstringSectionParameters([])
    result = _DocstringSectionPatched.transform(params_section)

    assert result == [params_section]
