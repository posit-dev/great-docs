"""Harness regression tests without package builds"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

from tests.harness.compare import compare
from tests.harness.normalise import FILE_RULES, log_skeleton, normalise_text, path_rules
from tests.harness.record import read_census, store_blob
from tests.harness.sides import OBSERVER_SOURCE


def test_file_rules_remove_commit_and_build_time_only():
    footer = (
        'center: "Site created with <strong>Great&nbsp;Docs</strong> (<a href=\\"https://'
        'github.com/posit-dev/great-docs/commit/98fefe3d\\">98fefe3d</a>)."'
    )
    meta = '<meta name="gd-build-time" content="2026-10-27T13:04:31.123456">'
    data = '{"published_at": "2025-02-01T12:00:00Z"}'
    text, counts = normalise_text("\n".join([footer, meta, data]), "x", FILE_RULES)

    assert text.splitlines() == [
        'center: "Site created with <strong>Great&nbsp;Docs</strong>."',
        '<meta name="gd-build-time" content="<TIMESTAMP>">',
        data,
    ]
    assert counts == {"great-docs-commit": 1, "iso-timestamp": 1}


def test_path_rules_replace_the_innermost_directory_first(tmp_path: Path):
    package = tmp_path / "job" / "pkg"
    rules = path_rules({"<JOB>": tmp_path / "job", "<PKG>": package})

    text, _ = normalise_text(f"{package}/README.md and {tmp_path / 'job'}", "", rules)

    assert text == "<PKG>/README.md and <JOB>"


def test_log_skeleton_keeps_steps_and_markers_without_timings():
    stdout = textwrap.dedent(
        """\
        ==============================================================================
        |  great-docs build · demo                                                   |
        |  20 steps · estimated ~1 min                                               |
        ==============================================================================

        -- Step  1/20 - Prepare build directory ----------------------------------------
              Preparing build directory: docs/_quarto/default/
           [OK] Ready                                                                  0.2s
        -- Step  5/20 - Generate changelog ---------------------------------------------
           [--] Skipped (no GitHub repo info)
           [!!] No site URL found
        |  [OK] Build complete — 20/20 steps (12 skipped, 1 warning)                 |
        |  Total time: 1m 2.5s                                                       |
        """
    )

    assert log_skeleton(stdout, "Error: 'changelog.enabled'\n") == [
        "Step  1/20 - Prepare build directory",
        "[OK] Ready",
        "Step  5/20 - Generate changelog",
        "[--] Skipped (no GitHub repo info)",
        "[!!] No site URL found",
        "[OK] Build complete — 20/20 steps (12 skipped, 1 warning)",
        "Error: 'changelog.enabled'",
    ]


@pytest.mark.skipif(sys.version_info < (3, 12), reason="the observer needs sys.monitoring")
def test_observer_counts_exceptions_that_great_docs_handles(tmp_path: Path):
    # Only exceptions handled inside the package belong in the census. The caller
    # handles a separate exception to check that the observer excludes it.
    package = tmp_path / "src" / "great_docs"
    package.mkdir(parents=True)
    _ = (package / "__init__.py").write_text(
        textwrap.dedent(
            """\
            def _parse(text):
                return int(text)

            def lenient(text):
                try:
                    return _parse(text)
                except ValueError:
                    return 0
            """
        ),
        encoding="utf-8",
    )
    script = "import great_docs\ngreat_docs.lenient('x')\ntry:\n    {}['k']\nexcept KeyError:\n    pass\n"
    census = tmp_path / "census"
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([str(tmp_path / "src"), str(OBSERVER_SOURCE.parent)]),
        "GREAT_DOCS_HARNESS_CENSUS": str(census),
    }
    _ = subprocess.run([sys.executable, "-c", script], env=env, cwd=tmp_path, check=True)

    entries, processes = read_census(census, path_rules({"<SRC>": tmp_path / "src"}))

    assert processes == 1
    assert entries == [
        {
            "type": "ValueError",
            "message": "invalid literal for int() with base 10: 'x'",
            "raised_in": "_parse",
            "count": 1,
            "raised_at": ["__init__.py:2"],
            "handlers": ["lenient (__init__.py:6)"],
        }
    ]


def _recording(root: Path, page: str, census: list[dict[str, Any]]) -> Path:
    """
    Write a one-case recording with one generated page and the given exception census

    Parameters
    ----------
    root :
        Recording directory to create.
    page :
        Page content stored as a blob.
    census :
        Handled-exception entries to include in the build record.

    Returns
    -------
    :
        The recording directory.
    """
    digest = store_blob(root / "blobs", page.encode())
    files = [{"path": "docs/index.qmd", "change": "added", "kind": "text", "sha256": digest}]
    build = {"status": 0, "files": files, "skeleton": [], "warnings": [], "census": census}
    manifest = {"case": "demo", "commands": {"build": build}}
    (root / "builds").mkdir(parents=True)
    _ = (root / "builds" / "demo.json").write_text(json.dumps(manifest), encoding="utf-8")
    side = {"label": root.name, "cases": ["demo"], "facts": {"python": "3.13"}}
    _ = (root / "side.json").write_text(json.dumps(side), encoding="utf-8")
    return root


def test_comparison_names_the_changed_file_and_the_new_handler(tmp_path: Path):
    handled = {
        "type": "KeyError",
        "message": "'x'",
        "raised_in": "GreatDocs._step",
        "count": 1,
        "raised_at": ["core.py:10"],
        "handlers": ["GreatDocs._step (core.py:12)"],
    }
    base = _recording(tmp_path / "base", "# Title\n", [])
    same = _recording(tmp_path / "same", "# Title\n", [])
    test = _recording(tmp_path / "test", "# Changed title\n", [handled])

    assert compare(base, same).matches
    result = compare(base, test)

    assert not result.matches
    findings = "\n".join(result.cases[0].findings)
    assert "build: file changed: docs/index.qmd" in findings
    assert "+# Changed title" in findings
    assert "NEW handled exception: KeyError" in findings
    assert "handled in GreatDocs._step (core.py:12)" in findings
