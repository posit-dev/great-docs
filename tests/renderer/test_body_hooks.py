"""Verify docstring body overrides"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import griffe as gf
import pytest

from great_docs._apiref._conversion import griffe_to_doc
from great_docs._apiref._settings import Settings
from great_docs._apiref.content import DocFunction
from great_docs._apiref.typing import DocType
from great_docs.extensions import Extension
from great_docs.pandoc.blocks import BlockContent, Blocks, Para
from great_docs.rendering import FunctionRenderer, RenderContext, Renderers


def make_doc(extension: Extension, code: str, name: str) -> DocType:
    """Prepare a snippet through the operation before constructing its documentation"""
    with gf.temporary_visited_package(
        "package", {"__init__.py": code}, docstring_parser=extension.settings.parser
    ) as module:
        doc = griffe_to_doc(
            module[name], inherited=False, skip_aliases=True, prepare=extension.prepare
        )
    assert doc is not None
    return doc


def test_docstring_body_mixin_runs_for_parent_and_each_member() -> None:
    extension = Extension(Settings())
    seen: dict[str, str] = {}

    class AppendNoteMixin:
        def render_docstring_body(self) -> BlockContent:
            body = super().render_docstring_body()
            name = self.context.authored_name
            seen[name] = str(body)
            return Blocks([body, Para(f"Note for {name}")])

    extension.set_renderers(Renderers(doc_mixin=AppendNoteMixin))

    code = '''
class Example:
    """Parent subject

    Parent detail
    """

    def child(self):
        """Child subject

        Child detail
        """
'''
    try:
        doc = make_doc(extension, code, "Example")
        output = str(extension.renderers.make(doc, extension=extension))
        assert "Parent detail" in seen["Example"]
        assert "Child detail" not in seen["Example"]
        assert "Note for child" not in seen["Example"]
        assert "Child detail" in seen["child"]
        assert output.index("Note for Example") < output.index("## Methods")
    finally:
        extension.close()


def test_summary_only_rendering_skips_docstring_body() -> None:
    extension = Extension(Settings())
    calls: list[RenderContext] = []

    class Presentation(FunctionRenderer):
        def render_docstring_body(self) -> BlockContent:
            calls.append(self.context)
            return super().render_docstring_body()

    extension.set_renderers(Renderers(functions=Presentation))

    try:
        doc = make_doc(extension, 'def run():\n    """Run the example"""\n', "run")
        renderer = extension.renderers.make(doc, extension=extension)
        assert "Run the example" in str(renderer.render_summary())
        assert calls == []
    finally:
        extension.close()


def test_docstring_body_override_can_replace_usage_examples() -> None:
    extension = Extension(Settings())

    class CustomFunction(FunctionRenderer):
        def render_signature(self) -> BlockContent:
            return None

        @property
        def summary_name(self) -> str:
            return "Run the task"

        def render_docstring_body(self) -> BlockContent:
            body = super().render_docstring_body()
            if body is None:
                return None
            return str(body).replace("run(old=True)", "run(current=True)")

    extension.set_renderers(Renderers(functions=CustomFunction))

    code = '''
def run(old=False):
    """Run the example

    Usage
    -----
    ```python
    run(old=True)
    ```
    """
'''
    try:
        doc = make_doc(extension, code, "run")
        renderer = extension.renderers.make(doc, extension=extension)
        output = str(renderer)
        assert "run(current=True)" in output
        assert "run(old=True)" not in output
        assert "doc-signature" not in output
        assert "Run the task" in str(renderer.render_summary())
    finally:
        extension.close()


def test_continuation_rendering_preserves_prepared_definitions() -> None:
    extension = Extension(Settings())

    @extension.on_docstring_parsed
    def sections(
        obj: gf.Object | gf.Alias, parsed: list[gf.DocstringSection]
    ) -> list[gf.DocstringSection]:
        return [
            gf.DocstringSectionText("A summary"),
            gf.DocstringSectionReturns(
                [
                    gf.DocstringReturn("", annotation="int", description="First paragraph"),
                    gf.DocstringReturn("", annotation="int", description="Second paragraph"),
                ]
            ),
        ]

    try:
        doc = cast("DocFunction", make_doc(extension, 'def run():\n    """A summary"""\n', "run"))
        definitions = doc.obj.docstring.parsed[1].value
        before = [item.description for item in definitions]
        first = str(extension.renderers.make(doc, extension=extension))
        second = str(extension.renderers.make(doc, extension=extension))
        assert first == second
        assert first.count("Second paragraph") == 1
        assert [item.description for item in definitions] == before
    finally:
        extension.close()


@pytest.mark.parametrize(
    ("known_root", "inside", "expected"),
    [(True, True, "reference/run.qmd"), (False, True, None), (True, False, None)],
)
def test_absolute_output_directories_use_explicit_context_coordinates(
    tmp_path: Path, known_root: bool, inside: bool, expected: str | None
) -> None:
    from great_docs._apiref.content import Page
    from great_docs._apiref.write import write_pages

    output = tmp_path / "output"
    destination = output / "reference" if inside else tmp_path / "elsewhere"
    settings = Settings(dir=str(destination))
    extension = Extension(settings)
    contexts: list[RenderContext] = []

    class RecordContextMixin:
        def render_docstring_body(self) -> BlockContent:
            contexts.append(self.context)
            return super().render_docstring_body()

    extension.set_renderers(Renderers(doc_mixin=RecordContextMixin))

    try:
        doc = make_doc(extension, "def run(): pass\n", "run")
        page = Page(path="run", contents=[doc])
        write_pages(
            [page],
            settings,
            site_toc_depth=2,
            renderers=extension.renderers,
            extension=extension,
            output_root=output if known_root else None,
        )
        assert (destination / "run.qmd").is_file()
        assert len(contexts) == 1
        assert contexts[0].page_path == expected

        from great_docs._apiref.inventory import InventoryItem
        from great_docs._apiref.typing_information import TypeSections

        contexts.clear()
        protocol = gf.Class("Readable", docstring=gf.Docstring("A readable value"))
        typing = TypeSections(
            protocols_items=[InventoryItem(name="Readable", obj=protocol)],
            typevars_items=[],
            typealiases_items=[],
            settings=settings,
            renderers=extension.renderers,
            extension=extension,
            page_path=str(destination / "types.qmd"),
            output_root=output if known_root else None,
        )
        _ = str(typing)
        assert len(contexts) == 1
        assert contexts[0].page_path == (expected.replace("run", "types") if expected else None)
    finally:
        extension.close()
