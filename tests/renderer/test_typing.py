# pyright: reportPrivateUsage=false
"""Tests for _renderer/typing.py type alias definitions."""

from typing import get_args


def test_module_imports_successfully():
    """The typing module loads without errors."""
    from great_docs._apiref import typing as qr_typing

    assert qr_typing is not None


def test_display_name_format_literals():
    """DisplayNameFormat contains expected literal values."""
    from great_docs._apiref.typing import DisplayNameFormat

    args = get_args(DisplayNameFormat)
    assert "doc" in args
    assert "full" in args
    assert "name" in args
    assert "short" in args
    assert "relative" in args
    assert "canonical" in args


def test_doc_object_kind_literals():
    """DocObjectKind contains all expected object kinds."""
    from great_docs._apiref.typing import DocObjectKind

    args = get_args(DocObjectKind)
    expected = {
        "module",
        "class",
        "method",
        "property",
        "function",
        "attribute",
        "alias",
        "type",
        "typevar",
        "type alias",
    }
    assert set(args) == expected


def test_documentable_union_members():
    """Documentable includes Doc, Page, and Section types."""
    from great_docs._apiref.typing import Documentable

    args = get_args(Documentable)
    type_names = {t.__name__ for t in args}
    assert "DocClass" in type_names
    assert "DocFunction" in type_names
    assert "DocAttribute" in type_names
    assert "DocModule" in type_names
    assert "Page" in type_names
    assert "Section" in type_names
    assert "Layout" not in type_names


def test_render_obj_type_union_members():
    """RenderObjType includes all Render class types."""
    from great_docs._apiref.typing import RenderObjType

    args = get_args(RenderObjType)
    type_names = {t.__name__ for t in args}
    assert "ObjectRenderer" in type_names
    assert "ClassRenderer" in type_names
    assert "FunctionRenderer" in type_names
    assert "AttributeRenderer" in type_names
    assert "ModuleRenderer" in type_names
    assert "ReferenceIndexRenderer" in type_names
    assert "APIPageRenderer" in type_names
    assert "ReferenceSectionRenderer" in type_names


def test_any_docstring_section_union():
    """AnyDocstringSection includes griffe and custom section types."""
    from great_docs._apiref.typing import AnyDocstringSection

    args = get_args(AnyDocstringSection)
    type_names = {t.__name__ for t in args}
    assert "DocstringSection" in type_names
    assert "DCDocstringSection" in type_names


def test_doc_type_union():
    """DocType includes the five core Doc types."""
    from great_docs._apiref.typing import DocType

    args = get_args(DocType)
    type_names = {t.__name__ for t in args}
    assert type_names == {
        "DocClass",
        "DocFunction",
        "DocAttribute",
        "DocTypeAlias",
        "DocModule",
    }


def test_doc_member_type_union():
    """DocMemberType includes MemberPage and Doc."""
    from great_docs._apiref.typing import DocMemberType

    args = get_args(DocMemberType)
    type_names = {t.__name__ for t in args}
    assert "MemberPage" in type_names
    assert "Doc" in type_names
