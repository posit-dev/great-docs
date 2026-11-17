"""Verify extension-input fingerprints through real Quarto execution and frozen results"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest
from bs4 import BeautifulSoup

from great_docs._apiref._extension_loading import _ExtensionSource
from great_docs._apiref.api_reference import APIReference

_REPOSITORY = Path(__file__).resolve().parents[2]
_FINGERPRINT = re.compile(r"<!-- great-docs-api-reference-inputs: ([0-9a-f]{64}) -->")


@pytest.fixture
def quarto_environment(tmp_path: Path) -> dict[str, str]:
    """
    Provide an environment in which Quarto runs Python with the project interpreter

    Skip the test when Quarto, uv or Jupyter is missing.

    Parameters
    ----------
    tmp_path
        The fallback location of the uv cache.

    Returns
    -------
    :
        The process environment for the CLI.
    """
    if shutil.which("quarto") is None or shutil.which("uv") is None:
        pytest.skip("Quarto and uv are required for rendered dependency checks")
    if importlib.util.find_spec("jupyter") is None:
        pytest.skip("Jupyter is required for rendered dependency checks")
    environment = {
        **os.environ,
        "QUARTO_PYTHON": sys.executable,
        "UV_CACHE_DIR": os.environ.get("UV_CACHE_DIR", str(tmp_path / "uv-cache")),
    }
    result = subprocess.run(
        ["uv", "run", "--no-sync", "quarto", "--version"],
        cwd=_REPOSITORY,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return environment


def execution_project(root: Path, mode: str) -> tuple[Path, Path]:
    """
    Create a project whose renderer adds a cell that prints a watched text file

    Parameters
    ----------
    root
        The project directory.
    mode
        The `freeze` setting, such as `auto` or `true`.

    Returns
    -------
    :
        The documentation directory and the watched text file.
    """
    package = root / "execution_fixture"
    package.mkdir()
    (package / "__init__.py").write_text(
        '__all__ = ["Document"]\n\nclass Document:\n    """A document"""\n', encoding="utf-8"
    )
    (root / "pyproject.toml").write_text(
        '[project]\nname = "execution-fixture"\nversion = "0.0.1"\n', encoding="utf-8"
    )
    docs = root / "docs"
    docs.mkdir()
    (docs / "index.qmd").write_text("# Extension execution\n", encoding="utf-8")
    (docs / "great-docs.yml").write_text(
        f"dynamic: false\napi_reference_extension: extension.py\nfreeze: {mode}\n"
        "reference:\n  - title: API\n    contents: [Document]\n"
        "changelog:\n  enabled: false\nskill:\n  enabled: false\n",
        encoding="utf-8",
    )
    data = docs / "value.txt"
    data.write_text("execution-original\n", encoding="utf-8")
    (docs / "extension.py").write_text(
        dedent("""\
        from great_docs.extensions import Extension
        from great_docs.pandoc.blocks import BlockContent, Blocks
        from great_docs.rendering import ClassRenderer, Renderers

        def setup(extension: Extension) -> None:
            data = extension.config_root / "value.txt"
            extension.watch("value.txt")

            class Presentation(ClassRenderer):
                def render_docstring_body(self) -> BlockContent:
                    body = super().render_docstring_body()
                    if self.context.authored_name != "Document":
                        return body
                    cell = "```{python}\\nfrom pathlib import Path\\nprint(Path(" + repr(str(data)) + ").read_text().strip())\\n```"
                    return Blocks([body, cell])

            extension.set_renderers(Renderers(classes=Presentation))
        """),
        encoding="utf-8",
    )
    return docs, data


def run_cli(root: Path, environment: dict[str, str], label: str, *arguments: str) -> None:
    """
    Run the `great-docs` CLI on a project and fail the test if the command fails

    Parameters
    ----------
    root
        The project directory.
    environment
        The process environment.
    label
        The name, without `.log`, of the log file that keeps the command's output
        for diagnosing a failed render.
    arguments
        The command and its arguments.
    """
    result = subprocess.run(
        ["uv", "run", "--no-sync", "great-docs", *arguments, "--project-path", str(root)],
        cwd=_REPOSITORY,
        env=environment,
        text=True,
        capture_output=True,
        timeout=240,
        check=False,
    )
    log = root / f"{label}.log"
    log.write_text(result.stdout + result.stderr, encoding="utf-8")
    assert result.returncode == 0, f"{log}\n{result.stdout}\n{result.stderr}"


def rendered_values(docs: Path) -> list[str]:
    """
    Read the cell outputs on the rendered `Document` page

    Parameters
    ----------
    docs
        The documentation directory.

    Returns
    -------
    :
        The text of each cell output, stripped.
    """
    page = docs / "_site" / "reference" / "Document.html"
    soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
    return [node.get_text().strip() for node in soup.select(".cell-output pre")]


def page_fingerprint(docs: Path) -> str:
    """
    Read the input fingerprint of the generated `Document.qmd`

    Parameters
    ----------
    docs
        The documentation directory.

    Returns
    -------
    :
        The fingerprint, which must appear exactly once on the page.
    """
    source = docs / "_quarto" / "default" / "reference" / "Document.qmd"
    matches = _FINGERPRINT.findall(source.read_text(encoding="utf-8"))
    assert len(matches) == 1
    return matches[0]


def test_dependency_only_edit_refreshes_automatic_execution(
    tmp_path: Path, quarto_environment: dict[str, str]
) -> None:
    docs, data = execution_project(tmp_path, "auto")
    run_cli(tmp_path, quarto_environment, "initial", "build")
    assert rendered_values(docs) == ["execution-original"]
    before = page_fingerprint(docs)
    data.write_text("execution-updated\n", encoding="utf-8")
    run_cli(tmp_path, quarto_environment, "data-edit", "build")
    assert page_fingerprint(docs) != before
    assert rendered_values(docs) == ["execution-updated"]


def test_locked_execution_refreshes_explicitly_and_persists(
    tmp_path: Path, quarto_environment: dict[str, str]
) -> None:
    docs, data = execution_project(tmp_path, "true")
    run_cli(tmp_path, quarto_environment, "initial", "build")
    assert rendered_values(docs) == ["execution-original"]
    before = page_fingerprint(docs)
    data.write_text("execution-refreshed\n", encoding="utf-8")
    run_cli(tmp_path, quarto_environment, "locked", "build")
    assert page_fingerprint(docs) != before
    assert rendered_values(docs) == ["execution-original"]

    generated = docs / "_quarto" / "default" / "reference" / "Document.qmd"
    run_cli(
        tmp_path,
        quarto_environment,
        "explicit-refresh",
        "freeze",
        str(generated.relative_to(tmp_path)),
    )
    persisted = list((docs / "_freeze" / "reference" / "Document").rglob("html.json"))
    assert len(persisted) == 1
    assert "execution-refreshed" in persisted[0].read_text(encoding="utf-8")
    data.write_text("execution-after-refresh\n", encoding="utf-8")
    run_cli(tmp_path, quarto_environment, "persisted", "build")
    assert rendered_values(docs) == ["execution-refreshed"]


def test_late_helpers_share_one_final_fingerprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = tmp_path / "fingerprint_fixture"
    package.mkdir()
    (package / "__init__.py").write_text('def run():\n    """Run an example"""\n', encoding="utf-8")
    (package / "types.py").write_text(
        'from typing import Protocol\nclass Reader(Protocol):\n    """A reader"""\n',
        encoding="utf-8",
    )
    source = tmp_path / "docs"
    source.mkdir()
    entry = source / "extension.py"
    entry.write_text(
        "from great_docs.pandoc.blocks import BlockContent, Blocks, Para\n"
        "from great_docs.rendering import FunctionRenderer, Renderers\n"
        "class Presentation(FunctionRenderer):\n"
        "    def render_docstring_body(self) -> BlockContent:\n"
        "        from .late import NOTE\n"
        "        return Blocks([super().render_docstring_body(), Para(NOTE)])\n"
        "def setup(extension):\n"
        "    extension.set_renderers(Renderers(functions=Presentation))\n",
        encoding="utf-8",
    )
    helper = source / "late.py"
    helper.write_text("NOTE = 'first'\n", encoding="utf-8")
    timestamp = helper.stat().st_mtime_ns
    output = tmp_path / "output"
    output.mkdir()
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(output)

    def generate() -> tuple[str, set[Path]]:
        reference = APIReference(
            {
                "package": "fingerprint_fixture",
                "dynamic": False,
                "sections": [{"contents": ["run"]}],
                "typing_module_paths": ["fingerprint_fixture.types"],
            },
            extension_source=_ExtensionSource(entry, source, source),
            output_root=output,
        )
        try:
            reference.build()
            paths = sorted((output / "reference").glob("*.qmd"))
            assert {path.name for path in paths} == {"index.qmd", "run.qmd", "types.qmd"}
            markers = [_FINGERPRINT.findall(path.read_text(encoding="utf-8")) for path in paths]
            assert all(len(marker) == 1 for marker in markers)
            assert len({marker[0] for marker in markers}) == 1
            return markers[0][0], set(reference.extension.imported_paths)
        finally:
            reference.close()

    first, imported = generate()
    assert helper in imported
    helper.write_text("NOTE = 'other'\n", encoding="utf-8")
    os.utime(helper, ns=(timestamp, timestamp))
    second, imported = generate()
    assert helper in imported
    assert first != second
    assert "other" in (output / "reference" / "run.qmd").read_text(encoding="utf-8")
