"""Verify signature caching, the Usage row and member presentation on class pages"""

from __future__ import annotations

from collections.abc import Sequence
from functools import cached_property
from textwrap import dedent
from typing import Literal, cast

import griffe as gf
import pytest
from great_docs._apiref._conversion import griffe_to_doc

from great_docs._apiref._rendering._context import _RenderingPurpose
from great_docs._apiref.collect import build_manifest
from great_docs._apiref.content import DocClass, DocFunction, Page, Section
from great_docs.pandoc.blocks import BlockContent
from great_docs.pandoc.inlines import Link
from great_docs.rendering import ClassRenderer, FunctionRenderer, ObjectRenderer, Renderers


def make_class_doc() -> DocClass:
    """
    Construct a class whose docstring and method docstring each have a body

    Returns
    -------
    :
        The documentation node of `Example`. Its body contains `CLASS_BODY` and its
        method's body contains `MEMBER_BODY`.
    """
    source = '''
        class Example:
            """Example subject

            CLASS_BODY
            """

            def method(self, value: int = 1):
                """Method subject

                MEMBER_BODY
                """
    '''
    with gf.temporary_visited_package(
        "composition_example", {"__init__.py": dedent(source)}, docstring_parser="numpy"
    ) as package:
        return cast("DocClass", griffe_to_doc(package["Example"]))


def test_signature_is_materialised_once_per_renderer():
    calls: list[str] = []

    class CountingFunction(FunctionRenderer):
        def render_signature(self) -> BlockContent:
            calls.append(self.obj.path)
            return super().render_signature()

    doc = cast("DocFunction", make_class_doc().members[0])
    renderer = Renderers(functions=CountingFunction).make(doc)
    first = str(renderer)
    assert "doc-signature" in first
    assert str(renderer) == first
    assert renderer.signature is renderer.signature
    assert calls == [doc.obj.path]


@pytest.mark.parametrize("with_source", [False, True])
def test_signature_omission_retains_only_a_useful_source_row(with_source: bool):
    class HiddenSignature(FunctionRenderer):
        def render_signature(self) -> BlockContent:
            return None

        @cached_property
        def source_link(self) -> Link | None:
            return Link("Source", "https://example.test/source.py#L1") if with_source else None

    doc = cast("DocFunction", make_class_doc().members[0])
    rendered = str(Renderers(functions=HiddenSignature).make(doc))
    assert "doc-signature" not in rendered
    assert ("doc-usage-source" in rendered) is with_source
    assert ("https://example.test/source.py#L1" in rendered) is with_source
    assert "MEMBER_BODY" in rendered


@pytest.mark.parametrize("hide_summary, hide_body", [(True, False), (False, True), (True, True)])
def test_member_presentation_preserves_inventory_membership(hide_summary: bool, hide_body: bool):
    class CustomClass(ClassRenderer):
        def render_members_summary(
            self,
            kind: Literal["type-aliases", "classes", "functions", "attributes"],
            renderers: Sequence[ObjectRenderer],
        ) -> BlockContent:
            return None if hide_summary else super().render_members_summary(kind, renderers)

        def render_members_body(
            self,
            kind: Literal["type-aliases", "classes", "functions", "attributes"],
            renderers: Sequence[ObjectRenderer],
        ) -> BlockContent:
            return None if hide_body else super().render_members_body(kind, renderers)

    doc = make_class_doc()
    sections = [Section(title="Examples", contents=[Page(path="Example", contents=[doc])])]
    members = tuple(doc.members)
    before = [(item.name, item.uri) for item in build_manifest(sections, dir="reference").items]
    rendered = str(Renderers(classes=CustomClass).make(doc))
    after = [(item.name, item.uri) for item in build_manifest(sections, dir="reference").items]
    assert tuple(doc.members) == members
    assert after == before
    assert any(name.endswith(".method") for name, _ in before)
    assert ("MEMBER_BODY" in rendered) is not hide_body
    assert ("gd-summary-table" in rendered) is not hide_summary
    assert ("doc-methods" in rendered) is not (hide_summary and hide_body)


def test_embedded_members_reset_typing_purpose_and_keep_the_page_path():
    appearances: list[tuple[_RenderingPurpose, str | None]] = []

    class ObservedFunction(FunctionRenderer):
        def render_description(self) -> BlockContent:
            appearances.append((self._purpose, self.page_path))
            return super().render_description()

    choices = Renderers(functions=ObservedFunction)
    renderer = choices.make(
        make_class_doc(),
        page_path="reference/Example.qmd",
        _purpose=_RenderingPurpose.PROTOCOL,
    )
    assert "MEMBER_BODY" in str(renderer)
    assert appearances == [(_RenderingPurpose.OBJECT, "reference/Example.qmd")]
