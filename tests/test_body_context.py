"""Verify appearance contexts and prepared facts through real reference consumers"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import cast

import griffe as gf
import pytest

from great_docs._apiref._extension_loading import _ExtensionSource
from great_docs._apiref.api_reference import APIReference
from great_docs.config import Config
from great_docs.rendering import RenderContext


@contextmanager
def recorded_reference(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[APIReference, Path, Path]]:
    """Own a reference with separate source/output roots and a body recorder"""
    package = root / "body_context_example"
    package.mkdir()
    (package / "__init__.py").write_text(
        "from .impl import Document\nfrom .impl import Document as Alias\n"
    )
    (package / "impl.py").write_text(
        'class Document:\n    """Document subject"""\n\n'
        '    def render(self) -> str:\n        """Render subject"""\n'
    )
    (package / "types.py").write_text(
        "from typing import Protocol\n\n"
        'class Readable(Protocol):\n    """Readable subject"""\n\n'
        '    def read(self) -> str:\n        """Read subject"""\n'
    )
    source = root / "docs"
    source.mkdir()
    (source / "great-docs.yml").write_text(
        "api_reference_extension: extension.py\ndynamic: false\n"
    )
    (source / "extension.py").write_text(
        "import griffe as gf\n"
        "from great_docs.extensions import Extension\n"
        "from great_docs.pandoc.blocks import BlockContent\n"
        "from great_docs.rendering import RenderContext, Renderers\n\n"
        "def setup(extension: Extension) -> None:\n"
        "    contexts: list[RenderContext] = []\n"
        "    prepared: list[str] = []\n"
        "    extension.cache['contexts'] = contexts\n"
        "    extension.cache['prepared'] = prepared\n"
        "    @extension.on_object_resolved\n"
        "    def resolved(obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias:\n"
        "        prepared.append(obj.path)\n"
        "        return obj\n"
        "    @extension.on_docstring_parsed\n"
        "    def sections(obj: gf.Object | gf.Alias, sections: list[gf.DocstringSection]) -> list[gf.DocstringSection]:\n"
        "        if obj.name == 'render':\n"
        "            returns = gf.DocstringSectionReturns([\n"
        "                gf.DocstringReturn('', annotation='str', description='First paragraph'),\n"
        "                gf.DocstringReturn('', annotation='str', description='Second paragraph'),\n"
        "            ])\n"
        "            extension.cache['returns'] = returns.value\n"
        "            return [gf.DocstringSectionText('Render subject'), returns]\n"
        "        return sections\n"
        "    class RecordContextMixin:\n"
        "        def render_docstring_body(self) -> BlockContent:\n"
        "            contexts.append(self.context)\n"
        "            return super().render_docstring_body()\n"
        "    extension.set_renderers(Renderers(object_renderer_mixin=RecordContextMixin))\n"
    )
    output = root / "output"
    config = Config(root, config_path=source / "great-docs.yml")
    monkeypatch.syspath_prepend(str(root))
    ref = APIReference(
        {
            "package": package.name,
            "dynamic": False,
            "typing_module_paths": [f"{package.name}.types"],
            "sections": [{"title": "API", "contents": ["Document", "Alias"]}],
        },
        extension_source=_ExtensionSource.make(config, source),
        output_root=output,
    )
    try:
        yield ref, source, output
    finally:
        ref.close()


def contexts(ref: APIReference) -> list[RenderContext]:
    """Read the appearances recorded by the extension's renderers"""
    return cast("list[RenderContext]", ref.extension.cache["contexts"])


def test_build_reports_alias_member_and_typing_destinations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with recorded_reference(tmp_path, monkeypatch) as (ref, source, output):
        output.mkdir()
        monkeypatch.chdir(output)
        ref.build()
        appearances = contexts(ref)
        parents = [
            context for context in appearances if context.authored_name in {"Document", "Alias"}
        ]
        assert {context.authored_name for context in parents} == {"Document", "Alias"}
        assert {context.canonical_identity for context in parents} == {
            "body_context_example.impl.Document"
        }
        assert {context.page_path for context in parents} == {
            "reference/Document.qmd",
            "reference/Alias.qmd",
        }
        methods = [
            context
            for context in appearances
            if context.canonical_identity.endswith("Document.render")
        ]
        assert len(methods) == 2
        assert all(context.contained and context.level == 3 for context in methods)
        assert {context.page_path for context in methods} == {
            context.page_path for context in parents
        }
        assert any(context.page_path == "reference/types.qmd" for context in appearances)
        for context in appearances:
            assert context.source_root == source
            assert context.output_root == output
            assert context.settings is ref.settings
            assert context.page_path is not None
            assert (output / context.page_path).is_file()
        with pytest.raises(FrozenInstanceError):
            setattr(appearances[0], "level", 99)


def test_summaries_skip_docstring_bodies_and_renderers_cache_their_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with recorded_reference(tmp_path, monkeypatch) as (ref, _, _):
        index = ref.renderers.make(ref, sections=ref.resolved)
        returns = cast("list[gf.DocstringReturn]", ref.extension.cache["returns"])
        before = [item.description for item in returns]
        assert "Document" in str(index)
        assert contexts(ref) == []
        prepared = list(cast("list[str]", ref.extension.cache["prepared"]))
        page = ref.resolved[0].contents[0]
        doc = page.contents[0].members[0]
        arguments = {"extension": ref.extension, "context_page_path": "reference/Document.qmd"}
        renderer = ref.renderers.make(doc, **arguments)
        assert renderer.render_summary()
        assert contexts(ref) == []
        first = str(renderer)
        assert len(contexts(ref)) == 1
        assert str(renderer) == first
        assert len(contexts(ref)) == 1
        assert str(ref.renderers.make(doc, **arguments)) == first
        assert len(contexts(ref)) == 2
        assert ref.extension.cache["prepared"] == prepared
        # Each rendering reads the prepared continuation definitions without changing them.
        assert "First paragraph" in first
        assert "Second paragraph" in first
        assert [item.description for item in returns] == before
