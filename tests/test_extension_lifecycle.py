"""
Verify reference cleanup and extension failures across builds and symbol queries

Builds, freezes, previews and symbol queries close their API references, and an
extension failure stops the build without a static retry.
"""

from __future__ import annotations

import io
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from great_docs import GreatDocs
from great_docs._apiref._customisation import ExtensionError
from great_docs._apiref.api_reference import APIReference
from great_docs._build import pipeline, reference, watch
from great_docs._build.log import BuildLog
from great_docs._build.pipeline import Run
from great_docs._build.steps import Outcome, Step
from great_docs._project.layout import Layout
from great_docs._reference import documented
from great_docs._website import quarto_yml
from tests.support import StubRemote, make_run, stubbed_build, write_config, write_pyproject


def make_project(root: Path) -> GreatDocs:
    """Create a project with a relative extension helper and one documented function"""
    write_pyproject(root, "extension_lifetime_example")
    package = root / "extension_lifetime_example"
    package.mkdir()
    (package / "__init__.py").write_text('def example():\n    """Example subject"""\n')
    (root / "helper.py").write_text("TOKEN = 'current'\n")
    (root / "extension.py").write_text(
        "from great_docs.extensions import Extension\n"
        "from .helper import TOKEN\n\n"
        "def setup(extension: Extension) -> None:\n"
        "    extension.cache['namespace'] = __package__\n"
        "    extension.cache['token'] = TOKEN\n"
    )
    write_config(root, {"api_reference_extension": "extension.py", "dynamic": True})
    return GreatDocs(str(root))


def test_dynamic_retry_releases_the_failed_extension_before_loading_the_next(
    tmp_path: Path,
) -> None:
    docs = make_project(tmp_path)
    block = {"package": "extension_lifetime_example", "sections": [], "dynamic": True}
    run = make_run(docs, quarto_config={"api-reference": block}, api_block=block)
    attempts: list[APIReference] = []
    namespaces: list[str] = []

    def build(ref: APIReference) -> None:
        assert run.api_reference is ref
        if namespaces:
            assert not any(name.startswith(namespaces[-1]) for name in sys.modules)
        extension = ref.extension
        assert extension.cache["token"] == "current"
        namespaces.append(str(extension.cache["namespace"]))
        attempts.append(ref)
        if len(attempts) == 1:
            raise ImportError("dynamic acquisition failed")

    try:
        with patch.object(APIReference, "build", autospec=True, side_effect=build):
            outcome, ref = reference.api(
                run, docs._config, docs.layout, BuildLog(stream=io.StringIO())
            )
        assert outcome == "API reference generated (static analysis)"
        assert len(attempts) == 2
        assert ref is attempts[1] is run.api_reference
        assert namespaces[0] != namespaces[1]
        assert namespaces[1] in sys.modules
    finally:
        run.close()
    assert not any(name.startswith(tuple(namespaces)) for name in sys.modules)


def test_configured_setup_failure_is_fatal_without_static_retry(tmp_path: Path) -> None:
    docs = make_project(tmp_path)
    (tmp_path / "extension.py").write_text("from .helper import TOKEN\n")
    block = {"package": "extension_lifetime_example", "sections": [], "dynamic": True}
    run = make_run(docs, quarto_config={"api-reference": block}, api_block=block)
    before = set(sys.modules)

    def build(ref: APIReference) -> None:
        _ = ref.extension

    with (
        patch.object(APIReference, "build", autospec=True, side_effect=build) as generate,
        pytest.raises(ExtensionError, match="setup"),
    ):
        reference.api(run, docs._config, docs.layout, BuildLog(stream=io.StringIO()))
    assert generate.call_count == 1
    assert block["dynamic"] is True
    assert not any(name.startswith("_great_docs_extension_") for name in set(sys.modules) - before)


@pytest.mark.parametrize("phase", ["summary", "body"])
def test_configured_renderer_failure_is_fatal_without_static_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    docs = make_project(tmp_path)
    (tmp_path / "extension.py").write_text(
        "from collections.abc import Sequence\n"
        "from pathlib import Path\n"
        "from great_docs.extensions import Extension\n"
        "from great_docs.pandoc.blocks import BlockContent, DefinitionItem\n"
        "from great_docs.rendering import FunctionRenderer, Renderers\n\n"
        "class BrokenRenderer(FunctionRenderer):\n"
        "    def render_summary(self) -> Sequence[DefinitionItem]:\n"
        f"        if {phase!r} == 'summary':\n"
        "            raise ImportError('configured presentation failed')\n"
        "        return super().render_summary()\n"
        "    def render_body(self) -> BlockContent:\n"
        f"        if {phase!r} == 'body':\n"
        "            raise ImportError('configured presentation failed')\n"
        "        return super().render_body()\n\n"
        "def setup(extension: Extension) -> None:\n"
        "    with Path(__file__).with_name('setups.txt').open('a') as stream:\n"
        "        stream.write('setup\\n')\n"
        "    extension.set_renderers(Renderers(functions=BrokenRenderer))\n"
    )
    docs.layout.build_dir.mkdir()
    monkeypatch.chdir(docs.layout.build_dir)
    monkeypatch.syspath_prepend(str(tmp_path))
    block = {
        "package": "extension_lifetime_example",
        "sections": [{"title": "API", "contents": ["example"]}],
        "dynamic": True,
    }
    run = make_run(docs, quarto_config={"api-reference": block}, api_block=block)
    before = set(sys.modules)
    try:
        with pytest.raises(ExtensionError, match="render") as failure:
            reference.api(run, docs._config, docs.layout, BuildLog(stream=io.StringIO()))
        assert isinstance(failure.value.__cause__, ImportError)
        assert (tmp_path / "setups.txt").read_text() == "setup\n"
        assert block["dynamic"] is True
        assert ".qmd" in str(failure.value)
        assert not any(
            name.startswith("_great_docs_extension_") for name in set(sys.modules) - before
        )
    finally:
        run.close()
        sys.modules.pop("extension_lifetime_example", None)


@pytest.mark.parametrize("fail_consumer", [False, True])
def test_query_releases_owned_imports_and_restores_package_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fail_consumer: bool
) -> None:
    docs = make_project(tmp_path)
    name = "extension_lifetime_example"
    original = ModuleType(name)
    monkeypatch.setitem(sys.modules, name, original)
    original_path = list(sys.path)
    namespace = ""

    def query() -> None:
        nonlocal namespace
        with documented._resolved_reference(
            docs._config,
            importable_name=name,
            search_paths=[tmp_path],
            create_sections=lambda _: [{"title": "API", "contents": ["example"]}],
        ) as ref:
            assert ref is not None
            namespace = str(ref.extension.cache["namespace"])
            assert namespace in sys.modules
            assert ref.extension.source_root == tmp_path
            assert ref.extension.config_root == tmp_path
            if fail_consumer:
                raise ValueError("consumer failed")

    if fail_consumer:
        with pytest.raises(ValueError, match="consumer failed"):
            query()
    else:
        query()
    assert sys.modules[name] is original
    assert sys.path == original_path
    assert namespace
    assert not any(module.startswith(namespace) for module in sys.modules)
    assert not docs.layout.build_dir.exists()


@pytest.mark.parametrize("fail_consumer", [False, True])
def test_build_closes_its_reference_after_consumers(tmp_path: Path, fail_consumer: bool) -> None:
    write_config(tmp_path)
    docs = GreatDocs(str(tmp_path))
    docs.layout.build_dir.mkdir()
    quarto_yml.write_initial(docs.layout.build_dir)
    active = MagicMock(spec=APIReference)

    def install(run: Run, *args: object, **kwargs: object) -> tuple[Outcome, APIReference]:
        run.api_reference = active
        return "API reference generated", active

    def consume(*args: object, **kwargs: object) -> str:
        active.close.assert_not_called()
        if fail_consumer:
            raise RuntimeError("consumer failed")
        return "Interlinks generated"

    with (
        stubbed_build(),
        patch.object(reference, "api", autospec=True, side_effect=install),
        patch.object(reference, "interlinks", autospec=True, side_effect=consume),
    ):
        if fail_consumer:
            with pytest.raises(RuntimeError, match="consumer failed"):
                docs.build(refresh=False)
        else:
            docs.build(refresh=False)
    active.close.assert_called_once_with()


@pytest.mark.parametrize("fail_consumer", [False, True])
def test_freeze_preparation_closes_its_reference(tmp_path: Path, fail_consumer: bool) -> None:
    write_config(tmp_path)
    docs = GreatDocs(str(tmp_path))
    active = MagicMock(spec=APIReference)

    def preparation(run: Run, *args: object, **kwargs: object) -> list[Step]:
        run.api_reference = active
        return []

    def freeze(*args: object, **kwargs: object) -> None:
        active.close.assert_not_called()
        if fail_consumer:
            raise ValueError("freeze failed")

    with (
        patch.object(pipeline, "preparation_steps", autospec=True, side_effect=preparation),
        patch.object(pipeline.freeze, "prepare", autospec=True, side_effect=freeze),
    ):
        if fail_consumer:
            with pytest.raises(ValueError, match="freeze failed"):
                pipeline.prepare_for_freeze(
                    docs._config, docs.layout, BuildLog(), remote=StubRemote()
                )
        else:
            pipeline.prepare_for_freeze(docs._config, docs.layout, BuildLog(), remote=StubRemote())
    active.close.assert_called_once_with()


@pytest.mark.parametrize("fail_rebuild", [False, True])
def test_preview_closes_each_generation_before_serving_or_retrying(
    tmp_path: Path, fail_rebuild: bool
) -> None:
    write_config(tmp_path)
    docs = GreatDocs(str(tmp_path))
    initial = MagicMock(spec=APIReference)
    rebuilt = MagicMock(spec=APIReference)
    run = make_run(docs, watch=True, api_reference=initial)

    def prepare(current: Run, *args: object, **kwargs: object) -> list[Step]:
        current.api_reference = rebuilt

        def finish_preparation() -> str:
            rebuilt.close.assert_not_called()
            if fail_rebuild:
                raise ValueError("preview failed")
            return "Prepared"

        return [Step("Prepare reference", finish_preparation)]

    def serve(
        layout: Layout,
        env: Mapping[str, str],
        rebuild: Callable[[watch.Staging], object],
        *args: object,
        **kwargs: object,
    ) -> None:
        initial.close.assert_called_once_with()
        staging = watch.stage(layout)
        staging.build_dir.mkdir(parents=True)
        if fail_rebuild:
            with pytest.raises(ValueError, match="preview failed"):
                rebuild(staging)
        else:
            rebuild(staging)
        rebuilt.close.assert_called_once_with()

    with (
        patch.object(pipeline, "preparation_steps", autospec=True, side_effect=prepare),
        patch.object(watch, "serve", autospec=True, side_effect=serve),
        patch.object(pipeline.quarto, "environment", autospec=True, return_value={}),
        patch.object(pipeline.finish, "print_layout_notice", autospec=True),
    ):
        pipeline._watch(
            run, docs._config, docs.layout, BuildLog(), [], remote=StubRemote(), refresh=True
        )
