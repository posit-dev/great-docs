"""Tests for the docstring `Type Parameters` section."""

from __future__ import annotations

import sys
import textwrap

import pytest

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 12),
    reason="PEP 695 type parameter syntax requires Python 3.12+",
)
requires_pep696 = pytest.mark.skipif(
    sys.version_info < (3, 13),
    reason="PEP 696 type parameter defaults require Python 3.13+",
)


def _render(source: str, name: str | None) -> str:
    """Render the named object from a source snippet to qmd"""
    from great_docs._apiref._tools import render_code_variable

    return render_code_variable(textwrap.dedent(source), name)


def test_generic_class_section_renders():
    """
    The bound is omitted in the docstring, so griffe fills it from the signature

    An unrendered section is not the only failure mode here: the heading renders
    on its own, so the section must be checked for leaked object reprs too.
    """
    source = '''
        class Model: ...

        class Repo[T: Model, K]:
            """
            A repository.

            Type Parameters
            ---------------
            T :
                The entity type stored in the repository.
            K :
                The primary-key type used to look entities up.
            """
    '''
    qmd = _render(source, "Repo")

    assert "Type Parameters" in qmd
    assert "The entity type stored in the repository." in qmd
    assert "The primary-key type used to look entities up." in qmd
    assert "object at 0x" not in qmd


def test_generic_function_section_renders():
    source = '''
        from collections.abc import Callable, Iterable

        def group_by[T, K](items: Iterable[T], key: Callable[[T], K]) -> dict[K, list[T]]:
            """
            Group items by a computed key.

            Type Parameters
            ---------------
            T :
                The element type, inferred from `items`.
            K :
                The grouping key type.
            """
    '''
    qmd = _render(source, "group_by")

    assert "The element type, inferred from" in qmd
    assert "The grouping key type." in qmd
    assert "object at 0x" not in qmd


def test_generic_type_alias_section_renders():
    """
    A generic type alias documents type parameters even though it is not callable

    `TypeAliasRenderer` does not inherit `CallableRendererMixin`, so it defines
    its own `render_type_parameters_section` rather than sharing the mixin's.
    """
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
    qmd = _render(source, "Pair")

    assert "The type of both elements." in qmd
    assert "object at 0x" not in qmd


def test_unbounded_parameter_omits_the_annotation_separator():
    """An unbounded parameter has no annotation, so no `:` separator is rendered"""
    source = '''
        class Box[K]:
            """
            A box.

            Type Parameters
            ---------------
            K :
                The key type.
            """
    '''
    qmd = _render(source, "Box")

    assert "The key type." in qmd
    assert "doc-parameter-annotation-sep" not in qmd
    assert "object at 0x" not in qmd


def test_constrained_parameter_renders_the_constraints():
    """
    A constrained parameter renders as the tuple griffe puts in `.annotation`

    `.constraints` needs no special handling: griffe already exposes
    `(str, bytes)` through the same attribute a bound uses.
    """
    source = '''
        class Both[S: (str, bytes)]:
            """
            A thing.

            Type Parameters
            ---------------
            S :
                Either flavour of string.
            """
    '''
    qmd = _render(source, "Both")

    assert "Either flavour of string." in qmd
    assert "str" in qmd and "bytes" in qmd
    assert "object at 0x" not in qmd


@requires_pep696
def test_default_renders():
    source = '''
        class Holder[T: int = bool]:
            """
            A holder.

            Type Parameters
            ---------------
            T :
                The held type.
            """
    '''
    qmd = _render(source, "Holder")

    assert "The held type." in qmd
    assert "doc-parameter-default" in qmd
    assert "object at 0x" not in qmd


def test_module_attributes_section_renders():
    """
    A module can document an `Attributes` section

    `ModuleRenderer` reaches `render_attributes_section` through the members
    mixin it shares with `ClassRenderer`, not through `CallableRendererMixin`.
    A module has no `Type Parameters` section.
    """
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
    qmd = _render(source, None)

    assert "The largest allowed value." in qmd
    assert "object at 0x" not in qmd


def test_docstring_bound_overrides_the_signature():
    """griffe lets an explicit docstring bound win over the one in the signature"""
    source = '''
        class Model: ...
        class Other: ...

        class Repo[T: Model]:
            """
            A repository.

            Type Parameters
            ---------------
            T : Other
                The entity type.
            """
    '''
    qmd = _render(source, "Repo")

    assert "The entity type." in qmd
    assert "Other" in qmd
    assert "object at 0x" not in qmd
