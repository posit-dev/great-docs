"""Tests for docstring section rendering and dispatch."""

from __future__ import annotations

import sys
import textwrap

import pytest

requires_pep695 = pytest.mark.skipif(
    sys.version_info < (3, 12),
    reason="PEP 695 `type` statement and type-parameter syntax require Python 3.12+",
)


def _render(source: str, name: str | None) -> str:
    """Render the named object from a source snippet to qmd"""
    from great_docs._apiref._tools import render_code_variable

    return render_code_variable(textwrap.dedent(source), name)


def test_examples_section_renders_code_and_prose():
    """
    An `Examples` section interleaves prose and code fragments

    `render_examples_section` is defined on every renderer, so this must never
    fall through to the unhandled-section path, which only logs and drops
    content.
    """
    source = '''
        def f():
            """
            Do a thing.

            Examples
            --------
            Some explanatory prose.

            >>> f()
            3
            """
    '''
    qmd = _render(source, "f")

    assert "Some explanatory prose." in qmd
    assert "f()" in qmd
    assert "object at 0x" not in qmd


def test_example_fragment_renders_directly():
    """`_render_example_fragment` handles a fragment without re-entering dispatch"""
    from great_docs._apiref._docstring_sections import ExampleCode, ExampleText
    from great_docs._apiref._render.doc import __RenderDoc as RenderDocImpl  # noqa: N813

    render = object.__new__(RenderDocImpl)

    assert "x = 1" in str(render._render_example_fragment(ExampleCode("x = 1")))
    assert render._render_example_fragment(ExampleText("hello")) == "hello"


def test_section_method_table_covers_every_griffe_section_kind():
    """
    Every griffe section kind maps to a renderer or to deliberate suppression

    A kind missing from the table degrades to a logged warning and no output,
    so the table is what keeps a griffe upgrade from silently dropping content.
    """
    import griffe as gf

    from great_docs._apiref._render._section_dispatch import SECTION_METHOD

    covered = {getattr(t, "kind", None) for t in SECTION_METHOD}
    missing = {kind for kind in gf.DocstringSectionKind if kind not in covered}

    assert not missing, f"griffe section kinds absent from SECTION_METHOD: {missing}"


def test_section_method_values_are_method_names():
    """Every value in `SECTION_METHOD` is a non-empty method name, not a callable or `None`"""
    from great_docs._apiref._render._section_dispatch import SECTION_METHOD

    assert all(isinstance(name, str) and name for name in SECTION_METHOD.values())


def test_parameters_section_on_a_module_is_not_rendered(caplog):
    """
    A module has no parameters, so the section has no renderer and is omitted

    `RenderDocModule` does not inherit `RenderDocCallMixin`. Before table
    dispatch it reached the mixin's handler anyway, because
    `singledispatchmethod` shared one registry across every subclass.
    """
    source = '''
        """
        A module.

        Parameters
        ----------
        x :
            Not a real thing.
        """
    '''
    with caplog.at_level("WARNING"):
        qmd = _render(source, None)

    assert "Not a real thing." not in qmd
    assert "object at 0x" not in qmd
    assert any("no renderer" in r.message for r in caplog.records)


def test_parameters_section_on_a_class_still_renders():
    """The mixin's method is still reachable from the classes that inherit it"""
    source = '''
        class Widget:
            """
            A widget.

            Parameters
            ----------
            size :
                How big.
            """

            def __init__(self, size: int): ...
    '''
    qmd = _render(source, "Widget")

    assert "How big." in qmd


def test_definition_section_without_items_renders_nothing():
    """
    Verify that empty `Parameters` and `Returns` sections produce no output

    griffe drops empty sections during parsing. Hooks and renderer subclasses
    can still supply them directly to the renderer.
    """
    import griffe as gf

    from great_docs._apiref._render.doc import __RenderDoc as RenderDocImpl  # noqa: N813

    render = object.__new__(RenderDocImpl)

    assert render.render_definition_items(gf.DocstringSectionParameters([])) is None
    assert render.render_definition_items(gf.DocstringSectionReturns([])) is None


def test_methods_section_is_dropped_silently(caplog):
    """Deliberate suppression must not warn — `Methods` is valid numpydoc"""
    source = '''
        class Widget:
            """
            A widget.

            Methods
            -------
            go(x)
                Do the thing.
            """

            def go(self, x): ...
    '''
    with caplog.at_level("WARNING"):
        qmd = _render(source, "Widget")

    assert "Do the thing." not in qmd
    assert not [r for r in caplog.records if "no renderer" in r.message]


def test_type_aliases_section_is_dropped_silently(caplog):
    """
    A hand-written `Type Aliases` section is a member summary, so it is dropped

    It restates what the real type-alias members already provide, so
    `render_type_aliases_section` drops it without a warning, the same as
    `render_functions_section` (which also covers `Methods`),
    `render_classes_section` and `render_modules_section`.
    """
    source = '''
        class Holder:
            """
            A holder.

            Type Aliases
            ------------
            Handwritten : int | str
                A hand-written summary.
            """
    '''
    with caplog.at_level("WARNING"):
        qmd = _render(source, "Holder")

    assert "Handwritten" not in qmd
    assert "A hand-written summary." not in qmd
    assert "object at 0x" not in qmd
    assert not [r for r in caplog.records if "no renderer" in r.message]


def test_functions_section_on_a_module_is_dropped_silently(caplog):
    """A hand-written `Functions` section on a module is dropped, not warned about"""
    source = '''
        """
        A module.

        Functions
        ---------
        helper(x)
            Do the thing.
        """
    '''
    with caplog.at_level("WARNING"):
        qmd = _render(source, None)

    assert "Do the thing." not in qmd
    assert "object at 0x" not in qmd
    assert not [r for r in caplog.records if "no renderer" in r.message]


def test_classes_section_on_a_module_is_dropped_silently(caplog):
    """A hand-written `Classes` section on a module is dropped, not warned about"""
    source = '''
        """
        A module.

        Classes
        -------
        Thing
            Do the thing.
        """
    '''
    with caplog.at_level("WARNING"):
        qmd = _render(source, None)

    assert "Do the thing." not in qmd
    assert "object at 0x" not in qmd
    assert not [r for r in caplog.records if "no renderer" in r.message]


def test_suppression_methods_are_independently_overridable():
    """
    Overriding one suppression method must not affect the other three

    The four suppressed section kinds (`Functions`/`Methods`, `Classes`,
    `Modules`, `Type Aliases`) share only the private `_suppress_section`
    helper, not a single dispatched method, so overriding
    `render_type_aliases_section` on a subclass must leave `Methods`
    (`render_functions_section`) dropped as before.

    Subclassing a public `Render*` class outside `great_docs` normally
    triggers `RenderBase.__init_subclass__`, which copies the subclass's
    attributes onto its immediate base class (`extend_base_class`) so that
    user overrides "fill in" the package's internal classes everywhere. That
    is a deliberate feature for real usage, but here it would leak a
    test-only override into global state and affect unrelated tests. It is
    neutralised for the duration of this test by patching
    `extend_base_class` to a no-op, so the subclass created below stays
    local to this test.
    """
    import great_docs._apiref._render.base as base_module
    from great_docs._apiref import RenderDocClass

    original_extend_base_class = base_module.extend_base_class
    base_module.extend_base_class = lambda cls: None
    try:

        class _MarkedRenderDocClass(RenderDocClass):
            def render_type_aliases_section(self, el):
                return "MARKER"

    finally:
        base_module.extend_base_class = original_extend_base_class

    render = object.__new__(_MarkedRenderDocClass)

    import griffe as gf

    assert render.render_docstring_section(gf.DocstringSectionTypeAliases([])) == "MARKER"
    assert render.render_docstring_section(gf.DocstringSectionFunctions([])) is None


def test_raises_section_on_a_property_still_renders(caplog):
    """
    A `Raises` section on a property renders, same as on a function

    `RenderDocAttribute` renders properties and plain attributes alike, and
    does not inherit the call mixin that defines `render_raises_section` for
    functions and classes. A `Raises` section is still ordinary, valid
    numpydoc on a property, so it must render rather than fall through to the
    unhandled-section path.
    """
    source = '''
        class Widget:
            """A widget."""

            @property
            def size(self):
                """
                The size.

                Raises
                ------
                ValueError
                    If the size cannot be determined.
                """
    '''
    with caplog.at_level("WARNING"):
        qmd = _render(source, "Widget.size")

    assert "If the size cannot be determined." in qmd
    assert "object at 0x" not in qmd
    assert not [r for r in caplog.records if "no renderer" in r.message]


def test_warns_section_on_a_property_still_renders(caplog):
    """A `Warns` section on a property renders, same as `Raises`"""
    source = '''
        class Widget:
            """A widget."""

            @property
            def size(self):
                """
                The size.

                Warns
                -----
                UserWarning
                    If the size is guessed.
                """
    '''
    with caplog.at_level("WARNING"):
        qmd = _render(source, "Widget.size")

    assert "If the size is guessed." in qmd
    assert "object at 0x" not in qmd
    assert not [r for r in caplog.records if "no renderer" in r.message]


def test_yields_section_on_a_property_still_renders(caplog):
    """A `Yields` section on a property renders, same as `Raises`"""
    source = '''
        class Widget:
            """A widget."""

            @property
            def size(self):
                """
                The size.

                Yields
                ------
                int
                    Each candidate size.
                """
    '''
    with caplog.at_level("WARNING"):
        qmd = _render(source, "Widget.size")

    assert "Each candidate size." in qmd
    assert "object at 0x" not in qmd
    assert not [r for r in caplog.records if "no renderer" in r.message]


def test_yields_and_receives_sections_on_a_property_both_render(caplog):
    """
    `Yields` and `Receives` are a mandatory pair, and both must render

    numpydoc requires `Receives` to be documented together with `Yields`
    since it describes what the same generator accepts via `.send()`. A
    property documenting both must render both halves, not just `Yields`.
    """
    source = '''
        class Widget:
            """A widget."""

            @property
            def size(self):
                """
                The size.

                Yields
                ------
                int
                    Each candidate size.

                Receives
                --------
                float
                    A scale factor to apply.
                """
    '''
    with caplog.at_level("WARNING"):
        qmd = _render(source, "Widget.size")

    assert "Each candidate size." in qmd
    assert "A scale factor to apply." in qmd
    assert "object at 0x" not in qmd
    assert not [r for r in caplog.records if "no renderer" in r.message]


def test_raises_section_on_a_typevar_annotated_property_still_renders(caplog):
    """
    A `Raises` section on a property still renders even if mislabelled

    `get_label` runs annotation heuristics before it checks for the
    `property` label, so a property whose return annotation stringifies to
    contain `TypeVar` gets the label `"typevar"`, not `"property"`.
    `_render_property_only_section` must gate on the griffe fact
    (`"property" in obj.labels`), not on `self.label`, or this case falls
    through to the unhandled-section path and silently drops the section.
    """
    source = '''
        from typing import TypeVar

        class Widget:
            """A widget."""

            @property
            def factory(self) -> TypeVar:
                """
                The factory.

                Raises
                ------
                ValueError
                    If no factory is available.
                """
    '''
    with caplog.at_level("WARNING"):
        qmd = _render(source, "Widget.factory")

    assert "If no factory is available." in qmd
    assert "object at 0x" not in qmd
    assert not [r for r in caplog.records if "no renderer" in r.message]


def test_receives_section_on_a_plain_attribute_is_unhandled(caplog):
    """
    A `Receives` section on a plain data attribute is a mistake, not content

    A plain attribute is not a generator, so it cannot receive anything via
    `.send()`. Unlike a property, it must take the unhandled-section path:
    nothing rendered, and a warning logged.
    """
    source = '''
        class Widget:
            """A widget."""

            size: int = 3
            """
            The size.

            Receives
            --------
            float
                A scale factor to apply.
            """
    '''
    with caplog.at_level("WARNING"):
        qmd = _render(source, "Widget.size")

    assert "A scale factor to apply." not in qmd
    assert "object at 0x" not in qmd
    assert any("no renderer" in r.message for r in caplog.records)


def test_raises_section_on_a_plain_attribute_is_unhandled(caplog):
    """
    A `Raises` section on a plain data attribute is a mistake, not content

    A plain attribute executes no code on access, so it cannot raise. Unlike
    a property, it must take the unhandled-section path: nothing rendered,
    and a warning logged.
    """
    source = '''
        class Widget:
            """A widget."""

            size: int = 3
            """
            The size.

            Raises
            ------
            ValueError
                If the size cannot be determined.
            """
    '''
    with caplog.at_level("WARNING"):
        qmd = _render(source, "Widget.size")

    assert "If the size cannot be determined." not in qmd
    assert "object at 0x" not in qmd
    assert any("no renderer" in r.message for r in caplog.records)


def test_warns_section_on_a_plain_attribute_is_unhandled(caplog):
    """
    A `Warns` section on a plain data attribute is a mistake, not content

    A plain attribute executes no code on access, so it cannot warn. Unlike
    a property, it must take the unhandled-section path: nothing rendered,
    and a warning logged.
    """
    source = '''
        class Widget:
            """A widget."""

            size: int = 3
            """
            The size.

            Warns
            -----
            UserWarning
                If the size is guessed.
            """
    '''
    with caplog.at_level("WARNING"):
        qmd = _render(source, "Widget.size")

    assert "If the size is guessed." not in qmd
    assert "object at 0x" not in qmd
    assert any("no renderer" in r.message for r in caplog.records)


def test_yields_section_on_a_plain_attribute_is_unhandled(caplog):
    """
    A `Yields` section on a plain data attribute is a mistake, not content

    A plain attribute is not a generator, so it cannot yield anything. Unlike
    a property, it must take the unhandled-section path: nothing rendered,
    and a warning logged.
    """
    source = '''
        class Widget:
            """A widget."""

            size: int = 3
            """
            The size.

            Yields
            ------
            int
                Each candidate size.
            """
    '''
    with caplog.at_level("WARNING"):
        qmd = _render(source, "Widget.size")

    assert "Each candidate size." not in qmd
    assert "object at 0x" not in qmd
    assert any("no renderer" in r.message for r in caplog.records)


def test_property_only_section_methods_are_independently_overridable():
    """
    Overriding one property-only section method must not affect the others

    `render_raises_section`, `render_warns_section`, `render_yields_section`
    and `render_receives_section` on `RenderDocAttribute` all delegate to the
    shared `_render_property_only_section` helper rather than to one
    dispatched method, so overriding `render_raises_section` on a subclass
    must leave `render_warns_section` rendering normally.

    Subclassing a public `Render*` class outside `great_docs` normally
    triggers `RenderBase.__init_subclass__`, which copies the subclass's
    attributes onto its immediate base class (`extend_base_class`) so that
    user overrides "fill in" the package's internal classes everywhere. That
    is a deliberate feature for real usage, but here it would leak a
    test-only override into global state and affect unrelated tests. It is
    neutralised for the duration of this test by patching
    `extend_base_class` to a no-op, so the subclass created below stays
    local to this test.
    """
    import great_docs._apiref._render.base as base_module
    from great_docs._apiref import RenderDocAttribute

    original_extend_base_class = base_module.extend_base_class
    base_module.extend_base_class = lambda cls: None
    try:

        class _MarkedRenderDocAttribute(RenderDocAttribute):
            def render_raises_section(self, el):
                return "MARKER"

    finally:
        base_module.extend_base_class = original_extend_base_class

    source = '''
        class Widget:
            """A widget."""

            @property
            def size(self):
                """
                The size.

                Raises
                ------
                ValueError
                    If the size cannot be determined.

                Warns
                -----
                UserWarning
                    If the size is guessed.
                """
    '''

    import great_docs._apiref._render as render_module
    from great_docs._apiref.content import DocAttribute

    original_render_doc_attribute = render_module._class_mapping[DocAttribute]
    render_module._class_mapping[DocAttribute] = _MarkedRenderDocAttribute
    try:
        qmd = _render(source, "Widget.size")
    finally:
        render_module._class_mapping[DocAttribute] = original_render_doc_attribute

    assert "MARKER" in qmd
    assert "If the size is guessed." in qmd


def test_every_table_entry_names_a_real_method():
    """
    A misspelt method name in `SECTION_METHOD` degrades to a silent warning

    Nothing raises when a name is wrong — the section is simply dropped and a
    warning is logged — so this is the only check that catches a rename.
    """
    from great_docs._apiref import (
        RenderDocAttribute,
        RenderDocClass,
        RenderDocFunction,
        RenderDocModule,
        RenderDocTypeAlias,
    )
    from great_docs._apiref._render._section_dispatch import SECTION_METHOD

    classes = (
        RenderDocClass,
        RenderDocFunction,
        RenderDocAttribute,
        RenderDocModule,
        RenderDocTypeAlias,
    )
    orphans = {
        name for name in SECTION_METHOD.values() if not any(hasattr(c, name) for c in classes)
    }

    assert not orphans, f"SECTION_METHOD names methods that do not exist: {orphans}"


@requires_pep695
def test_attributes_section_on_a_type_alias_is_unhandled(caplog):
    """
    A type alias has no attributes, so the section has no renderer

    `Attributes` describes the members of a class or a module. Anything else
    documenting one is an authoring mistake worth reporting.
    """
    source = '''
        type Pair = tuple[int, int]
        """
        Two integers.

        Attributes
        ----------
        first : int
            Not a real attribute.
        """
    '''
    with caplog.at_level("WARNING"):
        qmd = _render(source, "Pair")

    assert "Not a real attribute." not in qmd
    assert "object at 0x" not in qmd
    assert any("no renderer" in r.message for r in caplog.records)


def test_attributes_section_on_a_class_still_renders():
    source = '''
        class Widget:
            """
            A widget.

            Attributes
            ----------
            size : int
                How big it is.
            """

            size: int = 3
    '''
    assert "How big it is." in _render(source, "Widget")


def test_attributes_section_on_a_module_still_renders():
    source = '''
        """
        A module.

        Attributes
        ----------
        MAX : int
            The largest allowed value.
        """

        MAX: int = 3
    '''
    assert "The largest allowed value." in _render(source, None)


def test_type_parameters_section_on_a_module_is_unhandled(caplog):
    """
    A module is not generic, so it has no type parameters to describe
    """
    source = '''
        """
        A module.

        Type Parameters
        ---------------
        T :
            Not a real type parameter.
        """
    '''
    with caplog.at_level("WARNING"):
        qmd = _render(source, None)

    assert "Not a real type parameter." not in qmd
    assert "object at 0x" not in qmd
    assert any("no renderer" in r.message for r in caplog.records)


def test_type_parameters_section_on_a_plain_attribute_is_unhandled(caplog):
    source = '''
        class Holder:
            """A holder."""

            size: int = 3
            """
            The size.

            Type Parameters
            ---------------
            T :
                Not a real type parameter.
            """
    '''
    with caplog.at_level("WARNING"):
        qmd = _render(source, "Holder")

    assert "Not a real type parameter." not in qmd
    assert any("no renderer" in r.message for r in caplog.records)


@requires_pep695
def test_type_parameters_section_on_a_generic_class_still_renders():
    source = '''
        class Repo[T]:
            """
            A repository.

            Type Parameters
            ---------------
            T :
                The entity type.
            """
    '''
    assert "The entity type." in _render(source, "Repo")


@requires_pep695
def test_type_parameters_section_on_a_generic_function_still_renders():
    source = '''
        def first[T](items: list[T]) -> T:
            """
            Take the first item.

            Type Parameters
            ---------------
            T :
                The element type.
            """
            return items[0]
    '''
    assert "The element type." in _render(source, "first")


@requires_pep695
def test_type_parameters_section_on_a_generic_type_alias_still_renders():
    source = '''
        type Pair[T] = tuple[T, T]
        """
        Two values of the same type.

        Type Parameters
        ---------------
        T :
            The type of both elements.
        """
    '''
    assert "The type of both elements." in _render(source, "Pair")
