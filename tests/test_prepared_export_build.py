"""Verify semantic export shares the build's prepared reference and lifetime"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from great_docs import GreatDocs
from great_docs._apiref._customisation import ExtensionError
from great_docs._apiref.api_reference import APIReference
from great_docs._build import generated, reference
from great_docs._build.pipeline import Run
from great_docs._build.steps import BuildError, Outcome
from great_docs._website import quarto_yml
from tests.support import StubRemote, stubbed_build, write_config, write_pyproject


def test_build_exports_prepared_semantics_without_repeating_presentation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    name = "prepared_export_example"
    write_pyproject(tmp_path, name)
    package = tmp_path / name
    package.mkdir()
    (package / "__init__.py").write_text(
        'def document(visible: int, hidden: str = "private-default") -> str:\n'
        '    """Original runtime subject\n\n'
        "    Parameters\n    ----------\n"
        "    visible\n        Visible description.\n"
        "    hidden\n        Hidden description.\n"
        '    """\n\n'
        'def excluded():\n    """Excluded object description"""\n'
    )
    (tmp_path / "extension.py").write_text(
        "from pathlib import Path\n"
        "import griffe as gf\n"
        "from great_docs.extensions import Extension\n"
        "from great_docs.pandoc.blocks import BlockContent, Blocks, Para\n"
        "from great_docs.rendering import FunctionRenderer, Renderers\n\n"
        "def record(name: str) -> None:\n"
        "    with Path(__file__).with_name('events.txt').open('a') as stream:\n"
        "        stream.write(name + '\\n')\n\n"
        "class Presentation(FunctionRenderer):\n"
        "    def render_signature(self) -> BlockContent:\n"
        "        return None\n"
        "    @property\n"
        "    def summary_name(self) -> str:\n"
        "        return 'PRESENTATION_LABEL'\n\n"
        "    def render_docstring_body(self) -> BlockContent:\n"
        "        record('body:' + self.context.authored_name)\n"
        "        return Blocks([super().render_docstring_body(), Para('PRESENTATION_ONLY_NOTE')])\n\n"
        "    def render_docstring_body(self) -> BlockContent:\n"
        "        record('body:' + self.context.authored_name)\n"
        "        return Blocks([super().render_docstring_body(), Para('PRESENTATION_ONLY_NOTE')])\n\n"
        "    def render_docstring_body(self) -> BlockContent:\n"
        "        record('body:' + self.context.authored_name)\n"
        "        return Blocks([super().render_docstring_body(), Para('PRESENTATION_ONLY_NOTE')])\n\n"
        "def setup(extension: Extension) -> None:\n"
        "    record('setup')\n"
        "    extension.set_renderers(Renderers(functions=Presentation))\n"
        "    @extension.on_object_resolved(priority=-200)\n"
        "    def prepare(obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias | None:\n"
        "        record('prepare:' + obj.name)\n"
        "        if obj.name == 'excluded':\n"
        "            return None\n"
        "        if obj.name == 'document' and obj.docstring is not None:\n"
        "            obj.docstring.value = obj.docstring.value.replace('Original runtime subject', 'Prepared semantic subject')\n"
        "            obj.docstring.value += '\\n\\nSEMANTIC_NOTE\\n\\n%nodoc_param hidden'\n"
        "        return obj\n"
    )
    write_config(tmp_path, {"api_reference_extension": "extension.py", "dynamic": False})
    docs = GreatDocs(str(tmp_path))
    docs._remote = StubRemote()
    docs.layout.build_dir.mkdir()
    quarto_yml.write(
        docs.layout.build_dir,
        {
            "api-reference": {
                "package": name,
                "dynamic": False,
                "sections": [{"title": "API", "contents": ["document", "excluded"]}],
            }
        },
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    with stubbed_build(api_reference=True):
        docs.build(refresh=False)

    page = (docs.layout.build_dir / "reference" / "document.qmd").read_text()
    full = (docs.layout.build_dir / "llms-full.txt").read_text()
    index = (docs.layout.build_dir / "llms.txt").read_text()
    assert "PRESENTATION_ONLY_NOTE" in page
    assert "doc-signature" not in page
    for text in (full, index):
        assert "Prepared semantic subject" in text
        assert "PRESENTATION_ONLY_NOTE" not in text
        assert "PRESENTATION_LABEL" not in text
        assert "Original runtime subject" not in text
        assert "excluded" not in text
    assert "SEMANTIC_NOTE" in full
    assert "document(" in full
    assert "visible" in full
    assert "hidden" not in full
    assert "private-default" not in full
    events = (tmp_path / "events.txt").read_text().splitlines()
    assert events.count("setup") == 1
    assert events.count("prepare:document") == 1
    assert events.count("prepare:excluded") == 1
    assert events.count("body:document") == 1


def test_configured_export_failure_stops_the_build_and_releases_its_reference(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_config(tmp_path)
    docs = GreatDocs(str(tmp_path))
    docs.layout.build_dir.mkdir()
    quarto_yml.write_initial(docs.layout.build_dir)
    active = MagicMock(spec=APIReference)

    def install(run: Run, *args: object, **kwargs: object) -> tuple[Outcome, APIReference]:
        run.api_reference = active
        return "API reference generated", active

    with (
        stubbed_build(),
        patch.object(reference, "api", autospec=True, side_effect=install),
        patch.object(
            generated, "llms_txt", autospec=True, side_effect=ExtensionError("export failed")
        ),
        pytest.raises(BuildError) as failure,
    ):
        docs.build(refresh=False)
    assert isinstance(failure.value.__cause__, ExtensionError)
    active.close.assert_called_once_with()
    assert "llms.txt generation had issues" not in capsys.readouterr().out
