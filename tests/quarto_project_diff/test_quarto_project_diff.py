"""Tests of the Quarto project diff that build no package"""

from __future__ import annotations

import json
import os
import subprocess
import textwrap
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from tests.quarto_project_diff.catalogue import Release, make_repository
from tests.quarto_project_diff.__main__ import exit_status
from tests.quarto_project_diff.compare import FailOn, compare, render
from tests.quarto_project_diff.normalise import FILE_RULES, log_skeleton, normalise_text, path_rules
from tests.quarto_project_diff.record import (
    SCHEMA,
    WATCH_MARKER,
    has_watch_marker,
    served_directory,
    store_blob,
)
from tests.quarto_project_diff.sides import (
    PREVIEW_DIRECTORY_VARIABLE,
    RequirementError,
    run_checked,
    write_stub,
)


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


def test_file_rules_mask_the_discovery_key_but_keep_the_sections():
    cache = json.dumps({"key": "ab" * 32, "sections": [{"title": "Functions"}]}, indent=2)
    path = ".great-docs-cache/api-discovery/sections.json"

    text, counts = normalise_text(cache, path, FILE_RULES)
    elsewhere, _ = normalise_text(cache, "data.json", FILE_RULES)

    assert json.loads(text) == {"key": "<DIGEST>", "sections": [{"title": "Functions"}]}
    assert counts == {"discovery-key": 1}
    assert elsewhere == cache


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


def _recording(
    root: Path,
    commands: Mapping[str, Mapping[str, str | None]],
    extra: Mapping[str, Mapping[str, Any]] | None = None,
    **manifest: Any,
) -> Path:
    """
    Write a one-case recording in `root` and return its path

    Process `commands` in order, using each file's content or `None` for a removal.
    A path written by an earlier command counts as changed. Add per-command record keys
    from `extra` and manifest keys, such as `expects_reference`, from `manifest`.
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
            **(extra or {}).get(name, {}),
        }
    content = {"case": "demo", "order": list(records), "commands": records, **manifest}
    (root / "builds").mkdir(parents=True)
    _ = (root / "builds" / "demo.json").write_text(json.dumps(content), encoding="utf-8")
    side = {"schema": SCHEMA, "label": root.name, "cases": ["demo"], "facts": {"python": "3.13"}}
    _ = (root / "side.json").write_text(json.dumps(side), encoding="utf-8")
    return root


def test_comparison_names_the_changed_file(tmp_path: Path):
    base = _recording(tmp_path / "base", {"build": {"docs/index.qmd": "# Title\n"}})
    same = _recording(tmp_path / "same", {"build": {"docs/index.qmd": "# Title\n"}})
    test = _recording(tmp_path / "test", {"build": {"docs/index.qmd": "# Changed title\n"}})

    assert compare(base, same).matches
    result = compare(base, test)

    assert not result.matches
    findings = "\n".join(result.cases[0].findings)
    assert "build: file changed: docs/index.qmd" in findings
    assert "+# Changed title" in findings
    # File changes pass unless `--fail-on difference` is selected.
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
    """Reject recordings made with an older manifest schema"""
    current = _recording(tmp_path / "current", {"build": {}})
    older = _recording(tmp_path / "older", {"build": {}})
    side = json.loads((older / "side.json").read_text(encoding="utf-8"))
    _ = (older / "side.json").write_text(
        json.dumps({**side, "schema": SCHEMA - 1}), encoding="utf-8"
    )

    with pytest.raises(RequirementError, match=f"schema {SCHEMA - 1}"):
        _ = compare(older, current)


def test_freeze_after_build_fails_when_it_prepares_files_unlike_build(tmp_path: Path):
    """Report changed and removed files after a build as a freeze regression"""
    project = "docs/_quarto/default"
    built = {f"{project}/_quarto.yml": "a", f"{project}/_inv/index.lua": "", f"{project}/x.qmd": ""}
    frozen = {f"{project}/_quarto.yml": "b", f"{project}/_inv/index.lua": None}
    fixed = _recording(tmp_path / "fixed", {"build": built, "freeze": {}})
    broken = _recording(tmp_path / "broken", {"build": built, "freeze": frozen})
    meta = json.loads((fixed / "side.json").read_text(encoding="utf-8"))
    meta["facts"] |= {"checkout": "/x", "commit": "0" * 40}

    assert compare(fixed, fixed).matches
    result = compare(fixed, broken)

    assert result.cases[0].checks == [
        "freeze after build prepared 2 files unlike build (base: passes)",
        f"    changed {project}/_quarto.yml",
        f"    removed {project}/_inv/index.lua",
    ]
    assert result.cases[0].regressed
    report = render(result, meta, meta).splitlines()
    start = report.index("demo: DIFFER (regression)") + 1
    assert report[start : start + 3] == [
        "  check failed: freeze after build prepared 2 files unlike build (base: passes)",
        f"      changed {project}/_quarto.yml",
        f"      removed {project}/_inv/index.lua",
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


def test_watch_fails_without_a_rebuild_or_a_clean_stop(tmp_path: Path):
    """Treat missed rebuilds and unclean watch stops as failed checks"""
    stale = _watch_recording(tmp_path / "stale", 0, rebuilt=False)
    rebuilt = _watch_recording(tmp_path / "rebuilt", 0, rebuilt=True)
    crashed = _watch_recording(tmp_path / "crashed", 1, rebuilt=True, traceback=True)
    stuck = _watch_recording(tmp_path / "stuck", "timeout", previewed=False, rebuilt=False)

    assert compare(rebuilt, rebuilt).matches
    result = compare(rebuilt, stale)

    assert result.cases[0].checks == ["watch did not rebuild after a source edit (base: passes)"]
    assert result.cases[0].regressed
    assert compare(crashed, crashed).cases[0].checks == [
        "watch exited with status 1 after the interrupt (base: same)",
        "watch printed a traceback (base: same)",
    ]
    assert compare(stale, stuck).cases[0].checks == [
        "watch never reached the preview after its first build (base: passes)",
        "watch exited with status timeout after the interrupt (base: passes)",
    ]


def test_watch_edit_counts_once_it_reaches_the_previewed_project(tmp_path: Path):
    # Watch mode stages each rebuild in its cache directory before it updates the previewed
    # project, so the marker in the staged copy must not count as a rebuild.
    stub = write_stub(tmp_path / "bin", "false")
    served = tmp_path / "docs" / "_quarto" / "default"
    staged = tmp_path / "docs" / ".cache" / "watch"
    served.mkdir(parents=True)
    staged.mkdir(parents=True)
    preview_file = tmp_path / "preview-directory.txt"
    env = {**os.environ, PREVIEW_DIRECTORY_VARIABLE: str(preview_file)}

    assert served_directory(preview_file) is None
    _ = subprocess.run([str(stub), "preview", "--no-browser"], cwd=served, env=env, check=True)
    assert served_directory(preview_file) == served

    _ = (staged / "configuration.qmd").write_text(WATCH_MARKER, encoding="utf-8")
    assert not has_watch_marker(served)
    (served / "user-guide").mkdir()
    _ = (served / "user-guide" / "configuration.qmd").write_text(WATCH_MARKER, encoding="utf-8")
    assert has_watch_marker(served)


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
