"""
Test on-demand Great Docs Gauntlet site builds

The fixture builder makes rendered citation packages available during a default
test run. Most tests use a stub builder to avoid invoking Quarto.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from tests.gauntlet_sites import (
    CITATION_SITES,
    RENDERED_DIR,
    build_site,
    ensure_sites,
    quarto_available,
    sentinel_path,
    site_dir,
)

requires_quarto = pytest.mark.skipif(not quarto_available(), reason="Quarto is not installed")


def _make_site(rendered_dir: Path, name: str) -> Path:
    """Create the directory layout for a rendered package"""
    target = site_dir(rendered_dir, name)
    target.mkdir(parents=True)
    (target / "index.html").write_text("<html></html>", encoding="utf-8")
    return target


def test_citation_site_names_resolve_to_specs():
    """
    Verify each citation site names an existing Gauntlet specification

    Site build failures warn instead of aborting collection. Validate the
    allowlist directly so a misspelt package name cannot silently remove
    citation coverage.
    """
    import tests.gauntlet_sites as gauntlet_sites

    sys.path.insert(0, str(gauntlet_sites._TEST_PACKAGES_DIR))
    from synthetic.catalog import get_spec

    for name in CITATION_SITES:
        assert get_spec(name)["name"] == name


def test_existing_site_is_not_rebuilt(tmp_path: Path):
    """Verify an existing rendered site remains unchanged"""
    _make_site(tmp_path, "gdtest_minimal")
    calls: list[str] = []

    def stub(rendered_dir: Path, name: str) -> Path:
        calls.append(name)
        return _make_site(rendered_dir, name)

    assert ensure_sites(tmp_path, ["gdtest_minimal"], builder=stub) == []
    assert calls == []


def test_missing_site_is_built(tmp_path: Path):
    """Verify each missing rendered site is built"""
    calls: list[str] = []

    def stub(rendered_dir: Path, name: str) -> Path:
        calls.append(name)
        return _make_site(rendered_dir, name)

    built = ensure_sites(tmp_path, ["gdtest_a", "gdtest_b"], builder=stub)
    assert built == ["gdtest_a", "gdtest_b"]
    assert calls == ["gdtest_a", "gdtest_b"]


def test_builder_failure_does_not_stop_the_remaining_packages(tmp_path: Path):
    """
    Verify one failed build does not prevent later builds

    Leave the failed site unavailable so its rendered-output tests skip, then
    continue building the remaining sites.
    """

    def stub(rendered_dir: Path, name: str) -> Path:
        if name == "gdtest_a":
            raise OSError("Quarto render failed")
        return _make_site(rendered_dir, name)

    with pytest.warns(UserWarning, match="could not build Gauntlet site gdtest_a"):
        built = ensure_sites(tmp_path, ["gdtest_a", "gdtest_b"], builder=stub)

    assert built == ["gdtest_b"]
    assert not site_dir(tmp_path, "gdtest_a").is_dir()


def test_unexpected_builder_exception_propagates(tmp_path: Path):
    """
    Verify an unexpected builder exception propagates

    Exceptions outside `BUILD_FAILURES` indicate builder defects rather than
    unavailable fixtures.
    """

    def stub(rendered_dir: Path, name: str) -> Path:
        raise ZeroDivisionError("bug in the builder")

    with pytest.raises(ZeroDivisionError):
        ensure_sites(tmp_path, ["gdtest_a"], builder=stub)


def test_sentinel_is_a_sibling_of_the_package_directory(tmp_path: Path):
    """
    Verify the sentinel remains outside the package directory

    Regenerating a package replaces its directory. Keeping the sentinel beside
    that directory preserves the lock throughout the build.
    """
    assert sentinel_path(tmp_path, "gdtest_minimal") == tmp_path / ".gdtest_minimal.building"


def test_builder_holds_the_sentinel_until_the_build_finishes(tmp_path: Path):
    """Verify the build holds its sentinel and then releases it"""

    def stub(rendered_dir: Path, name: str) -> Path:
        assert sentinel_path(rendered_dir, name).exists(), "build sentinel is missing"
        return _make_site(rendered_dir, name)

    ensure_sites(tmp_path, ["gdtest_a"], builder=stub)
    assert not sentinel_path(tmp_path, "gdtest_a").exists()


def test_failed_build_releases_the_sentinel(tmp_path: Path):
    """
    Verify a failed build releases the lock

    A sentinel left behind by a crash would make every later session wait out
    the full timeout.
    """

    def stub(rendered_dir: Path, name: str) -> Path:
        raise OSError("Quarto render failed")

    with pytest.warns(UserWarning, match="could not build Gauntlet site gdtest_a"):
        ensure_sites(tmp_path, ["gdtest_a"], builder=stub)

    assert not sentinel_path(tmp_path, "gdtest_a").exists()


def test_build_failure_is_not_reported_as_a_lock_failure(tmp_path: Path):
    """
    Verify a builder `OSError` is reported as a build failure

    Lock acquisition and site building can both raise `OSError`. Report the
    stage that failed so the warning identifies the correct cause.
    """

    def stub(rendered_dir: Path, name: str) -> Path:
        raise OSError("Quarto render failed")

    with pytest.warns(UserWarning) as record:
        built = ensure_sites(tmp_path, ["gdtest_a"], builder=stub)

    assert built == []
    messages = [str(warning.message) for warning in record]
    assert any("could not build Gauntlet site gdtest_a" in message for message in messages)
    assert not any("could not claim the build lock" in message for message in messages)


def test_propagating_exception_releases_the_sentinel(tmp_path: Path):
    """Verify a propagating exception releases the sentinel"""

    def stub(rendered_dir: Path, name: str) -> Path:
        raise ZeroDivisionError("bug in the builder")

    with pytest.raises(ZeroDivisionError):
        ensure_sites(tmp_path, ["gdtest_a"], builder=stub)

    assert not sentinel_path(tmp_path, "gdtest_a").exists()


def test_second_process_waits_for_the_active_build(tmp_path: Path):
    """
    Verify a second process waits for an active build

    An existing sentinel represents another pytest-xdist process. The second
    process waits for the site and reports that it built nothing.
    """
    sentinel_path(tmp_path, "gdtest_a").parent.mkdir(parents=True, exist_ok=True)
    sentinel_path(tmp_path, "gdtest_a").write_text(str(os.getpid()))
    calls: list[str] = []

    def stub(rendered_dir: Path, name: str) -> Path:
        calls.append(name)
        return _make_site(rendered_dir, name)

    def finish_the_build():
        time.sleep(0.3)
        _make_site(tmp_path, "gdtest_a")
        sentinel_path(tmp_path, "gdtest_a").unlink()

    worker = threading.Thread(target=finish_the_build)
    worker.start()
    built = ensure_sites(tmp_path, ["gdtest_a"], builder=stub, timeout=10.0)
    worker.join()

    assert built == []
    assert calls == []
    assert site_dir(tmp_path, "gdtest_a").is_dir()


def test_waiting_process_returns_after_the_timeout(tmp_path: Path):
    """Verify waiting for an active build respects the timeout"""
    sentinel_path(tmp_path, "gdtest_a").parent.mkdir(parents=True, exist_ok=True)
    sentinel_path(tmp_path, "gdtest_a").write_text(str(os.getpid()))

    def stub(rendered_dir: Path, name: str) -> Path:
        raise AssertionError("builder ran while another process held the sentinel")

    started = time.monotonic()
    with pytest.warns(UserWarning, match="gdtest_a"):
        built = ensure_sites(tmp_path, ["gdtest_a"], builder=stub, timeout=0.5)

    assert built == []
    assert time.monotonic() - started < 5.0


def test_sentinel_with_non_numeric_value_is_replaced(tmp_path: Path):
    """Verify a non-numeric sentinel value is stale"""
    calls: list[str] = []

    def stub(rendered_dir: Path, name: str) -> Path:
        calls.append(name)
        return _make_site(rendered_dir, name)

    sentinel_path(tmp_path, "gdtest_a").parent.mkdir(parents=True, exist_ok=True)
    sentinel_path(tmp_path, "gdtest_a").write_text("not-a-pid")

    built = ensure_sites(tmp_path, ["gdtest_a"], builder=stub, timeout=10.0)

    assert built == ["gdtest_a"]
    assert calls == ["gdtest_a"]
    assert site_dir(tmp_path, "gdtest_a").is_dir()


def test_live_process_retains_sentinel_after_wait_timeout(tmp_path: Path):
    """
    Verify a live process retains its sentinel after a waiter times out

    The wait timeout limits how long another process blocks. The longer
    live-process threshold limits when that process may replace the sentinel.
    A valid Quarto render can consume the full render timeout without making
    its sentinel stale.
    """
    import tests.gauntlet_sites as gauntlet_sites

    def stub(rendered_dir: Path, name: str) -> Path:
        raise AssertionError("builder ran while another process held the sentinel")

    sentinel_path(tmp_path, "gdtest_a").parent.mkdir(parents=True, exist_ok=True)
    sentinel_path(tmp_path, "gdtest_a").write_text(str(os.getpid()))

    # Exceed the wait timeout while remaining within the live-process limit.
    sentinel_file = sentinel_path(tmp_path, "gdtest_a")
    old_time = time.time() - gauntlet_sites._RENDER_TIMEOUT_SECONDS
    os.utime(sentinel_file, (old_time, old_time))
    assert gauntlet_sites._LIVE_HOLDER_STALE_SECONDS > gauntlet_sites._RENDER_TIMEOUT_SECONDS

    with pytest.warns(UserWarning, match="gdtest_a"):
        built = ensure_sites(tmp_path, ["gdtest_a"], builder=stub, timeout=0.5)

    assert built == []
    assert sentinel_path(tmp_path, "gdtest_a").exists()


def test_expired_live_process_sentinel_is_replaced(tmp_path: Path):
    """
    Verify a live process loses an expired sentinel

    Treat a sentinel older than the live-process threshold as stale even when
    its PID still exists. This limit prevents a stalled process from blocking
    later test sessions indefinitely.
    """
    import tests.gauntlet_sites as gauntlet_sites

    calls: list[str] = []

    def stub(rendered_dir: Path, name: str) -> Path:
        calls.append(name)
        return _make_site(rendered_dir, name)

    sentinel_path(tmp_path, "gdtest_a").parent.mkdir(parents=True, exist_ok=True)
    sentinel_path(tmp_path, "gdtest_a").write_text(str(os.getpid()))

    sentinel_file = sentinel_path(tmp_path, "gdtest_a")
    old_time = time.time() - (gauntlet_sites._LIVE_HOLDER_STALE_SECONDS + 1.0)
    os.utime(sentinel_file, (old_time, old_time))

    built = ensure_sites(tmp_path, ["gdtest_a"], builder=stub, timeout=5.0)

    assert built == ["gdtest_a"]
    assert calls == ["gdtest_a"]
    assert site_dir(tmp_path, "gdtest_a").is_dir()


def test_sentinel_for_an_exited_process_is_replaced(tmp_path: Path):
    """
    Verify a sentinel for an exited process is replaced

    A valid PID does not keep the sentinel active after its process exits.
    """
    calls: list[str] = []

    def stub(rendered_dir: Path, name: str) -> Path:
        calls.append(name)
        return _make_site(rendered_dir, name)

    proc = subprocess.Popen([sys.executable, "-c", ""], stdout=subprocess.DEVNULL)
    dead_pid = proc.pid
    proc.wait()

    sentinel_path(tmp_path, "gdtest_a").parent.mkdir(parents=True, exist_ok=True)
    sentinel_path(tmp_path, "gdtest_a").write_text(str(dead_pid))

    built = ensure_sites(tmp_path, ["gdtest_a"], builder=stub, timeout=10.0)

    assert built == ["gdtest_a"]
    assert calls == ["gdtest_a"]
    assert site_dir(tmp_path, "gdtest_a").is_dir()


def test_released_sentinel_is_reclaimed_before_waiting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """
    Verify a released sentinel is reclaimed before waiting

    The original owner can release the sentinel between a failed claim and the
    subsequent staleness check. Retry the claim immediately because no process
    may remain responsible for building the site.
    """
    import tests.gauntlet_sites as gauntlet_sites

    calls: list[str] = []

    def stub(rendered_dir: Path, name: str) -> Path:
        calls.append(name)
        return _make_site(rendered_dir, name)

    sentinel = sentinel_path(tmp_path, "gdtest_a")
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.write_text(str(os.getpid()))

    real_is_stale = gauntlet_sites._sentinel_is_stale

    def vanish_then_check(rendered_dir: Path, name: str) -> tuple[bool, tuple[int, int] | None]:
        # Release the sentinel between the failed claim and staleness check.
        sentinel.unlink()
        return real_is_stale(rendered_dir, name)

    monkeypatch.setattr(gauntlet_sites, "_sentinel_is_stale", vanish_then_check)

    built = ensure_sites(tmp_path, ["gdtest_a"], builder=stub, timeout=5.0)

    assert built == ["gdtest_a"]
    assert calls == ["gdtest_a"]
    assert site_dir(tmp_path, "gdtest_a").is_dir()


def test_site_dir_matches_the_rendered_output_tests():
    """
    Verify the builder and rendered-output tests resolve the same site

    A different root or directory layout would make the builder publish sites
    that the rendered-output tests never discover.
    """
    from tests.test_gdg_rendered import _RENDERED_DIR, _site_dir

    assert RENDERED_DIR == _RENDERED_DIR, (
        "the fixture builder and rendered-output tests use different roots"
    )
    assert _site_dir("gdtest_minimal") == site_dir(_RENDERED_DIR, "gdtest_minimal")


def test_site_dir_of_an_unbuilt_package_stays_under_the_rendered_root(tmp_path: Path):
    """
    Keep an absent package lookup inside the rendered fixture root

    An unguarded `Layout.make` call searches upwards for a project manifest and
    can return the enclosing repository's site or configuration instead.
    Guard both lookups so missing packages remain inside the fixture tree.
    """
    from tests.test_gdg_rendered import _config_path, _site_dir

    resolved = site_dir(tmp_path, "gdtest_never_built_xyz")
    assert resolved.is_relative_to(tmp_path)
    assert _site_dir("gdtest_never_built_xyz").is_relative_to(RENDERED_DIR)
    assert not _config_path("gdtest_never_built_xyz").exists()


@requires_quarto
def test_build_site_renders_citation_html(tmp_path: Path):
    """
    Verify a built site contains the required citation markup

    Exercise the complete rendering pipeline from loading the generated package
    through writing API-reference pages and rendering citation anchors,
    superscripts, and backlinks with Quarto.
    """
    built = build_site(tmp_path, "gdtest_docstring_references")

    assert built == site_dir(tmp_path, "gdtest_docstring_references")
    page = built / "reference" / "quicksort.html"
    assert page.exists(), f"expected quicksort.html in {sorted(built.rglob('*.html'))}"

    html = page.read_text(encoding="utf-8")
    assert "gd-cite-ref" in html, "rendered page has no citation-reference class"
    assert "<sup>1</sup>" in html, "citation reference is not a superscript"
    assert "#cite-gdtest_docstring_references-quicksort-1" in html, "citation has no anchor"
    assert "gd-linkback-caret" in html, "citation has no backlink to its reference"
    assert ".. [1]" not in html, "rendered HTML contains raw RST citation markup"


@requires_quarto
def test_build_site_deploys_the_citation_styles(tmp_path: Path):
    """
    Verify the compiled theme includes the citation styles

    Citation markup requires the corresponding backlink classes from the
    deployed theme.
    """
    built = build_site(tmp_path, "gdtest_docstring_references")
    css = "\n".join(
        f.read_text(encoding="utf-8") for f in sorted(built.glob("site_libs/bootstrap/*.css"))
    )
    assert "gd-linkback-letter" in css, "deployed theme has no citation backlink styles"


@requires_quarto
def test_build_site_replaces_an_incomplete_package(tmp_path: Path):
    """
    Verify a package without a rendered site is replaced

    A failed Gauntlet build can leave generated source without a `_site`
    directory. Replace that incomplete package instead of merging old and new
    output.
    """
    stale = tmp_path / "gdtest_docstring_references"
    (stale / "leftover").mkdir(parents=True)

    built = build_site(tmp_path, "gdtest_docstring_references")

    assert built.is_dir()
    assert not (stale / "leftover").exists(), "published package contains stale build output"


@requires_quarto
def test_successful_build_removes_the_staging_directory(tmp_path: Path):
    """
    Verify a successful build removes its staging directory

    Publishing moves the generated package out of its private staging
    directory. The surrounding staging directory must also be removed.
    """
    build_site(tmp_path, "gdtest_docstring_references")

    assert list(tmp_path.glob(".building-*")) == []


def test_failed_build_removes_the_staging_directory(tmp_path: Path):
    """
    Verify a pre-render failure removes the staging directory

    An unknown package name fails before Quarto runs. The staging directory
    must not remain as incomplete build output.
    """
    with pytest.raises(ValueError):
        build_site(tmp_path, "gdtest_does_not_exist")

    assert list(tmp_path.glob(".building-*")) == []


def test_render_failure_includes_quarto_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """
    Verify a failed Quarto process includes its diagnostics

    Include the package name, exit code, and Quarto stderr so the failure
    identifies both the affected fixture and the render error.
    """
    marker = "Quarto failed while reading a citation page"

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            args=["quarto", "render"], returncode=1, stdout="", stderr=marker
        )

    monkeypatch.setattr("tests.gauntlet_sites.subprocess.run", fake_run)

    with pytest.raises(subprocess.SubprocessError, match=marker):
        build_site(tmp_path, "gdtest_docstring_references")


def test_failed_render_removes_staging_sys_path_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """
    Verify a failed render removes staging entries from `sys.path`

    The generated package is importable from staging before publication. A
    render failure deletes that directory, so its import paths must also be
    removed.
    """

    def fake_run(*args: object, **kwargs: object) -> None:
        raise subprocess.CalledProcessError(1, ["quarto", "render"])

    monkeypatch.setattr("tests.gauntlet_sites.subprocess.run", fake_run)

    with pytest.raises(subprocess.CalledProcessError):
        build_site(tmp_path, "gdtest_docstring_references")

    assert not any(".building" in entry for entry in sys.path)


def test_configure_hook_builds_the_citation_allowlist(monkeypatch: pytest.MonkeyPatch):
    """
    Verify the collection hook prepares only the citation sites

    The rendered-output tests determine their parameters while test modules are
    imported, so these sites must exist before collection.
    """
    import tests.conftest as conftest
    import tests.gauntlet_sites as gauntlet_sites

    calls: list[tuple[Path, tuple[str, ...]]] = []
    monkeypatch.setattr(gauntlet_sites, "quarto_available", lambda: True)
    monkeypatch.setattr(
        gauntlet_sites,
        "ensure_sites",
        lambda rendered_dir, names: calls.append((rendered_dir, tuple(names))),
    )

    conftest.pytest_configure(None)

    assert calls == [(conftest.RENDERED_DIR, CITATION_SITES)]


def test_configure_hook_skips_build_without_quarto(monkeypatch: pytest.MonkeyPatch):
    """Verify the collection hook does not build without Quarto"""
    import tests.conftest as conftest
    import tests.gauntlet_sites as gauntlet_sites

    monkeypatch.setattr(gauntlet_sites, "quarto_available", lambda: False)
    monkeypatch.setattr(
        gauntlet_sites,
        "ensure_sites",
        lambda rendered_dir, names: pytest.fail("builder ran without Quarto"),
    )

    conftest.pytest_configure(None)


def test_configure_hook_warns_when_site_preparation_fails(monkeypatch: pytest.MonkeyPatch):
    """
    Verify an environmental build failure warns without aborting collection

    Rendered sites are optional fixtures. An environmental failure such as a
    filesystem error must leave them unavailable without stopping other tests.
    """
    import tests.conftest as conftest
    import tests.gauntlet_sites as gauntlet_sites

    def fake_ensure_sites(rendered_dir: Path, names: tuple[str, ...]) -> None:
        raise OSError("permission denied")

    monkeypatch.setattr(gauntlet_sites, "quarto_available", lambda: True)
    monkeypatch.setattr(gauntlet_sites, "ensure_sites", fake_ensure_sites)

    with pytest.warns(UserWarning, match="permission denied"):
        conftest.pytest_configure(None)


def test_member_check_meta_test_skips_when_its_packages_are_absent(
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Verify the member-heading coverage check skips without its fixtures

    A partial build can contain only citation sites. Skip this coverage check
    when none of the packages that exercise member headings is available.
    """
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parent))
    import test_gdg_rendered as rendered

    monkeypatch.setattr(rendered, "_has_rendered_site", lambda name: False)

    with pytest.raises(pytest.skip.Exception):
        rendered.test_reference_page_heading_levels_exercises_member_check()
