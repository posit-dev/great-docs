"""Tests for PEP 695 type alias support (`type X = ...`)."""

from __future__ import annotations

import sys
import textwrap

import pytest

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 12),
    reason="PEP 695 `type` statement requires Python 3.12+",
)
requires_pep696 = pytest.mark.skipif(
    sys.version_info < (3, 13),
    reason="PEP 696 type parameter defaults require Python 3.13+",
)


def _load_type_parameters(code: str, name: str):
    """Load the type parameters of the named alias from a source snippet"""
    import griffe as gf

    with gf.temporary_visited_package("package", {"__init__.py": code}) as m:
        return m[name].type_parameters


@pytest.mark.parametrize(
    ("source", "name", "expected"),
    [
        ("type Simple = int | str", "Simple", ""),
        ("type ListOrSet[T] = list[T] | set[T]", "ListOrSet", "[T]"),
        ("type Bounded[T: str] = list[T]", "Bounded", "[T: str]"),
        ("type Constrained[S: (str, bytes)] = list[S]", "Constrained", "[S: (str, bytes)]"),
        ("type Variadic[T, *Ts] = tuple[T, *Ts]", "Variadic", "[T, *Ts]"),
        ("type Callback[**P] = dict[P, int]", "Callback", "[**P]"),
        pytest.param(
            "type WithDefault[T = int] = list[T]",
            "WithDefault",
            "[T = int]",
            marks=requires_pep696,
        ),
    ],
)
def test_render_type_parameters(source: str, name: str, expected: str):
    from great_docs._apiref._render._type_parameters import render_type_parameters

    assert render_type_parameters(_load_type_parameters(source, name)) == expected


def test_render_type_parameters_none():
    from great_docs._apiref._render._type_parameters import render_type_parameters

    assert render_type_parameters(None) == ""


def _load_member(code: str, name: str):
    """Load a single named member from a source snippet"""
    import griffe as gf

    with gf.temporary_visited_package("package", {"__init__.py": code}) as m:
        return m[name]


def test_label_pep695_spelling():
    from great_docs._apiref._render._label import get_label

    obj = _load_member("type Contract = int | str", "Contract")
    assert get_label(obj) == "typealias"


def test_label_legacy_spelling():
    from great_docs._apiref._render._label import get_label

    code = "from typing import TypeAlias\nContract: TypeAlias = int | str\n"
    obj = _load_member(code, "Contract")
    assert get_label(obj) == "typealias"


def test_label_bare_typevar_is_constant():
    """A bare `T = TypeVar("T")` has no annotation, so it labels as a constant"""
    from great_docs._apiref._render._label import get_label

    code = 'from typing import TypeVar\nT = TypeVar("T")\n'
    assert get_label(_load_member(code, "T")) == "constant"


def test_label_plain_constant_still_works():
    from great_docs._apiref._render._label import get_label

    assert get_label(_load_member("MAX: int = 3\n", "MAX")) == "constant"


@pytest.mark.parametrize("annotation", ["TypeAliasRegistry", "MyTypeAlias"])
def test_label_similarly_named_annotation_is_constant(annotation: str):
    from great_docs._apiref._render._label import get_label

    source = f"class {annotation}: pass\nvalue: {annotation}\n"
    assert get_label(_load_member(source, "value")) == "constant"


def test_from_griffe_builds_a_type_alias_node():
    from great_docs._apiref.content import Doc, DocTypeAlias

    obj = _load_member("type Contract = int | str", "Contract")
    doc = Doc.from_griffe("Contract", obj)

    assert isinstance(doc, DocTypeAlias)
    assert doc.kind == "type alias"
    assert doc.name == "Contract"
    assert doc.anchor == "package.Contract"


def _render_alias(source: str, name: str) -> str:
    """Render the named alias from a source snippet to qmd"""
    from great_docs._apiref._tools import render_code_variable

    return render_code_variable(source, name)


def test_reported_crash_no_longer_raises():
    """The reproducer from issue #288."""
    source = 'from typing import Literal\n\ntype Contract = Literal["a", "b"]\n'
    qmd = _render_alias(source, "Contract")
    assert "Contract" in qmd


@pytest.mark.parametrize(
    ("source", "name", "expected"),
    [
        (
            'from typing import Literal\ntype Contract = Literal["a", "b"]\n',
            "Contract",
            "[type]{.doc-type-alias-keyword .kw} [Contract]{.doc-parameter-name}"
            " [=]{.doc-parameter-default-sep .op}"
            " [Literal[[&quot;a&quot;]{.st}, [&quot;b&quot;]{.st}]]{.doc-parameter-default}",
        ),
        (
            "type ListOrSet[T] = list[T] | set[T]\n",
            "ListOrSet",
            "[type]{.doc-type-alias-keyword .kw} [ListOrSet[T]]{.doc-parameter-name}"
            " [=]{.doc-parameter-default-sep .op}"
            " [list[T] | set[T]]{.doc-parameter-default}",
        ),
        (
            "from typing import Callable\ntype Callback[**P] = Callable[P, int]\n",
            "Callback",
            "[type]{.doc-type-alias-keyword .kw} [Callback[**P]]{.doc-parameter-name}"
            " [=]{.doc-parameter-default-sep .op}"
            " [Callable[P, int]]{.doc-parameter-default}",
        ),
        (
            "type Bounded[T: str] = list[T]\n",
            "Bounded",
            "[type]{.doc-type-alias-keyword .kw} [Bounded[T: str]]{.doc-parameter-name}"
            " [=]{.doc-parameter-default-sep .op}"
            " [list[T]]{.doc-parameter-default}",
        ),
        (
            "type Constrained[S: (str, bytes)] = list[S]\n",
            "Constrained",
            "[type]{.doc-type-alias-keyword .kw}"
            " [Constrained[S: (str, bytes)]]{.doc-parameter-name}"
            " [=]{.doc-parameter-default-sep .op}"
            " [list[S]]{.doc-parameter-default}",
        ),
        (
            "type Variadic[T, *Ts] = tuple[T, *Ts]\n",
            "Variadic",
            "[type]{.doc-type-alias-keyword .kw} [Variadic[T, *Ts]]{.doc-parameter-name}"
            " [=]{.doc-parameter-default-sep .op}"
            " [tuple[T, *Ts]]{.doc-parameter-default}",
        ),
        pytest.param(
            "type WithDefault[T = int] = list[T]\n",
            "WithDefault",
            "[type]{.doc-type-alias-keyword .kw} [WithDefault[T = int]]{.doc-parameter-name}"
            " [=]{.doc-parameter-default-sep .op}"
            " [list[T]]{.doc-parameter-default}",
            marks=requires_pep696,
        ),
    ],
)
def test_signature_rendering(source: str, name: str, expected: str):
    assert expected in _render_alias(source, name)


def test_type_information_preserves_alias_name():
    from unittest.mock import MagicMock, patch

    import griffe as gf

    from great_docs._apiref.typing_information import TypeInformation

    api_ref = MagicMock()
    api_ref.package = "package"
    api_ref.settings.dir = "reference"

    with (
        gf.temporary_visited_package(
            "package", {"__init__.py": "type Contract[T] = list[T]\n"}
        ) as module,
        patch("great_docs._apiref.typing_information.get_object", return_value=module),
    ):
        rendered = str(TypeInformation("package", api_ref))

    assert "[Contract[T]]{.doc-parameter-name}" in rendered


def test_type_information_lists_reexported_names():
    """Document definitions re-exported by a typing module"""
    from unittest.mock import MagicMock, patch

    import griffe as gf

    from great_docs._apiref.typing_information import TypeInformation

    api_ref = MagicMock()
    api_ref.package = "package"
    api_ref.settings.dir = "reference"

    defs = '''
    from typing import Protocol, TypeVar

    type Contract = int | str
    T = TypeVar("T")

    class Reader(Protocol):
        """A reader."""
    '''
    modules = {
        "__init__.py": "",
        "_defs.py": textwrap.dedent(defs),
        "types.py": "from ._defs import Contract, Reader, T\n",
    }

    with gf.temporary_visited_package("package", modules) as package:
        with patch(
            "great_docs._apiref.typing_information.get_object",
            return_value=package["types"],
        ):
            rendered = str(TypeInformation("package.types", api_ref))

    assert "Protocols" in rendered
    assert "Reader" in rendered
    assert "Type Variables" in rendered
    assert "T" in rendered
    assert "Type Aliases" in rendered
    assert "Contract" in rendered


def test_type_information_omits_names_imported_from_outside():
    """Omit names imported from outside the package"""
    from unittest.mock import MagicMock, patch

    import griffe as gf

    from great_docs._apiref.typing_information import TypeInformation

    api_ref = MagicMock()
    api_ref.package = "package"
    api_ref.settings.dir = "reference"

    modules = {
        "__init__.py": "",
        "types.py": "from typing import AnyStr\n",
    }

    with gf.temporary_visited_package("package", modules) as package:
        # `AnyStr` is a genuine TypeVar, so only its provenance keeps it off
        # the page; without loading `typing` the alias would go unresolved
        # and the assertion would hold for the wrong reason.
        gf.GriffeLoader(modules_collection=package.modules_collection).load("typing")
        with patch(
            "great_docs._apiref.typing_information.get_object",
            return_value=package["types"],
        ):
            rendered = str(TypeInformation("package.types", api_ref))

    assert "AnyStr" not in rendered


def test_css_class_slug_is_hyphenated():
    """A space in the class attribute would silently become two classes."""
    qmd = _render_alias("type Contract = int | str\n", "Contract")
    assert "doc-type-alias" in qmd
    assert "doc-type alias" not in qmd


def test_label_class_is_emitted():
    """The label class matches the existing `.doc-label-typealias` scss rule."""
    qmd = _render_alias("type Contract = int | str\n", "Contract")
    assert "doc-label-typealias" in qmd


def test_docstring_is_rendered():
    source = 'type Contract = int | str\n"""A contract kind."""\n'
    assert "A contract kind." in _render_alias(source, "Contract")


def test_recursive_alias_renders():
    """Lazy evaluation means the value is never resolved, so this must not raise."""
    qmd = _render_alias("type Recursive = Recursive | None\n", "Recursive")
    assert "[Recursive | None]{.doc-parameter-default}" in qmd


def test_forward_reference_alias_renders():
    """The static `.value` expression is unresolved, so an undefined name is fine."""
    qmd = _render_alias("type Broken = NotDefinedAnywhere\n", "Broken")
    assert "NotDefinedAnywhere" in qmd


def test_valueless_alias_omits_default_clause():
    """A `TypeAlias` with no `.value` must not render the literal string 'None'.

    `type X = ...` always has a value when parsed from source, so this state
    is constructed directly rather than via `_render_alias`.
    """
    import griffe as gf

    from great_docs._apiref._render import get_render_type
    from great_docs._apiref.content import Doc

    obj = gf.TypeAlias(name="Empty", lineno=1)
    assert obj.value is None

    doc = Doc.from_griffe("Empty", obj)
    qmd = str(get_render_type(doc)(doc, 1))

    assert "None" not in qmd
    assert "doc-parameter-default-sep" not in qmd


def test_type_alias_group_renders_in_a_class():
    """A type alias declared in a class must not be silently dropped"""
    import textwrap

    from great_docs._apiref._tools import render_code_variable

    source = textwrap.dedent('''
        class Holder:
            """A holder."""

            type Inner = int
            """An inner alias."""

            size: int = 3
            """The size."""
    ''')
    qmd = render_code_variable(source, "Holder")

    assert "Inner" in qmd
    assert "An inner alias." in qmd


def test_type_alias_group_has_its_own_heading():
    import textwrap

    from great_docs._apiref._tools import render_code_variable

    source = textwrap.dedent('''
        class Holder:
            """A holder."""

            type Inner = int
            """An inner alias."""
    ''')
    qmd = render_code_variable(source, "Holder")

    assert "Type Aliases" in qmd
    assert "doc-type-aliases" in qmd


def test_exclude_type_aliases_removes_the_member_from_the_output():
    """`exclude_type_aliases` must keep an excluded alias out of the rendered qmd"""
    import textwrap

    from great_docs._apiref._globals import EXCLUSIONS
    from great_docs._apiref._render.extending import exclude_type_aliases
    from great_docs._apiref._tools import render_code_variable

    source = textwrap.dedent('''
        class Holder:
            """A holder."""

            type Kept = str
            """A kept alias."""

            type Dropped = int
            """A dropped alias."""
    ''')

    # Without the exclusion both aliases are rendered
    assert "Dropped" in render_code_variable(source, "Holder")

    original = dict(EXCLUSIONS.type_aliases)
    try:
        exclude_type_aliases({"package.Holder": "Dropped"})
        qmd = render_code_variable(source, "Holder")
    finally:
        EXCLUSIONS.type_aliases.clear()
        EXCLUSIONS.type_aliases.update(original)

    assert "A kept alias." in qmd
    assert "Dropped" not in qmd
    assert "A dropped alias." not in qmd


def test_type_alias_group_precedes_attributes():
    import textwrap

    from great_docs._apiref._tools import render_code_variable

    source = textwrap.dedent('''
        class Holder:
            """A holder."""

            type Inner = int
            """An inner alias."""

            size: int = 3
            """The size."""
    ''')
    qmd = render_code_variable(source, "Holder")

    assert qmd.index("Type Aliases") < qmd.index("Attributes")


def test_existing_group_headings_unchanged():
    """The shared title expression must not alter the other groups' headings"""
    import textwrap

    from great_docs._apiref._tools import render_code_variable

    source = textwrap.dedent('''
        class Holder:
            """A holder."""

            size: int = 3
            """The size."""

            def go(self) -> None:
                """Go."""
    ''')
    qmd = render_code_variable(source, "Holder")

    assert "Attributes" in qmd
    assert "Methods" in qmd
    assert "Type Aliases" not in qmd


def test_module_level_type_alias_group():
    from great_docs._apiref._tools import render_code_variable

    source = 'type Contract = int | str\n"""A contract."""\n'
    qmd = render_code_variable(source, None)

    assert "Type Aliases" in qmd
    assert "Contract" in qmd


def test_inventory_role_for_type_alias():
    from great_docs._apiref.inventory import InventoryItem, _create_inventory_item

    obj = _load_member("type Contract = int | str\n", "Contract")
    entry = _create_inventory_item(InventoryItem(obj=obj, name="package.Contract"))

    assert entry["role"] == "type"


def test_inventory_roles_never_contain_spaces():
    from great_docs._apiref.inventory import InventoryItem, _create_inventory_item

    code = "type Contract = int | str\ndef f(): ...\nclass C: ...\nMAX: int = 3\n"
    for name in ("Contract", "f", "C", "MAX"):
        obj = _load_member(code, name)
        entry = _create_inventory_item(InventoryItem(obj=obj, name=name))
        assert " " not in entry["role"]


def test_api_reference_builds_with_a_type_alias(monkeypatch, tmp_path):
    """The full issue #288 path: APIReference.build() over a package with an alias

    `APIReference.build` writes to disk and returns `None` rather than handing
    back pages, so the build is proven by the files it writes and by the
    `type alias` kind showing up among the collected `items` — not by a
    return value.
    """
    from great_docs._apiref.api_reference import APIReference

    pkg = tmp_path / "gdta_build"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        "from typing import Literal\n\n"
        'type Contract = Literal["a", "b"]\n'
        '"""A contract kind."""\n\n\n'
        "def f(c: Contract) -> None:\n"
        '    """Do a thing."""\n'
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)

    ref = APIReference(
        {
            "package": "gdta_build",
            "sections": [{"title": "All", "desc": "d", "contents": ["Contract", "f"]}],
        }
    )
    ref.build()

    assert (tmp_path / "reference" / "index.qmd").exists()
    contract_qmd = (tmp_path / "reference" / "Contract.qmd").read_text()
    assert "A contract kind." in contract_qmd
    assert "doc-type-alias" in contract_qmd
    assert "doc-label-typealias" in contract_qmd
    assert (
        "[type]{.doc-type-alias-keyword .kw} [Contract]{.doc-parameter-name}"
        " [=]{.doc-parameter-default-sep .op}"
        " [Literal[[&quot;a&quot;]{.st}, [&quot;b&quot;]{.st}]]{.doc-parameter-default}"
        in contract_qmd
    )
    kinds = {item.obj.kind.value for item in ref.items}
    assert "type alias" in kinds


def test_inventory_roles_unchanged_for_other_kinds():
    from great_docs._apiref.inventory import InventoryItem, _create_inventory_item

    code = "def f(): ...\nclass C: ...\nMAX: int = 3\n"
    expected = {"f": "function", "C": "class", "MAX": "attribute"}
    for name, role in expected.items():
        obj = _load_member(code, name)
        entry = _create_inventory_item(InventoryItem(obj=obj, name=name))
        assert entry["role"] == role
