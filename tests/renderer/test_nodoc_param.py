"""Parameter exclusion through resolution and rendered documentation"""

from __future__ import annotations

import re
from pathlib import Path
from textwrap import dedent

import griffe as gf
import pytest

from great_docs._apiref._constructor import parse_class_docstring
from great_docs._apiref._parameter_docs import (
    CallableDocumentation,
    ParameterDirectiveError,
    filter_parameter_sections,
)
from great_docs._apiref._settings import CallableSignatures, Settings
from great_docs._apiref._tools import _render
from great_docs.hooks._docstring_parsed import emit_docstring_parsed
from great_docs.hooks._object_resolved import emit_object_resolved


def _function(doc: str = "%nodoc_param old") -> gf.Function:
    """Build a callable with a retained and a deprecated parameter"""
    obj = gf.Function(
        "configure",
        parameters=gf.Parameters(gf.Parameter("value"), gf.Parameter("old", default="None")),
    )
    obj.docstring = gf.Docstring(doc, parent=obj, parser="numpy")
    return obj


def _rendered(obj: gf.Object | gf.Alias, style: str = "highlighted") -> str:
    """Render a callable through the documentation hooks"""
    assert emit_object_resolved(obj) is obj
    if obj.docstring is not None:
        if obj.is_class:
            parse_class_docstring(obj)
        emit_docstring_parsed(obj)
    return _render(obj, Settings(callable_signatures=CallableSignatures(style=style)))


def _signature(qmd: str) -> str:
    """Extract the highlighted signature from generated documentation"""
    match = re.search(r"```pythonsignature\n(.*?)\n```", qmd, re.DOTALL)
    assert match is not None, qmd
    return match.group(1)


def test_directive_is_stripped_without_changing_signature() -> None:
    obj = _function("Configure values\n\n%nodoc_param old\n%nodoc_param old")
    original = obj.parameters
    for _ in range(2):
        assert emit_object_resolved(obj) is obj
        assert obj.docstring is not None
        assert obj.docstring.value == "Configure values"
        assert CallableDocumentation.make(obj).excluded_names == {"old"}
        assert obj.parameters is original
        assert [p.name for p in obj.parameters] == ["value", "old"]


@pytest.mark.parametrize("name", ["", "old value", "old,value", "*old", "for", "missing"])
def test_invalid_declarations_fail(name: str) -> None:
    obj = _function(f"%nodoc_param {name}")
    with pytest.raises(ParameterDirectiveError, match="configure: %nodoc_param"):
        emit_object_resolved(obj)


@pytest.mark.parametrize("declaration", ["%nodoc_param(old)", "%nodoc_param=old"])
def test_attached_directive_arguments_are_invalid(declaration: str) -> None:
    with pytest.raises(ParameterDirectiveError, match="one bare Python parameter name"):
        emit_object_resolved(_function(declaration))


@pytest.mark.parametrize("fence", ["```", "~~~"])
def test_fenced_directive_stays_literal(fence: str) -> None:
    doc = f"Example\n\n{fence}text\n%nodoc_param missing\n{fence}"
    obj = _function(doc)
    assert emit_object_resolved(obj) is obj
    assert obj.docstring is not None
    assert obj.docstring.value == doc
    assert not CallableDocumentation.make(obj).excluded_names


@pytest.mark.parametrize("alias_first", [True, False])
def test_alias_and_target_keep_the_same_exclusions(alias_first: bool) -> None:
    module = gf.Module("package")
    target = _function()
    module.set_member("configure", target)
    alias = gf.Alias("alias", target, parent=module)
    objects = [alias, target] if alias_first else [target, alias]
    for obj in objects * 2:
        assert emit_object_resolved(obj) is obj
        assert CallableDocumentation.make(obj).excluded_names == {"old"}


def test_nodoc_discards_object_before_parameter_validation() -> None:
    obj = _function("%nodoc\n%nodoc_param missing")
    assert emit_object_resolved(obj) is None


@pytest.mark.parametrize("style", ["highlighted", "plain"])
def test_signature_excludes_parameter_in_each_style(style: str) -> None:
    qmd = _rendered(_function("Configure values\n\n%nodoc_param old"), style)
    assert "old" not in qmd
    if style == "highlighted":
        assert _signature(qmd) == "configure(value)"
    else:
        assert "[value]{.doc-parameter-name}" in qmd


@pytest.mark.parametrize(
    ("signature", "excluded", "expected"),
    [
        ("x, /, old=None", "old", "f(x, /)"),
        ("old, /, *, x=1", "old", "f(*, x=1)"),
        ("x, *args, y=1, **kwargs", "args", "f(x, *, y=1, **kwargs)"),
        ("x, *, old=1", "old", "f(x)"),
        ("*args, **kwargs", "kwargs", "f(*args)"),
        ("old=None", "old", "f()"),
    ],
)
def test_parameter_kind_separators(signature: str, excluded: str, expected: str) -> None:
    source = f'def f({signature}):\n    """\n    Call f\n\n    %nodoc_param {excluded}\n    """\n'
    settings = Settings(callable_signatures=CallableSignatures(wrap="width"))
    with gf.temporary_visited_package("package", {"__init__.py": source}) as module:
        obj = module["f"]
        assert emit_object_resolved(obj) is obj
        assert _signature(_render(obj, settings)) == expected


def test_overloads_are_filtered_independently_without_mutation() -> None:
    source = '''
    from typing import overload
    @overload
    def f(value: int, old: bool = False) -> int: ...
    @overload
    def f(value: str) -> str: ...
    def f(*args, **kwargs):
        """
        Convert a value

        %nodoc_param old
        """
    '''
    with gf.temporary_visited_package("package", {"__init__.py": dedent(source)}) as module:
        obj = module["f"]
        before = [[p.name for p in ov.parameters] for ov in obj.overloads]
        assert _signature(_rendered(obj)) == "f(value: int) -> int\nf(value: str) -> str"
        assert [[p.name for p in ov.parameters] for ov in obj.overloads] == before
        assert [p.name for p in obj.parameters] == ["args", "kwargs"]


@pytest.mark.parametrize("method", ["instance", "class", "static"])
def test_methods_exclude_only_the_requested_parameter(method: str) -> None:
    prefix = {"instance": "", "class": "@classmethod\n", "static": "@staticmethod\n"}[method]
    receiver = {"instance": "self, ", "class": "cls, ", "static": ""}[method]
    source = "class C:\n" + "\n".join(
        "    " + line
        for line in (
            f"{prefix}def f({receiver}value, old=None):\n"
            '    """\n    Configure values\n\n    %nodoc_param old\n    """\n'
        ).splitlines()
    )
    with gf.temporary_visited_package("package", {"__init__.py": source}) as module:
        assert _signature(_rendered(module["C"]["f"])) == "f(value)"


@pytest.mark.parametrize("constructor", ["__init__", "__new__"])
@pytest.mark.parametrize("class_doc", [True, False])
def test_class_uses_constructor_directives_without_documenting_constructor(
    constructor: str, class_doc: bool
) -> None:
    doc = '"""Build values"""' if class_doc else ""
    source = f'''
    class C:
        {doc}
        def {constructor}(self, value, old=None):
            """
            Build values

            %nodoc_param old
            """
    '''
    with gf.temporary_visited_package("package", {"__init__.py": dedent(source)}) as module:
        assert _signature(_rendered(module["C"])) == "C(value)"
        assert [p.name for p in module["C"][constructor].parameters] == ["self", "value", "old"]


def test_subclass_exclusions_do_not_affect_inherited_constructor() -> None:
    source = '''
    class Base:
        def __init__(self, value, old=None): ...
    class Hidden(Base):
        """
        Build values

        %nodoc_param old
        """
    class Visible(Base):
        """Build values"""
    '''
    with gf.temporary_visited_package("package", {"__init__.py": dedent(source)}) as module:
        assert _signature(_rendered(module["Hidden"])) == "Hidden(value)"
        assert "old=None" in _signature(_rendered(module["Visible"]))
        assert [p.name for p in module["Base"]["__init__"].parameters] == ["self", "value", "old"]


@pytest.mark.parametrize(
    ("parser", "section"),
    [
        (
            "numpy",
            "Parameters\n----------\nvalue\n    Retained description.\nold\n    Excluded description.",
        ),
        ("google", "Args:\n    value: Retained description.\n    old: Excluded description."),
        ("sphinx", ":param value: Retained description.\n:param old: Excluded description."),
    ],
)
def test_parameter_descriptions_use_the_complete_signature(parser: str, section: str) -> None:
    obj = _function()
    obj.parameters["value"].annotation = "int"
    obj.parameters["value"].default = "3"
    obj.parameters["old"].annotation = "str"
    obj.docstring = gf.Docstring(
        f"Configure values\n\n%nodoc_param old\n\n{section}\n", parent=obj, parser=parser
    )
    qmd = _rendered(obj)
    assert "Retained description." in qmd
    assert "Excluded description." not in qmd
    assert obj.docstring is not None
    [parameters] = [s for s in obj.docstring.parsed if isinstance(s, gf.DocstringSectionParameters)]
    assert parameters.value[0].annotation == "int"
    assert parameters.value[0].value == "3"
    assert [p.name for p in obj.parameters] == ["value", "old"]


def test_grouped_and_other_parameter_sections_are_copied_and_filtered() -> None:
    grouped = gf.DocstringParameter(
        "value, old", description="Shared description", annotation="int"
    )
    excluded = gf.DocstringParameter("**kwargs", description="Hidden keywords")
    sections = [
        gf.DocstringSectionParameters([grouped]),
        gf.DocstringSectionOtherParameters([excluded]),
    ]
    filtered = filter_parameter_sections(sections, frozenset({"old", "kwargs"}))
    assert len(filtered) == 1
    assert filtered[0].value[0].name == "value"
    assert filtered[0].value[0].annotation == "int"
    assert grouped.name == "value, old"
    assert sections[1].value == [excluded]


def test_empty_parameter_section_disappears_but_deprecation_prose_remains() -> None:
    obj = _function(
        "Configure values\n\n%nodoc_param old\n\n"
        "Parameters\n----------\nold : str\n    Excluded description.\n\n"
        "Notes\n-----\nThe previous spelling is deprecated.\n"
    )
    qmd = _rendered(obj)
    assert "## Parameters" not in qmd
    assert "Excluded description." not in qmd
    assert "The previous spelling is deprecated." in qmd


def test_dataclass_fields_do_not_reappear_as_attributes() -> None:
    from great_docs._apiref._render.docclass import RenderDocClass
    from great_docs._apiref.content import Doc

    source = '''
    from dataclasses import InitVar, dataclass
    @dataclass
    class C:
        """
        Configure values

        %nodoc_param old
        %nodoc_param init_old
        """
        value: int = 1
        'Retained field description'
        old: int = 2
        'Excluded field description'
        init_old: InitVar[int] = 3
        'Excluded init description'
    '''
    with gf.temporary_visited_package(
        "package", {"__init__.py": dedent(source)}, docstring_parser="numpy"
    ) as module:
        obj = module["C"]
        qmd = _rendered(obj)
        members = [Doc.from_griffe(name, attribute) for name, attribute in obj.attributes.items()]
        node = Doc.from_griffe("C", obj, members)
        renderer = RenderDocClass(node, settings=Settings())
        assert not renderer.attributes
        assert "Retained field description" in qmd
        assert "Excluded field description" not in qmd
        assert "Excluded init description" not in qmd
        assert "old" not in _signature(qmd)
        assert "## Init Parameters" not in qmd
        assert {p.name for p in obj.parameters} == {"self", "value", "old", "init_old"}


def test_class_and_constructor_exclusions_are_combined() -> None:
    source = '''
    class C:
        """
        Configure values

        %nodoc_param old

        Parameters
        ----------
        value
            Retained description.
        old
            Hidden class parameter.
        older
            Hidden constructor parameter.
        """
        def __init__(self, value: int, old=None, older=None):
            """
            Configure values

            %nodoc_param older
            """
    '''
    with gf.temporary_visited_package(
        "package", {"__init__.py": dedent(source)}, docstring_parser="numpy"
    ) as module:
        cls = module["C"]
        qmd = _rendered(cls)
        assert _signature(qmd) == "C(value)"
        assert "Hidden class parameter." not in qmd
        assert "Hidden constructor parameter." not in qmd
        assert "older" not in _signature(_rendered(cls["__init__"]))
        assert "old=None" in _signature(_rendered(cls["__init__"]))


def test_overload_only_constructor_uses_class_exclusions(tmp_path: Path) -> None:
    source = '''
    from typing import overload
    class C:
        """
        Configure values

        %nodoc_param old
        """
        @overload
        def __new__(cls, value: int, old=None) -> C: ...
        @overload
        def __new__(cls, value: str, old=None) -> C: ...
    '''
    package = tmp_path / "stub_params"
    package.mkdir()
    (package / "__init__.pyi").write_text(dedent(source))
    module = gf.load("stub_params", search_paths=[tmp_path], allow_inspection=False)
    cls = module["C"]
    assert _signature(_rendered(cls)) == "C(value: int)\nC(value: str)"
    assert all("old" in ov.parameters for ov in cls.overloads["__new__"])


@pytest.mark.parametrize("receiver", ["self", "cls"])
def test_implicit_receivers_cannot_be_excluded(receiver: str) -> None:
    module = gf.Module("package")
    cls = gf.Class("C", parent=module)
    obj = gf.Function("f", parent=cls, parameters=gf.Parameters(gf.Parameter(receiver)))
    obj.docstring = gf.Docstring(f"%nodoc_param {receiver}", parent=obj)
    with pytest.raises(ParameterDirectiveError, match=receiver):
        emit_object_resolved(obj)


def test_explicit_attributes_section_remains_visible() -> None:
    source = '''
    from dataclasses import dataclass
    @dataclass
    class C:
        """
        Configure values

        %nodoc_param old

        Attributes
        ----------
        old
            Public attribute description.
        """
        old: int = 1
    '''
    with gf.temporary_visited_package(
        "package", {"__init__.py": dedent(source)}, docstring_parser="numpy"
    ) as module:
        qmd = _rendered(module["C"])
        assert _signature(qmd) == "C()"
        assert "Public attribute description." in qmd


@pytest.mark.parametrize(
    ("parameters", "excluded", "expected"),
    [
        ("old, self", "old", "f(self)"),
        ("self, old", "old", "f(self)"),
        ("self, old", "self", "f(old)"),
    ],
)
def test_static_parameter_names_do_not_become_receivers(
    parameters: str, excluded: str, expected: str
) -> None:
    source = (
        "class C:\n    @staticmethod\n"
        f'    def f({parameters}):\n        """\n        Configure values\n\n'
        f'        %nodoc_param {excluded}\n        """\n'
    )
    with gf.temporary_visited_package("package", {"__init__.py": source}) as module:
        assert _signature(_rendered(module["C"]["f"])) == expected


def test_overloaded_methods_keep_only_explicit_retained_parameters() -> None:
    source = '''
    from typing import overload
    class C:
        @overload
        def f(self, value: int, old=None) -> int: ...
        @overload
        def f(self, value: str, old=None) -> str: ...
        def f(self, value, old=None):
            """
            Configure values

            %nodoc_param old
            """
    '''
    with gf.temporary_visited_package("package", {"__init__.py": dedent(source)}) as module:
        assert (
            _signature(_rendered(module["C"]["f"])) == "f(value: int) -> int\nf(value: str) -> str"
        )
