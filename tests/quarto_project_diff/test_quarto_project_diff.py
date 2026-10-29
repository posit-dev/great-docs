"""Tests of the Quarto project diff that build no package"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from tests.quarto_project_diff.catalogue import Release, make_repository
from tests.quarto_project_diff.__main__ import exit_status
from tests.quarto_project_diff.compare import FailOn, compare, render
from tests.quarto_project_diff.normalise import FILE_RULES, log_skeleton, normalise_text, path_rules
from tests.quarto_project_diff.record import SCHEMA, read_census, store_blob
from tests.quarto_project_diff.sides import OBSERVER_SOURCE, RequirementError, run_checked


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


def test_file_rules_remove_a_commit_folded_across_lines():
    footer = textwrap.dedent(
        """\
        center: >-
          Site created with <strong>Great&nbsp;Docs</strong> (<a
          href="https://github.com/posit-dev/great-docs/commit/3f8d0ffb">3f8d0ffb</a>).
        """
    )
    text, counts = normalise_text(footer, "x", FILE_RULES)

    assert text == "center: >-\n  Site created with <strong>Great&nbsp;Docs</strong>.\n"
    assert counts == {"great-docs-commit": 1}


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
        "GREAT_DOCS_QUARTO_PROJECT_DIFF_CENSUS": str(census),
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


def _recording(
    root: Path,
    commands: Mapping[str, Mapping[str, str | None]],
    census: Sequence[Mapping[str, Any]] = (),
    extra: Mapping[str, Mapping[str, Any]] | None = None,
    **manifest: Any,
) -> Path:
    """
    Write a one-case recording from the files each command wrote

    Parameters
    ----------
    root :
        Recording directory to create.
    commands :
        For each command in order, the content of each file it wrote, or `None` for a file
        it removed. A path that an earlier command wrote counts as changed.
    census :
        Handled-exception entries of every command.
    extra :
        Further record keys per command.
    **manifest :
        Further manifest keys, such as `expects_reference`.

    Returns
    -------
    :
        The recording directory.
    """
    records: dict[str, Any] = {}
    written: set[str] = set()
    for name, pages in commands.items():
        files: list[dict[str, Any]] = []
        for path, page in pages.items():
            if page is None:
                files.append({"path": path, "change": "removed"})
                continue
            change = "changed" if path in written else "added"
            digest = store_blob(root / "blobs", page.encode())
            files.append({"path": path, "change": change, "kind": "text", "sha256": digest})
            written.add(path)
        records[name] = {
            "status": 0,
            "files": files,
            "skeleton": [],
            "warnings": [],
            "census": list(census),
            **(extra or {}).get(name, {}),
        }
    content = {"case": "demo", "order": list(records), "commands": records, **manifest}
    (root / "builds").mkdir(parents=True)
    _ = (root / "builds" / "demo.json").write_text(json.dumps(content), encoding="utf-8")
    side = {"schema": SCHEMA, "label": root.name, "cases": ["demo"], "facts": {"python": "3.13"}}
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
    base = _recording(tmp_path / "base", {"build": {"docs/index.qmd": "# Title\n"}})
    same = _recording(tmp_path / "same", {"build": {"docs/index.qmd": "# Title\n"}})
    test = _recording(
        tmp_path / "test", {"build": {"docs/index.qmd": "# Changed title\n"}}, [handled]
    )

    assert compare(base, same).matches
    result = compare(base, test)

    assert not result.matches
    findings = "\n".join(result.cases[0].findings)
    assert "build: file changed: docs/index.qmd" in findings
    assert "+# Changed title" in findings
    assert "NEW handled exception: KeyError" in findings
    assert "handled in GreatDocs._step (core.py:12)" in findings
    # Differences without a regression pass, unless the run fails on any difference
    assert not result.cases[0].regressed
    assert result.passes()
    assert not result.passes("difference")


def test_comparison_fails_when_the_test_side_lacks_an_expected_reference_index(tmp_path: Path):
    project = "docs/_quarto/default"
    complete = {f"{project}/_quarto.yml": "", f"{project}/reference/index.qmd": ""}
    partial = {f"{project}/_quarto.yml": ""}
    without = _recording(tmp_path / "without", {"build": partial}, expects_reference=True)
    also_without = _recording(tmp_path / "also", {"build": partial}, expects_reference=True)
    good = _recording(tmp_path / "good", {"build": complete}, expects_reference=True)
    unexpected = _recording(tmp_path / "unexpected", {"build": partial}, expects_reference=False)

    result = compare(without, also_without)

    assert not result.matches
    assert result.cases[0].status == "fail"
    assert result.cases[0].checks == [f"{project}/reference/index.qmd is missing (base: same)"]
    assert not result.passes()
    assert compare(good, good).matches
    assert compare(unexpected, unexpected).matches
    assert compare(good, without).cases[0].checks == [
        f"{project}/reference/index.qmd is missing (base: passes)"
    ]


def test_comparison_refuses_a_recording_from_another_recording_schema(tmp_path: Path):
    current = _recording(tmp_path / "current", {"build": {}})
    older = _recording(tmp_path / "older", {"build": {}})
    side = json.loads((older / "side.json").read_text(encoding="utf-8"))
    _ = (older / "side.json").write_text(json.dumps({**side, "schema": 1}), encoding="utf-8")

    with pytest.raises(RequirementError, match="schema 1"):
        _ = compare(older, current)


def test_freeze_after_build_reports_what_it_prepares_differently_as_a_known_gap(tmp_path: Path):
    project = "docs/_quarto/default"
    built = {f"{project}/_quarto.yml": "a", f"{project}/_inv/index.lua": "", f"{project}/x.qmd": ""}
    frozen = {f"{project}/_quarto.yml": "b", f"{project}/_inv/index.lua": None}
    base = _recording(tmp_path / "base", {"build": built, "freeze": frozen})
    same = _recording(tmp_path / "same", {"build": built, "freeze": frozen})
    fixed = _recording(tmp_path / "fixed", {"build": built, "freeze": {}})

    result = compare(base, same)

    assert result.matches
    assert result.cases[0].known_gaps == [
        "freeze prepares 2 files unlike build [freeze-steps] (base: same)",
        f"    changed {project}/_quarto.yml",
        f"    removed {project}/_inv/index.lua",
    ]
    assert compare(base, fixed).cases[0].known_gaps == [
        "closed: freeze prepares 2 files unlike build [freeze-steps]"
    ]


def test_release_repositories_of_one_package_have_the_same_commits(tmp_path: Path):
    releases = (Release("v0.1"), Release("v0.2", {"pkg.py": "VALUE = 2\n"}))
    heads: list[str] = []
    for name in ("one", "two"):
        package = tmp_path / name
        package.mkdir()
        _ = (package / "pkg.py").write_text("VALUE = 1\n", encoding="utf-8")
        make_repository(package, releases)
        heads.append(run_checked(["git", "rev-parse", "v0.1", "v0.2"], package))

    assert heads[0] == heads[1]
    assert len(set(heads[0].split())) == 2


def _watch_recording(root: Path, status: int | str, **facts: bool) -> Path:
    """
    Write a recording of one watch command with the given exit status and watch facts

    Parameters
    ----------
    root :
        Recording directory to create.
    status :
        Exit status of the watch command.
    **facts :
        Values of `previewed`, `rebuilt` and `traceback`.

    Returns
    -------
    :
        The recording directory.
    """
    watch = {"status": status, "watch": {"previewed": True, "traceback": False, **facts}}
    return _recording(root, {"watch": {}}, extra={"watch": watch})


def test_watch_without_rebuild_is_a_known_gap_and_a_crash_fails(tmp_path: Path):
    stale = _watch_recording(tmp_path / "stale", 0, rebuilt=False)
    rebuilt = _watch_recording(tmp_path / "rebuilt", 0, rebuilt=True)
    crashed = _watch_recording(tmp_path / "crashed", 1, rebuilt=False, traceback=True)
    stuck = _watch_recording(tmp_path / "stuck", "timeout", previewed=False, rebuilt=False)

    result = compare(stale, stale)

    assert result.matches
    assert result.cases[0].known_gaps == [
        "watch mode does not rebuild after a source edit [watch-rebuild] (base: same)"
    ]
    assert compare(rebuilt, rebuilt).cases[0].known_gaps == []
    assert compare(stale, rebuilt).cases[0].status == "differ"
    assert compare(crashed, crashed).cases[0].checks == [
        "watch exited with status 1 after the interrupt (base: same)",
        "watch printed a traceback (base: same)",
    ]
    assert compare(stale, stuck).cases[0].checks == [
        "watch never reached the preview after its first build (base: passes)",
        "watch exited with status timeout after the interrupt (base: passes)",
    ]


def test_a_command_that_starts_failing_is_a_regression(tmp_path: Path):
    def side(name: str, status: int) -> Path:
        return _recording(tmp_path / name, {"build": {}}, extra={"build": {"status": status}})

    ok, broken, other = side("ok", 0), side("broken", 1), side("other", 2)

    result = compare(ok, broken)
    assert result.cases[0].regressions == ["build: exit status 0 -> 1"]
    assert not result.passes()
    assert compare(broken, other).cases[0].regressions == ["build: exit status 1 -> 2"]
    # A fix is a difference, not a regression
    fixed = compare(broken, ok)
    assert fixed.cases[0].status == "differ" and fixed.passes()


def test_a_command_run_on_one_side_only_is_a_regression(tmp_path: Path):
    base = _recording(tmp_path / "base", {"init": {}, "build": {}})
    test = _recording(tmp_path / "test", {"build": {}})

    result = compare(base, test)

    assert result.cases[0].regressions == ["init: run on one side only"]
    assert not result.passes()


def test_report_verdict_and_exit_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    base = _recording(tmp_path / "base", {"build": {"docs/index.qmd": "a"}})
    changed = _recording(tmp_path / "changed", {"build": {"docs/index.qmd": "b"}})
    broken = _recording(
        tmp_path / "broken", {"build": {"docs/index.qmd": "a"}}, extra={"build": {"status": 1}}
    )
    meta = json.loads((base / "side.json").read_text(encoding="utf-8"))
    meta["facts"] |= {"checkout": "/x", "commit": "0" * 40}

    def verdict(result: Any, fail_on: FailOn = "regression") -> str:
        return render(result, meta, meta, fail_on).splitlines()[-1]

    differs = compare(base, changed)
    assert verdict(compare(base, base)) == "MATCH: all 1 cases"
    assert verdict(compare(base, base), "difference") == "MATCH: all 1 cases"
    assert verdict(differs) == "DIFFER: 1 of 1 cases; no regressions, so the run passes"
    assert verdict(differs, "difference") == (
        "DIFFER: 1 of 1 cases; no regressions, but --fail-on difference fails the run"
    )
    regressed = compare(base, broken)
    assert verdict(regressed) == "DIFFER: 1 of 1 cases; 1 regressed"
    assert "demo: DIFFER (regression)" in render(regressed, meta, meta)
    assert "  regression: build: exit status 0 -> 1" in render(regressed, meta, meta)

    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert exit_status(differs, "regression") == 0
    assert capsys.readouterr().out.startswith("::warning title=Quarto project differences::1 of 1")
    assert exit_status(differs, "difference") == 1
    assert exit_status(regressed, "regression") == 1
    assert exit_status(compare(base, base), "regression") == 0
    assert capsys.readouterr().out == ""
