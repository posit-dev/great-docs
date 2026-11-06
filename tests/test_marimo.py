"""Tests for great_docs._marimo: marimo notebook integration utilities."""

from __future__ import annotations

import io
import subprocess
import sys
import types
from pathlib import Path

import pytest

from great_docs import _marimo
from great_docs._marimo import (
    _FALLBACK_VERSION,
    _ISLANDS_CDN,
    _tag_setup_islands,
    generate_islands_for_build,
    generate_islands_html,
    get_islands_head_html,
    islands_runtime_version,
    notebook_source,
    parse_marimo_source,
    prepare_notebooks,
)

# ---------------------------------------------------------------------------
# islands_runtime_version
# ---------------------------------------------------------------------------


class TestIslandsRuntimeVersion:
    def test_returns_installed_version(self, monkeypatch):
        fake_marimo = type(sys)("marimo")
        fake_marimo.__version__ = "1.2.3"
        monkeypatch.setitem(sys.modules, "marimo", fake_marimo)
        assert islands_runtime_version() == "1.2.3"

    def test_fallback_when_marimo_missing(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "marimo", None)
        assert islands_runtime_version() == _FALLBACK_VERSION


# ---------------------------------------------------------------------------
# get_islands_head_html
# ---------------------------------------------------------------------------


class TestGetIslandsHeadHtml:
    def test_explicit_version(self):
        html = get_islands_head_html(version="0.99.0")
        assert f"{_ISLANDS_CDN}@0.99.0/dist/main.js" in html
        assert f"{_ISLANDS_CDN}@0.99.0/dist/style.css" in html
        assert "<marimo-filename hidden>" in html

    def test_version_none_uses_runtime(self, monkeypatch):
        fake_marimo = type(sys)("marimo")
        fake_marimo.__version__ = "5.6.7"
        monkeypatch.setitem(sys.modules, "marimo", fake_marimo)
        html = get_islands_head_html(version=None)
        assert f"{_ISLANDS_CDN}@5.6.7/dist/main.js" in html

    def test_includes_font_and_katex(self):
        html = get_islands_head_html(version="1.0.0")
        assert "fonts.googleapis.com" in html
        assert "katex" in html


# ---------------------------------------------------------------------------
# _tag_setup_islands
# ---------------------------------------------------------------------------


class TestTagSetupIslands:
    def _island(self, *, reactive=True, empty_output=True, label="cell"):
        reactive_attr = 'data-reactive="true"' if reactive else 'data-reactive="false"'
        if empty_output:
            output = "<marimo-cell-output><span></span></marimo-cell-output>"
        else:
            output = "<marimo-cell-output><span>Hello</span></marimo-cell-output>"
        return f'<marimo-island {reactive_attr} data-app-id="main">{output}</marimo-island>'

    def test_empty_input_returns_empty(self):
        assert _tag_setup_islands("") == ""

    def test_leading_empty_cells_tagged(self):
        html = self._island(reactive=True, empty_output=True)
        result = _tag_setup_islands(html)
        assert 'data-gd-setup="true"' in result

    def test_non_empty_cell_not_tagged(self):
        html = self._island(reactive=True, empty_output=False)
        result = _tag_setup_islands(html)
        assert 'data-gd-setup="true"' not in result

    def test_leading_run_stops_at_first_output(self):
        empty = self._island(reactive=True, empty_output=True)
        non_empty = self._island(reactive=True, empty_output=False)
        trailing_empty = self._island(reactive=True, empty_output=True)
        html = empty + non_empty + trailing_empty
        result = _tag_setup_islands(html)
        count = result.count('data-gd-setup="true"')
        assert count == 1

    def test_non_reactive_island_skipped(self):
        init = self._island(reactive=False, empty_output=True)
        empty = self._island(reactive=True, empty_output=True)
        html = init + empty
        result = _tag_setup_islands(html)
        assert result.count('data-gd-setup="true"') == 1

    def test_text_between_islands_preserved(self):
        html = "<p>Before</p>" + self._island() + "<p>After</p>"
        result = _tag_setup_islands(html)
        assert "<p>Before</p>" in result
        assert "<p>After</p>" in result


# ---------------------------------------------------------------------------
# parse_marimo_source
# ---------------------------------------------------------------------------

SAMPLE_NOTEBOOK = """\
import marimo

app = marimo.App()

@app.cell()
def imports():
    import pandas as pd
    import numpy as np
    return pd, np

@app.cell()
def analysis(pd):
    df = pd.DataFrame({"a": [1, 2, 3]})
    return df

@app.cell()
def empty_cell():
    # just a comment
    return
"""


class TestParseMarimoSource:
    def test_parses_cells(self):
        cells = parse_marimo_source(SAMPLE_NOTEBOOK)
        names = [c["name"] for c in cells]
        assert "imports" in names
        assert "analysis" in names

    def test_strips_return_and_trailing_blanks(self):
        cells = parse_marimo_source(SAMPLE_NOTEBOOK)
        analysis = next(c for c in cells if c["name"] == "analysis")
        assert "return" not in analysis["code"]
        assert not analysis["code"].endswith("\n\n")

    def test_dedents_body(self):
        cells = parse_marimo_source(SAMPLE_NOTEBOOK)
        imports = next(c for c in cells if c["name"] == "imports")
        assert imports["code"].startswith("import pandas")

    def test_empty_source_returns_empty(self):
        assert parse_marimo_source("") == []

    def test_cell_without_return(self):
        src = (
            "import marimo\napp = marimo.App()\n\n"
            "@app.cell()\n"
            "def side_effect():\n"
            "    print('hello')\n"
        )
        cells = parse_marimo_source(src)
        assert len(cells) == 1
        assert cells[0]["name"] == "side_effect"
        assert "print" in cells[0]["code"]

    def test_blank_line_before_return_stripped(self):
        src = (
            "import marimo\napp = marimo.App()\n\n"
            "@app.cell()\n"
            "def with_gap():\n"
            "    x = 1\n"
            "\n"
            "    return x\n"
        )
        cells = parse_marimo_source(src)
        gap_cell = next(c for c in cells if c["name"] == "with_gap")
        assert gap_cell["code"] == "x = 1"

    def test_cell_with_only_return_excluded(self):
        src = "import marimo\napp = marimo.App()\n\n@app.cell()\ndef noop():\n    return\n"
        cells = parse_marimo_source(src)
        names = [c["name"] for c in cells]
        assert "noop" not in names


# ---------------------------------------------------------------------------
# notebook_source
# ---------------------------------------------------------------------------


class TestNotebookSource:
    def test_reads_file_content(self, tmp_path):
        nb = tmp_path / "demo.py"
        nb.write_text("import marimo\n", encoding="utf-8")
        assert notebook_source(nb) == "import marimo\n"


# ---------------------------------------------------------------------------
# generate_islands_html / generate_islands_for_build
# ---------------------------------------------------------------------------

_ISLANDS = (
    '<marimo-island data-app-id="main" data-reactive="true">'
    "<marimo-cell-output><span></span></marimo-cell-output></marimo-island>"
    '<marimo-island data-app-id="main" data-reactive="true">'
    "<marimo-cell-output><span>out</span></marimo-cell-output></marimo-island>"
)


class _FakeIslandGenerator:
    """A marimo island generator stand-in that avoids kernel subprocesses"""

    from_file_calls: list[tuple[str, bool]] = []
    build_error: Exception | None = None

    def __init__(self) -> None:
        self.render_calls: list[tuple[bool, str]] = []

    @classmethod
    def from_file(cls, path: str, *, display_code: bool) -> _FakeIslandGenerator:
        cls.from_file_calls.append((path, display_code))
        return cls()

    async def build(self) -> None:
        if self.build_error is not None:
            raise self.build_error

    def render_body(self, *, include_init_island: bool, max_width: str) -> str:
        self.render_calls.append((include_init_island, max_width))
        return _ISLANDS


@pytest.fixture
def fake_marimo(monkeypatch: pytest.MonkeyPatch) -> type[_FakeIslandGenerator]:
    class Generator(_FakeIslandGenerator):
        from_file_calls: list[tuple[str, bool]] = []
        build_error: Exception | None = None

    module = types.ModuleType("marimo")
    module.MarimoIslandGenerator = Generator  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "marimo", module)
    return Generator


class TestGenerateIslandsHtml:
    def test_tags_setup_cells_and_names_the_app_after_the_notebook(
        self, fake_marimo: type[_FakeIslandGenerator], tmp_path: Path
    ):
        html = generate_islands_html(tmp_path / "demo.py")

        assert fake_marimo.from_file_calls == [(str(tmp_path / "demo.py"), True)]
        assert html.count('data-gd-setup="true"') == 1
        assert html.count('data-app-id="demo"') == 2
        assert html.count('data-reactive="true"') == 2

    def test_without_code_or_reactivity_leaves_cells_untagged_and_static(
        self, fake_marimo: type[_FakeIslandGenerator], tmp_path: Path
    ):
        html = generate_islands_html(
            tmp_path / "demo.py", display_code=False, reactive=False, app_id="custom"
        )

        assert fake_marimo.from_file_calls == [(str(tmp_path / "demo.py"), False)]
        assert "data-gd-setup" not in html
        assert html.count('data-app-id="custom"') == 2
        assert 'data-reactive="true"' not in html
        assert html.count('data-reactive="false"') == 2

    def test_keeps_the_main_app_id(self, fake_marimo: type[_FakeIslandGenerator], tmp_path: Path):
        html = generate_islands_html(tmp_path / "demo.py", app_id="main")

        assert html.count('data-app-id="main"') == 2

    def test_restores_streams_when_a_cell_run_fails(
        self, fake_marimo: type[_FakeIslandGenerator], tmp_path: Path
    ):
        fake_marimo.build_error = RuntimeError("kernel died")
        stdout, stderr = sys.stdout, sys.stderr

        with pytest.raises(RuntimeError, match="kernel died"):
            generate_islands_html(tmp_path / "demo.py")

        assert sys.stdout is stdout
        assert sys.stderr is stderr


class TestGenerateIslandsForBuild:
    def test_writes_the_islands_creating_missing_directories(
        self, fake_marimo: type[_FakeIslandGenerator], tmp_path: Path
    ):
        output = tmp_path / "build" / "_marimo_islands" / "demo.html"

        generate_islands_for_build(tmp_path / "demo.py", output, app_id="custom")

        html = output.read_text(encoding="utf-8")
        assert html.count('data-app-id="custom"') == 2
        assert html.count('data-gd-setup="true"') == 1

    def test_passes_display_code_and_reactive_through(
        self, fake_marimo: type[_FakeIslandGenerator], tmp_path: Path
    ):
        output = tmp_path / "demo-nocode.html"

        generate_islands_for_build(tmp_path / "demo.py", output, display_code=False, reactive=False)

        html = output.read_text(encoding="utf-8")
        assert fake_marimo.from_file_calls == [(str(tmp_path / "demo.py"), False)]
        assert 'data-reactive="false"' in html
        assert "data-gd-setup" not in html


# ---------------------------------------------------------------------------
# prepare_notebooks
# ---------------------------------------------------------------------------


def _found(name: str) -> object:
    return object()


def _missing(name: str) -> None:
    return None


class _Exporter:
    """A stand-in for `marimo export html-wasm` that writes a fixed page or fails"""

    def __init__(self, page: str | None, stderr: str = "") -> None:
        self.page = page
        self.stderr = stderr

    def __call__(self, args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if self.page is None:
            return subprocess.CompletedProcess(args, 1, stdout="", stderr=self.stderr)
        output_dir = Path(args[args.index("-o") + 1])
        (output_dir / "index.html").write_text(self.page, encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")


class TestPrepareNotebooks:
    @pytest.fixture
    def source_dir(self, tmp_path: Path) -> Path:
        notebooks = tmp_path / "docs" / "notebooks"
        notebooks.mkdir(parents=True)
        (notebooks / "demo.py").write_text("import marimo\n", encoding="utf-8")
        (notebooks / "data.json").write_text("{}", encoding="utf-8")
        return tmp_path / "docs"

    @pytest.fixture
    def islands(self, monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, bool]]:
        """Record island filenames and whether each variant shows code"""
        written: list[tuple[str, bool]] = []

        def generate(notebook: Path, output: Path, *, display_code: bool = True) -> None:
            written.append((output.name, display_code))

        monkeypatch.setattr(_marimo.importlib.util, "find_spec", _found)
        monkeypatch.setattr(_marimo, "generate_islands_for_build", generate)
        return written

    def test_copies_notebooks_and_writes_both_island_variants(
        self,
        source_dir: Path,
        tmp_path: Path,
        islands: list[tuple[str, bool]],
        monkeypatch: pytest.MonkeyPatch,
    ):
        build_dir = tmp_path / "build"
        monkeypatch.setattr(_marimo.subprocess, "run", _Exporter("<body></body>"))
        prepare_notebooks(source_dir, build_dir, report=print, warn=pytest.fail)

        assert (build_dir / "notebooks" / "data.json").read_text() == "{}"
        assert islands == [("demo.html", True), ("demo-nocode.html", False)]
        index = (build_dir / "notebooks" / "demo" / "index.html").read_text()
        assert index.count("great-docs:marimo-autorun") == 1
        assert index.endswith("</script>\n</body>")

    def test_leaves_an_export_that_already_runs_its_cells(
        self,
        source_dir: Path,
        tmp_path: Path,
        islands: list[tuple[str, bool]],
        monkeypatch: pytest.MonkeyPatch,
    ):
        page = "<body><!-- great-docs:marimo-autorun --></body>"
        build_dir = tmp_path / "build"
        monkeypatch.setattr(_marimo.subprocess, "run", _Exporter(page))
        prepare_notebooks(source_dir, build_dir, report=print, warn=pytest.fail)

        assert (build_dir / "notebooks" / "demo" / "index.html").read_text() == page

    def test_warns_when_the_export_fails(
        self,
        source_dir: Path,
        tmp_path: Path,
        islands: list[tuple[str, bool]],
        monkeypatch: pytest.MonkeyPatch,
    ):
        warnings: list[str] = []
        monkeypatch.setattr(_marimo.subprocess, "run", _Exporter(None, stderr="  no kernel  "))
        prepare_notebooks(source_dir, tmp_path / "build", report=print, warn=warnings.append)

        assert warnings == [
            "Warning: marimo WASM export failed for demo.py (iframe mode will 404). no kernel"
        ]

    def test_reports_missing_marimo_and_copies_nothing(
        self, source_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        reports: list[str] = []
        monkeypatch.setattr(_marimo.importlib.util, "find_spec", _missing)
        prepare_notebooks(source_dir, tmp_path / "build", report=reports.append, warn=pytest.fail)

        assert len(reports) == 1
        assert "'marimo' package is not installed" in reports[0]
        assert not (tmp_path / "build").exists()

    def test_gives_streams_an_encoding_while_generating_islands(
        self, source_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # The build log's detail stream has no `encoding`, which the marimo import reads.
        class DetailStream(io.RawIOBase):
            pass

        detail = DetailStream()
        seen: list[bool] = []

        def generate(notebook: Path, output: Path, *, display_code: bool = True) -> None:
            seen.append(hasattr(sys.stdout, "encoding"))

        monkeypatch.setattr(_marimo.importlib.util, "find_spec", _found)
        monkeypatch.setattr(_marimo, "generate_islands_for_build", generate)
        monkeypatch.setattr(_marimo.subprocess, "run", _Exporter("<body></body>"))
        monkeypatch.setattr(sys, "stdout", detail)
        prepare_notebooks(source_dir, tmp_path / "build", report=print, warn=pytest.fail)

        assert seen == [True, True]
        assert sys.stdout is detail
