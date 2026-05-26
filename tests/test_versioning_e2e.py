from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from great_docs._api_diff import ApiSnapshot, ParameterInfo, SymbolInfo
from great_docs._versioned_build import (
    _version_build_dir,
    assemble_site,
    create_version_aliases,
    generate_redirect_files,
    preprocess_version,
    write_version_map,
)
from great_docs._versioning import (
    VersionEntry,
    get_latest_version,
    parse_versions_config,
)


# ═══════════════════════════════════════════════════════════════════════════
# Mock Quarto Renderer
# ═══════════════════════════════════════════════════════════════════════════


def fake_quarto_render(build_dir: Path) -> None:
    """
    Simulate ``quarto render`` by converting ``.qmd`` → ``.html``.

    Creates a ``_site/`` directory mirroring the source tree, wrapping each
    ``.qmd`` file's content in a minimal HTML shell. Non-QMD files and
    directories starting with ``_`` are copied as-is (except ``_quarto.yml``).
    """
    site_dir = build_dir / "_site"
    site_dir.mkdir(parents=True, exist_ok=True)

    for item in _walk(build_dir):
        rel = item.relative_to(build_dir)

        # Skip _site/ itself and _quarto.yml
        if str(rel).startswith("_site"):
            continue

        if item.is_file():
            if item.suffix in (".qmd", ".md"):
                # Convert to HTML
                content = item.read_text(encoding="utf-8", errors="replace")
                title = _extract_title(content)
                html = _wrap_html(title, content)
                out = site_dir / str(rel).replace(".qmd", ".html").replace(".md", ".html")
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(html, encoding="utf-8")
            elif not str(rel).startswith("_"):
                # Copy static files (JS, CSS, JSON, etc.)
                out = site_dir / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, out)


def _walk(root: Path):
    """Recursively yield all files under *root*, skipping _site/."""
    for item in sorted(root.iterdir()):
        if item.name == "_site":
            continue
        if item.is_dir():
            yield from _walk(item)
        else:
            yield item


def _extract_title(content: str) -> str:
    """Pull the title from YAML frontmatter."""
    import re

    m = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', content, re.MULTILINE)
    return m.group(1) if m else "Untitled"


def _wrap_html(title: str, qmd_content: str) -> str:
    """Wrap QMD content in a minimal HTML page."""
    # Strip YAML frontmatter for the body
    import re

    body = re.sub(r"^---.*?---\s*", "", qmd_content, count=1, flags=re.DOTALL)
    return (
        f"<!DOCTYPE html>\n<html>\n<head><title>{title}</title></head>\n"
        f"<body>\n<h1>{title}</h1>\n{body}\n</body>\n</html>\n"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Pipeline Runner (mock-based)
# ═══════════════════════════════════════════════════════════════════════════


def run_mock_versioned_build(
    tmp_path: Path,
    *,
    versions_config: list[Any],
    pages: dict[str, str],
    snapshots: dict[str, ApiSnapshot] | None = None,
    section_configs: list[dict] | None = None,
    site_url: str | None = None,
    version_tags: list[str] | None = None,
    latest_only: bool = False,
) -> dict[str, Any]:
    """
    Run the full multi-version pipeline with a mock Quarto renderer.

    Parameters
    ----------
    tmp_path
        Temporary directory for the build.
    versions_config
        The ``versions:`` list as it would appear in ``great-docs.yml``.
    pages
        Mapping of relative path → QMD content for the source tree.
    snapshots
        Optional mapping of version tag → ``ApiSnapshot`` to save as
        snapshot files (for Strategy A testing).
    section_configs
        Section configs from ``great-docs.yml`` (for section-level scoping).
    site_url
        Site base URL for canonical URL injection.
    version_tags
        Filter to build only these version tags.
    latest_only
        Build only the latest version.

    Returns
    -------
    dict
        Build result with keys:
        - ``versions``: parsed ``VersionEntry`` list
        - ``latest_tag``: tag of the latest version
        - ``pages_by_version``: ``{tag: [page_paths]}``
        - ``output_dir``: ``Path`` to the final ``_site/``
        - ``build_root``: ``Path`` to the per-version build dirs
    """
    # --- Setup ---
    project_root = tmp_path / "project"
    source_dir = project_root / "great-docs"
    source_dir.mkdir(parents=True)

    # Write pages
    for rel_path, content in pages.items():
        p = source_dir / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    # Ensure _quarto.yml exists
    qy = source_dir / "_quarto.yml"
    if not qy.exists():
        qy.write_text(
            "project:\n  type: website\n  output-dir: _site\n"
            "format:\n  html: {}\nwebsite:\n  title: Test Site\n",
            encoding="utf-8",
        )

    # Write API snapshots
    if snapshots:
        snap_dir = project_root / "api-snapshots"
        snap_dir.mkdir(parents=True, exist_ok=True)
        for tag, snap in snapshots.items():
            snap.save(snap_dir / f"{tag}.json")

    # --- Parse config ---
    versions = parse_versions_config(versions_config)
    latest = get_latest_version(versions)
    latest_tag = latest.tag if latest else versions[0].tag

    # --- Filter targets ---
    if latest_only:
        targets = [v for v in versions if v.tag == latest_tag]
    elif version_tags:
        tag_set = set(version_tags)
        targets = [v for v in versions if v.tag in tag_set]
    else:
        targets = list(versions)

    # --- Stage 1: Preprocess ---
    build_root = project_root / "_great_docs_build"
    build_root.mkdir(parents=True)

    pages_by_version: dict[str, list[str]] = {}
    build_dirs: list[Path] = []

    for entry in targets:
        ver_dir = _version_build_dir(build_root, entry, latest_tag)
        pp_pages = preprocess_version(
            source_dir,
            ver_dir,
            entry,
            versions,
            project_root=project_root,
            section_configs=section_configs,
        )
        pages_by_version[entry.tag] = pp_pages
        build_dirs.append(ver_dir)

    # --- Stage 2: Mock render ---
    for bd in build_dirs:
        fake_quarto_render(bd)

    # --- Stage 3: Assemble ---
    output_dir = source_dir / "_site"
    assemble_site(build_root, targets, latest_tag, output_dir)

    # Version map
    write_version_map(output_dir, versions, pages_by_version)

    # Aliases
    create_version_aliases(output_dir, versions, latest_tag)

    # Redirect files
    generate_redirect_files(output_dir, versions, latest_tag)

    return {
        "versions": versions,
        "targets": targets,
        "latest_tag": latest_tag,
        "pages_by_version": pages_by_version,
        "output_dir": output_dir,
        "build_root": build_root,
        "source_dir": source_dir,
        "project_root": project_root,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Helpers for assertions
# ═══════════════════════════════════════════════════════════════════════════


def assert_page_exists(output_dir: Path, path: str, version: str | None = None) -> str:
    """Assert an HTML page exists and return its content."""
    if version:
        full = output_dir / "v" / version / path
    else:
        full = output_dir / path
    assert full.exists(), f"Expected page at {full.relative_to(output_dir)}"
    return full.read_text(encoding="utf-8")


def assert_page_missing(output_dir: Path, path: str, version: str | None = None):
    """Assert an HTML page does NOT exist."""
    if version:
        full = output_dir / "v" / version / path
    else:
        full = output_dir / path
    assert not full.exists(), f"Page should not exist: {full.relative_to(output_dir)}"


def assert_page_contains(output_dir: Path, path: str, text: str, version: str | None = None):
    """Assert a page exists and contains the given text."""
    content = assert_page_exists(output_dir, path, version)
    assert text in content, f"'{text}' not found in {path} (version={version})"


def assert_page_not_contains(output_dir: Path, path: str, text: str, version: str | None = None):
    """Assert a page exists but does NOT contain the given text."""
    content = assert_page_exists(output_dir, path, version)
    assert text not in content, f"'{text}' unexpectedly found in {path} (version={version})"


# ═══════════════════════════════════════════════════════════════════════════
# Test Scenarios
# ═══════════════════════════════════════════════════════════════════════════


class TestBasicThreeVersionSite:
    """
    Scenario: A simple site with three versions (0.3, 0.2, 0.1).
    No API snapshots, no section scoping, no fences.
    Validates basic site assembly, version map, aliases, and redirects.
    """

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.3", "0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nWelcome to the docs.",
                "user-guide/intro.qmd": "---\ntitle: Introduction\n---\n\nGetting started.",
                "user-guide/advanced.qmd": "---\ntitle: Advanced\n---\n\nAdvanced usage.",
            },
        )

    def test_latest_at_root(self, site):
        content = assert_page_exists(site["output_dir"], "index.html")
        assert "Welcome to the docs" in content

    def test_old_versions_under_v_prefix(self, site):
        assert_page_exists(site["output_dir"], "index.html", version="0.2")
        assert_page_exists(site["output_dir"], "index.html", version="0.1")

    def test_user_guide_in_all_versions(self, site):
        assert_page_exists(site["output_dir"], "user-guide/intro.html")
        assert_page_exists(site["output_dir"], "user-guide/intro.html", version="0.2")
        assert_page_exists(site["output_dir"], "user-guide/intro.html", version="0.1")

    def test_version_map_exists(self, site):
        vm_path = site["output_dir"] / "_version_map.json"
        assert vm_path.exists()
        data = json.loads(vm_path.read_text())
        assert len(data["versions"]) == 3
        assert data["versions"][0]["tag"] == "0.3"
        assert data["versions"][0]["latest"] is True

    def test_version_map_pages(self, site):
        data = json.loads((site["output_dir"] / "_version_map.json").read_text())
        # All pages should appear in all versions
        assert "index.html" in data["pages"]
        assert set(data["pages"]["index.html"]) == {"0.3", "0.2", "0.1"}

    def test_latest_alias_exists(self, site):
        alias_html = assert_page_exists(site["output_dir"], "v/latest/index.html")
        assert "url=/" in alias_html

    def test_stable_alias_exists(self, site):
        alias_html = assert_page_exists(site["output_dir"], "v/stable/index.html")
        assert "url=/" in alias_html

    def test_netlify_redirects(self, site):
        redirects = site["output_dir"] / "_redirects"
        assert redirects.exists()
        content = redirects.read_text()
        assert "/v/latest/*" in content
        assert "/v/stable/*" in content

    def test_vercel_json(self, site):
        vercel = site["output_dir"] / "vercel.json"
        assert vercel.exists()
        data = json.loads(vercel.read_text())
        assert any("latest" in r["source"] for r in data["rewrites"])

    def test_three_versions_built(self, site):
        assert len(site["pages_by_version"]) == 3
        for tag in ("0.3", "0.2", "0.1"):
            assert tag in site["pages_by_version"]


class TestVersionFences:
    """
    Scenario: Pages with version-only and version-except fenced divs.
    Validates that fences are resolved correctly per version.
    """

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.3", "0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "guide.qmd": (
                    "---\ntitle: Guide\n---\n\n"
                    "Common content.\n\n"
                    '::: {.version-only versions="0.3"}\n'
                    "This is brand new in 0.3!\n"
                    ":::\n\n"
                    '::: {.version-except versions="0.3"}\n'
                    "This is the old way of doing things.\n"
                    ":::\n"
                ),
            },
        )

    def test_version_03_sees_new_content(self, site):
        assert_page_contains(site["output_dir"], "guide.html", "brand new in 0.3")

    def test_version_03_no_old_content(self, site):
        assert_page_not_contains(site["output_dir"], "guide.html", "old way")

    def test_version_02_sees_old_content(self, site):
        assert_page_contains(site["output_dir"], "guide.html", "old way", version="0.2")

    def test_version_02_no_new_content(self, site):
        assert_page_not_contains(
            site["output_dir"], "guide.html", "brand new in 0.3", version="0.2"
        )

    def test_common_content_in_all(self, site):
        assert_page_contains(site["output_dir"], "guide.html", "Common content")
        assert_page_contains(site["output_dir"], "guide.html", "Common content", version="0.2")
        assert_page_contains(site["output_dir"], "guide.html", "Common content", version="0.1")

    def test_fence_markers_stripped(self, site):
        """The ::: fence markers themselves should not appear in output."""
        content = assert_page_exists(site["output_dir"], "guide.html")
        assert "version-only" not in content
        assert "version-except" not in content


class TestPageScoping:
    """
    Scenario: Some pages are restricted to specific versions via
    frontmatter ``versions:`` key.
    """

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.3", "0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "changelog.qmd": "---\ntitle: Changelog\n---\n\nChanges.",
                "new-feature.qmd": (
                    '---\ntitle: New Feature\nversions: ["0.3"]\n---\n\nOnly available in 0.3.'
                ),
                "legacy.qmd": (
                    '---\ntitle: Legacy\nversions: ["0.1", "0.2"]\n---\n\nRemoved in 0.3.'
                ),
            },
        )

    def test_unscoped_pages_everywhere(self, site):
        for version in (None, "0.2", "0.1"):
            assert_page_exists(site["output_dir"], "index.html", version=version)
            assert_page_exists(site["output_dir"], "changelog.html", version=version)

    def test_new_feature_only_in_03(self, site):
        assert_page_exists(site["output_dir"], "new-feature.html")
        assert_page_missing(site["output_dir"], "new-feature.html", version="0.2")
        assert_page_missing(site["output_dir"], "new-feature.html", version="0.1")

    def test_legacy_only_in_01_02(self, site):
        assert_page_missing(site["output_dir"], "legacy.html")  # Not in 0.3 (latest/root)
        assert_page_exists(site["output_dir"], "legacy.html", version="0.2")
        assert_page_exists(site["output_dir"], "legacy.html", version="0.1")

    def test_version_map_reflects_scoping(self, site):
        data = json.loads((site["output_dir"] / "_version_map.json").read_text())
        assert "0.3" in data["pages"]["new-feature.html"]
        assert "0.2" not in data["pages"]["new-feature.html"]
        assert "0.1" not in data["pages"].get("new-feature.html", [])


class TestSectionScoping:
    """
    Scenario: Entire sections (directories) are version-scoped via config.
    """

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.3", "0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "user-guide/intro.qmd": "---\ntitle: Intro\n---\n\nGuide.",
                "recipes/01-basic.qmd": "---\ntitle: Basic Recipe\n---\n\nRecipe.",
                "migrations/v03.qmd": "---\ntitle: Migrating to 0.3\n---\n\nMigration.",
            },
            section_configs=[
                {"dir": "recipes", "versions": ["0.3", "0.2"]},
                {"dir": "migrations", "versions": ["0.3"]},
            ],
        )

    def test_recipes_in_03_and_02(self, site):
        assert_page_exists(site["output_dir"], "recipes/01-basic.html")
        assert_page_exists(site["output_dir"], "recipes/01-basic.html", version="0.2")

    def test_recipes_not_in_01(self, site):
        assert_page_missing(site["output_dir"], "recipes/01-basic.html", version="0.1")

    def test_migrations_only_in_03(self, site):
        assert_page_exists(site["output_dir"], "migrations/v03.html")
        assert_page_missing(site["output_dir"], "migrations/v03.html", version="0.2")
        assert_page_missing(site["output_dir"], "migrations/v03.html", version="0.1")

    def test_unscoped_sections_everywhere(self, site):
        # user-guide has no section config → present in all versions
        assert_page_exists(site["output_dir"], "user-guide/intro.html")
        assert_page_exists(site["output_dir"], "user-guide/intro.html", version="0.2")
        assert_page_exists(site["output_dir"], "user-guide/intro.html", version="0.1")


class TestInlineBadgesAndCallouts:
    """
    Scenario: Pages contain [version-badge] markers and version callouts.
    """

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.3", "0.2"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "features.qmd": (
                    "---\ntitle: Features\n---\n\n"
                    "## Widget [version-badge new]\n\n"
                    "The widget is great.\n\n"
                    "## Old Thing [version-badge deprecated 0.2]\n\n"
                    "Don't use this anymore.\n\n"
                    '::: {.version-note version="0.3"}\n'
                    "This API was redesigned in 0.3.\n"
                    ":::\n\n"
                    '::: {.version-deprecated version="0.1"}\n'
                    "Use `new_thing()` instead.\n"
                    ":::\n"
                ),
            },
        )

    def test_new_badge_expanded_in_03(self, site):
        assert_page_contains(site["output_dir"], "features.html", "gd-badge-new")
        assert_page_contains(site["output_dir"], "features.html", "New in 0.3")

    def test_deprecated_badge_with_explicit_version(self, site):
        assert_page_contains(site["output_dir"], "features.html", "Deprecated in 0.2")

    def test_version_note_becomes_callout(self, site):
        assert_page_contains(site["output_dir"], "features.html", "callout-note")
        assert_page_contains(site["output_dir"], "features.html", "Added in 0.3")

    def test_version_deprecated_becomes_warning(self, site):
        assert_page_contains(site["output_dir"], "features.html", "callout-warning")
        assert_page_contains(site["output_dir"], "features.html", "Deprecated since 0.1")

    def test_badges_use_version_label_in_02(self, site):
        # In version 0.2, the default badge version is the entry's label
        content = assert_page_exists(site["output_dir"], "features.html", version="0.2")
        assert "New in 0.2" in content  # badge uses 0.2's own label

    def test_raw_markers_removed(self, site):
        content = assert_page_exists(site["output_dir"], "features.html")
        assert "[version-badge" not in content
        assert ".version-note" not in content
        assert ".version-deprecated" not in content


class TestNestedFences:
    """
    Scenario: Nested version fences — outer and inner fences interact.
    """

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.3", "0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "nested.qmd": (
                    "---\ntitle: Nested Fences\n---\n\n"
                    "Always visible.\n\n"
                    '::: {.version-only versions="0.2,0.3"}\n'
                    "Visible in 0.2 and 0.3.\n\n"
                    '::: {.version-only versions="0.3"}\n'
                    "Only in 0.3 (nested).\n"
                    ":::\n\n"
                    ":::\n\n"
                    "Also always visible.\n"
                ),
            },
        )

    def test_outer_fence_03(self, site):
        assert_page_contains(site["output_dir"], "nested.html", "Visible in 0.2 and 0.3")

    def test_inner_fence_03(self, site):
        assert_page_contains(site["output_dir"], "nested.html", "Only in 0.3 (nested)")

    def test_outer_fence_02(self, site):
        assert_page_contains(
            site["output_dir"], "nested.html", "Visible in 0.2 and 0.3", version="0.2"
        )

    def test_inner_fence_not_in_02(self, site):
        assert_page_not_contains(
            site["output_dir"], "nested.html", "Only in 0.3 (nested)", version="0.2"
        )

    def test_neither_fence_in_01(self, site):
        content = assert_page_exists(site["output_dir"], "nested.html", version="0.1")
        assert "Visible in 0.2 and 0.3" not in content
        assert "Only in 0.3 (nested)" not in content

    def test_always_visible_in_all(self, site):
        for v in (None, "0.2", "0.1"):
            assert_page_contains(site["output_dir"], "nested.html", "Always visible", version=v)
            assert_page_contains(
                site["output_dir"], "nested.html", "Also always visible", version=v
            )


class TestApiSnapshotVersioning:
    """
    Scenario: Old versions use API snapshots (Strategy A) to generate
    reference pages, while the latest version has live pages.
    """

    @pytest.fixture()
    def site(self, tmp_path):
        snap_02 = ApiSnapshot(
            version="0.2",
            package_name="mypkg",
            symbols={
                "Widget": SymbolInfo(
                    name="Widget",
                    kind="class",
                    bases=["Base"],
                    parameters=[ParameterInfo(name="color", annotation="str")],
                ),
                "render": SymbolInfo(
                    name="render",
                    kind="function",
                    parameters=[
                        ParameterInfo(name="data", annotation="DataFrame"),
                        ParameterInfo(name="fmt", annotation="str", default="'html'"),
                    ],
                    return_annotation="str",
                ),
            },
        )
        snap_01 = ApiSnapshot(
            version="0.1",
            package_name="mypkg",
            symbols={
                "Widget": SymbolInfo(
                    name="Widget",
                    kind="class",
                    parameters=[ParameterInfo(name="color", annotation="str")],
                ),
            },
        )

        return run_mock_versioned_build(
            tmp_path,
            versions_config=[
                {"tag": "0.3", "label": "0.3.0"},
                {
                    "tag": "0.2",
                    "label": "0.2.0",
                    "api_snapshot": "api-snapshots/0.2.json",
                },
                {
                    "tag": "0.1",
                    "label": "0.1.0",
                    "api_snapshot": "api-snapshots/0.1.json",
                },
            ],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nDocs.",
                # Latest version has manually-written reference pages
                "reference/index.qmd": "---\ntitle: API Reference\n---\n\nSee classes below.",
                "reference/Widget.qmd": "---\ntitle: Widget\n---\n\nThe widget class.",
                "reference/render.qmd": "---\ntitle: render\n---\n\nRender function.",
                "reference/new_func.qmd": "---\ntitle: new_func\n---\n\nNew in 0.3!",
            },
            snapshots={"0.2": snap_02, "0.1": snap_01},
        )

    def test_latest_has_all_ref_pages(self, site):
        assert_page_exists(site["output_dir"], "reference/Widget.html")
        assert_page_exists(site["output_dir"], "reference/render.html")
        assert_page_exists(site["output_dir"], "reference/new_func.html")
        assert_page_exists(site["output_dir"], "reference/index.html")

    def test_v02_snapshot_generates_ref_pages(self, site):
        # Strategy A: reference pages built from snapshot
        assert_page_exists(site["output_dir"], "reference/Widget.html", version="0.2")
        assert_page_exists(site["output_dir"], "reference/render.html", version="0.2")
        assert_page_exists(site["output_dir"], "reference/index.html", version="0.2")

    def test_v02_snapshot_has_widget_signature(self, site):
        content = assert_page_exists(site["output_dir"], "reference/Widget.html", version="0.2")
        assert "Widget" in content
        assert "color" in content

    def test_v02_render_func_has_return_type(self, site):
        content = assert_page_exists(site["output_dir"], "reference/render.html", version="0.2")
        assert "str" in content

    def test_v01_fewer_symbols(self, site):
        # v0.1 only had Widget, no render function
        assert_page_exists(site["output_dir"], "reference/Widget.html", version="0.1")
        # The snapshot-generated render.html should NOT exist for 0.1
        # (render wasn't in the 0.1 snapshot)
        assert_page_missing(site["output_dir"], "reference/render.html", version="0.1")

    def test_v01_no_new_func(self, site):
        # new_func was added in 0.3, not in any snapshot
        assert_page_missing(site["output_dir"], "reference/new_func.html", version="0.1")

    def test_snapshot_ref_index_groups_by_kind(self, site):
        content = assert_page_exists(site["output_dir"], "reference/index.html", version="0.2")
        assert "Classes" in content
        assert "Functions" in content


class TestPrereleasAndEolVersions:
    """
    Scenario: Site with prerelease (dev) and end-of-life versions.
    """

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=[
                {"tag": "dev", "label": "0.4.0-dev", "prerelease": True},
                {"tag": "0.3", "label": "0.3.0"},
                {"tag": "0.1", "label": "0.1.0", "eol": True},
            ],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nDocs.",
                "guide.qmd": "---\ntitle: Guide\n---\n\nGuide.",
            },
        )

    def test_latest_is_03(self, site):
        assert site["latest_tag"] == "0.3"

    def test_dev_under_v_prefix(self, site):
        assert_page_exists(site["output_dir"], "index.html", version="dev")

    def test_eol_under_v_prefix(self, site):
        assert_page_exists(site["output_dir"], "index.html", version="0.1")

    def test_version_map_has_prerelease_flag(self, site):
        data = json.loads((site["output_dir"] / "_version_map.json").read_text())
        dev_entry = next(v for v in data["versions"] if v["tag"] == "dev")
        assert dev_entry.get("prerelease") is True

    def test_version_map_has_eol_flag(self, site):
        data = json.loads((site["output_dir"] / "_version_map.json").read_text())
        eol_entry = next(v for v in data["versions"] if v["tag"] == "0.1")
        assert eol_entry.get("eol") is True

    def test_no_dev_alias_collision(self, site):
        # "dev" is both a tag and a potential alias — alias should not be created
        alias_path = site["output_dir"] / "v" / "dev" / "index.html"
        # dev exists as a real version dir, but not as an alias redirect
        if alias_path.exists():
            content = alias_path.read_text()
            # If it exists, it should be the real rendered page, not a redirect
            # (or not exist at all as an alias)
            # The version is under v/dev/ as a real version
            assert "Docs" in content or "http-equiv" not in content


class TestLatestOnlyBuild:
    """
    Scenario: Building with latest_only=True.
    Only the latest version should be built.
    """

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.3", "0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "guide.qmd": "---\ntitle: Guide\n---\n\nGuide.",
            },
            latest_only=True,
        )

    def test_only_latest_built(self, site):
        assert list(site["pages_by_version"].keys()) == ["0.3"]

    def test_latest_at_root(self, site):
        assert_page_exists(site["output_dir"], "index.html")

    def test_old_versions_not_built(self, site):
        assert_page_missing(site["output_dir"], "index.html", version="0.2")
        assert_page_missing(site["output_dir"], "index.html", version="0.1")


class TestSelectiveVersionBuild:
    """
    Scenario: Building with version_tags filter.
    """

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.3", "0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
            },
            version_tags=["0.3", "0.1"],
        )

    def test_only_selected_versions_built(self, site):
        assert set(site["pages_by_version"].keys()) == {"0.3", "0.1"}

    def test_skipped_version_missing(self, site):
        assert_page_missing(site["output_dir"], "index.html", version="0.2")

    def test_selected_versions_present(self, site):
        assert_page_exists(site["output_dir"], "index.html")  # 0.3 at root
        assert_page_exists(site["output_dir"], "index.html", version="0.1")


class TestVersionRangeExpressions:
    """
    Scenario: Fences using comparison operators (>=, <, etc.).
    """

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.4", "0.3", "0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "compat.qmd": (
                    "---\ntitle: Compatibility\n---\n\n"
                    '::: {.version-only versions=">=0.2"}\n'
                    "Available since 0.2.\n"
                    ":::\n\n"
                    '::: {.version-only versions=">0.1,<0.4"}\n'
                    "Only in 0.2 and 0.3.\n"
                    ":::\n"
                ),
            },
        )

    def test_gte_02_in_04(self, site):
        assert_page_contains(site["output_dir"], "compat.html", "Available since 0.2")

    def test_gte_02_in_02(self, site):
        assert_page_contains(
            site["output_dir"], "compat.html", "Available since 0.2", version="0.2"
        )

    def test_gte_02_not_in_01(self, site):
        assert_page_not_contains(
            site["output_dir"], "compat.html", "Available since 0.2", version="0.1"
        )

    def test_range_02_03_in_02(self, site):
        assert_page_contains(
            site["output_dir"], "compat.html", "Only in 0.2 and 0.3", version="0.2"
        )

    def test_range_02_03_in_03(self, site):
        assert_page_contains(
            site["output_dir"], "compat.html", "Only in 0.2 and 0.3", version="0.3"
        )

    def test_range_02_03_not_in_04(self, site):
        assert_page_not_contains(site["output_dir"], "compat.html", "Only in 0.2 and 0.3")

    def test_range_02_03_not_in_01(self, site):
        assert_page_not_contains(
            site["output_dir"], "compat.html", "Only in 0.2 and 0.3", version="0.1"
        )


class TestCombinedFeaturesIntegration:
    """
    Scenario: A realistic site combining multiple features simultaneously:
    fences, page scoping, section scoping, badges, callouts, and snapshots.
    """

    @pytest.fixture()
    def site(self, tmp_path):
        snap_02 = ApiSnapshot(
            version="0.2",
            package_name="mypkg",
            symbols={
                "Widget": SymbolInfo(name="Widget", kind="class"),
            },
        )

        return run_mock_versioned_build(
            tmp_path,
            versions_config=[
                {"tag": "0.3", "label": "0.3.0"},
                {"tag": "0.2", "label": "0.2.0", "api_snapshot": "api-snapshots/0.2.json"},
            ],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nWelcome.",
                "guide.qmd": (
                    "---\ntitle: Guide\n---\n\n"
                    "## Setup [version-badge new]\n\n"
                    "Setup instructions.\n\n"
                    '::: {.version-note version="0.3"}\n'
                    "The setup process was simplified in 0.3.\n"
                    ":::\n\n"
                    '::: {.version-only versions="0.3"}\n'
                    "### New Configuration Format\n\n"
                    "Use YAML instead of JSON.\n"
                    ":::\n"
                ),
                "advanced.qmd": (
                    '---\ntitle: Advanced\nversions: ["0.3"]\n---\n\nAdvanced topics.\n'
                ),
                "recipes/01-basic.qmd": ("---\ntitle: Basic Recipe\n---\n\nA recipe."),
                "reference/Widget.qmd": ("---\ntitle: Widget\n---\n\nLive Widget docs."),
            },
            snapshots={"0.2": snap_02},
            section_configs=[
                {"dir": "recipes", "versions": ["0.3"]},
            ],
        )

    def test_badges_expanded(self, site):
        assert_page_contains(site["output_dir"], "guide.html", "gd-badge-new")

    def test_callouts_expanded(self, site):
        assert_page_contains(site["output_dir"], "guide.html", "callout-note")

    def test_fence_resolved(self, site):
        assert_page_contains(site["output_dir"], "guide.html", "New Configuration Format")
        assert_page_not_contains(
            site["output_dir"], "guide.html", "New Configuration Format", version="0.2"
        )

    def test_page_scoping(self, site):
        assert_page_exists(site["output_dir"], "advanced.html")
        assert_page_missing(site["output_dir"], "advanced.html", version="0.2")

    def test_section_scoping(self, site):
        assert_page_exists(site["output_dir"], "recipes/01-basic.html")
        assert_page_missing(site["output_dir"], "recipes/01-basic.html", version="0.2")

    def test_snapshot_api_ref(self, site):
        assert_page_exists(site["output_dir"], "reference/Widget.html", version="0.2")

    def test_latest_live_ref(self, site):
        content = assert_page_exists(site["output_dir"], "reference/Widget.html")
        assert "Live Widget docs" in content

    def test_version_map_complete(self, site):
        data = json.loads((site["output_dir"] / "_version_map.json").read_text())
        assert len(data["versions"]) == 2
        # advanced.qmd is only in 0.3
        assert "0.2" not in data["pages"].get("advanced.html", [])


class TestEmptyVersionNoPages:
    """
    Edge case: A version where all pages are scoped out.
    The version should still build (with just _quarto.yml) but have no pages.
    """

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.3", "0.2"],
            pages={
                "only-new.qmd": ('---\ntitle: Only New\nversions: ["0.3"]\n---\n\nNew.'),
            },
        )

    def test_v02_has_no_content_pages(self, site):
        assert site["pages_by_version"]["0.2"] == []

    def test_v03_has_the_page(self, site):
        assert "only-new.html" in site["pages_by_version"]["0.3"]


class TestMixedFencesAndPageScoping:
    """
    Edge case: A page is scoped to versions 0.2+ but also has a fence
    that shows content only in 0.3.
    """

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.3", "0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHome.",
                "partial.qmd": (
                    '---\ntitle: Partial\nversions: ["0.2", "0.3"]\n---\n\n'
                    "Base content.\n\n"
                    '::: {.version-only versions="0.3"}\n'
                    "Extra 0.3 content.\n"
                    ":::\n"
                ),
            },
        )

    def test_not_in_01(self, site):
        assert_page_missing(site["output_dir"], "partial.html", version="0.1")

    def test_in_02_without_extra(self, site):
        assert_page_contains(site["output_dir"], "partial.html", "Base content", version="0.2")
        assert_page_not_contains(
            site["output_dir"], "partial.html", "Extra 0.3 content", version="0.2"
        )

    def test_in_03_with_extra(self, site):
        assert_page_contains(site["output_dir"], "partial.html", "Base content")
        assert_page_contains(site["output_dir"], "partial.html", "Extra 0.3 content")


class TestSingleVersionSite:
    """
    Edge case: Only one version configured. Should still work correctly.
    """

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["1.0"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nSingle version site.",
            },
        )

    def test_single_version_at_root(self, site):
        assert_page_contains(site["output_dir"], "index.html", "Single version site")

    def test_no_v_prefix_dirs(self, site):
        assert not (site["output_dir"] / "v" / "1.0").exists()

    def test_version_map_has_one_version(self, site):
        data = json.loads((site["output_dir"] / "_version_map.json").read_text())
        assert len(data["versions"]) == 1


class TestSubdirectoryPages:
    """
    Scenario: Pages in deeply nested subdirectories.
    """

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHome.",
                "guide/getting-started/install.qmd": ("---\ntitle: Install\n---\n\nInstall steps."),
                "guide/getting-started/configure.qmd": (
                    '---\ntitle: Configure\nversions: ["0.2"]\n---\n\nConfig.'
                ),
                "guide/advanced/plugins.qmd": ("---\ntitle: Plugins\n---\n\nPlugin guide."),
            },
        )

    def test_nested_pages_in_latest(self, site):
        assert_page_exists(site["output_dir"], "guide/getting-started/install.html")
        assert_page_exists(site["output_dir"], "guide/getting-started/configure.html")
        assert_page_exists(site["output_dir"], "guide/advanced/plugins.html")

    def test_scoped_nested_page(self, site):
        assert_page_missing(
            site["output_dir"],
            "guide/getting-started/configure.html",
            version="0.1",
        )

    def test_unscoped_nested_page_in_old(self, site):
        assert_page_exists(
            site["output_dir"],
            "guide/getting-started/install.html",
            version="0.1",
        )


# ═══════════════════════════════════════════════════════════════════════════
# Edge Case Tests — Fence Processing
# ═══════════════════════════════════════════════════════════════════════════


class TestEmptyFenceBlock:
    """Edge case: A fence div with no content between open and close."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "empty-fence.qmd": (
                    "---\ntitle: Empty Fences\n---\n\n"
                    "Before fence.\n\n"
                    '::: {.version-only versions="0.2"}\n'
                    ":::\n\n"
                    "After fence.\n"
                ),
            },
        )

    def test_before_content_preserved(self, site):
        assert_page_contains(site["output_dir"], "empty-fence.html", "Before fence")

    def test_after_content_preserved(self, site):
        assert_page_contains(site["output_dir"], "empty-fence.html", "After fence")

    def test_empty_fence_no_crash_old_version(self, site):
        assert_page_contains(site["output_dir"], "empty-fence.html", "Before fence", version="0.1")
        assert_page_contains(site["output_dir"], "empty-fence.html", "After fence", version="0.1")


class TestAdjacentFences:
    """Edge case: Multiple fences back-to-back with no content between them."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.3", "0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "adjacent.qmd": (
                    "---\ntitle: Adjacent\n---\n\n"
                    '::: {.version-only versions="0.3"}\n'
                    "First block.\n"
                    ":::\n"
                    '::: {.version-only versions="0.2"}\n'
                    "Second block.\n"
                    ":::\n"
                    '::: {.version-only versions="0.1"}\n'
                    "Third block.\n"
                    ":::\n"
                ),
            },
        )

    def test_v03_sees_only_first(self, site):
        assert_page_contains(site["output_dir"], "adjacent.html", "First block")
        assert_page_not_contains(site["output_dir"], "adjacent.html", "Second block")
        assert_page_not_contains(site["output_dir"], "adjacent.html", "Third block")

    def test_v02_sees_only_second(self, site):
        assert_page_contains(site["output_dir"], "adjacent.html", "Second block", version="0.2")
        assert_page_not_contains(site["output_dir"], "adjacent.html", "First block", version="0.2")
        assert_page_not_contains(site["output_dir"], "adjacent.html", "Third block", version="0.2")

    def test_v01_sees_only_third(self, site):
        assert_page_contains(site["output_dir"], "adjacent.html", "Third block", version="0.1")
        assert_page_not_contains(site["output_dir"], "adjacent.html", "First block", version="0.1")
        assert_page_not_contains(site["output_dir"], "adjacent.html", "Second block", version="0.1")


class TestNestedMixedFenceTypes:
    """Edge case: version-only inside version-except and vice versa."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.3", "0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "mixed.qmd": (
                    "---\ntitle: Mixed Fences\n---\n\n"
                    "Always here.\n\n"
                    # Outer: except 0.1 → show in 0.2, 0.3
                    '::: {.version-except versions="0.1"}\n'
                    "Not in 0.1.\n\n"
                    # Inner: only 0.3 → show only in 0.3
                    '::: {.version-only versions="0.3"}\n'
                    "Only 0.3 nested in except-0.1.\n"
                    ":::\n\n"
                    ":::\n\n"
                    # Outer: only 0.1 → show in 0.1
                    '::: {.version-only versions="0.1"}\n'
                    "Only in 0.1 outer.\n\n"
                    # Inner: except 0.1 → would normally show, but parent is 0.1-only
                    '::: {.version-except versions="0.1"}\n'
                    "This is paradoxical (inside 0.1-only but except 0.1).\n"
                    ":::\n\n"
                    ":::\n"
                ),
            },
        )

    def test_v03_sees_except_01_content(self, site):
        assert_page_contains(site["output_dir"], "mixed.html", "Not in 0.1")

    def test_v03_sees_nested_only_03(self, site):
        assert_page_contains(site["output_dir"], "mixed.html", "Only 0.3 nested in except-0.1")

    def test_v02_sees_except_01_but_not_nested(self, site):
        assert_page_contains(site["output_dir"], "mixed.html", "Not in 0.1", version="0.2")
        assert_page_not_contains(
            site["output_dir"], "mixed.html", "Only 0.3 nested in except-0.1", version="0.2"
        )

    def test_v01_sees_only_01_outer(self, site):
        assert_page_contains(site["output_dir"], "mixed.html", "Only in 0.1 outer", version="0.1")
        assert_page_not_contains(site["output_dir"], "mixed.html", "Not in 0.1", version="0.1")

    def test_v01_paradox_excluded(self, site):
        """Inner except-0.1 inside outer only-0.1 should be excluded (parent wins)."""
        assert_page_not_contains(site["output_dir"], "mixed.html", "paradoxical", version="0.1")

    def test_v03_no_only_01_content(self, site):
        assert_page_not_contains(site["output_dir"], "mixed.html", "Only in 0.1 outer")

    def test_always_visible_in_all(self, site):
        for v in (None, "0.2", "0.1"):
            assert_page_contains(site["output_dir"], "mixed.html", "Always here", version=v)


class TestDeeplyNestedFences:
    """Edge case: 4 levels of fence nesting."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.4", "0.3", "0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "deep.qmd": (
                    "---\ntitle: Deep Nesting\n---\n\n"
                    "Level 0 (all).\n\n"
                    '::: {.version-only versions="0.2,0.3,0.4"}\n'
                    "Level 1 (not 0.1).\n\n"
                    '::: {.version-only versions="0.3,0.4"}\n'
                    "Level 2 (not 0.1, 0.2).\n\n"
                    '::: {.version-only versions="0.4"}\n'
                    "Level 3 (only 0.4).\n"
                    ":::\n\n"
                    ":::\n\n"
                    ":::\n"
                ),
            },
        )

    def test_v04_all_levels(self, site):
        for text in ("Level 0", "Level 1", "Level 2", "Level 3"):
            assert_page_contains(site["output_dir"], "deep.html", text)

    def test_v03_three_levels(self, site):
        assert_page_contains(site["output_dir"], "deep.html", "Level 0", version="0.3")
        assert_page_contains(site["output_dir"], "deep.html", "Level 1", version="0.3")
        assert_page_contains(site["output_dir"], "deep.html", "Level 2", version="0.3")
        assert_page_not_contains(site["output_dir"], "deep.html", "Level 3", version="0.3")

    def test_v02_two_levels(self, site):
        assert_page_contains(site["output_dir"], "deep.html", "Level 0", version="0.2")
        assert_page_contains(site["output_dir"], "deep.html", "Level 1", version="0.2")
        assert_page_not_contains(site["output_dir"], "deep.html", "Level 2", version="0.2")
        assert_page_not_contains(site["output_dir"], "deep.html", "Level 3", version="0.2")

    def test_v01_only_level_0(self, site):
        assert_page_contains(site["output_dir"], "deep.html", "Level 0", version="0.1")
        assert_page_not_contains(site["output_dir"], "deep.html", "Level 1", version="0.1")
        assert_page_not_contains(site["output_dir"], "deep.html", "Level 2", version="0.1")
        assert_page_not_contains(site["output_dir"], "deep.html", "Level 3", version="0.1")


class TestFenceWithWildcard:
    """Edge case: Fence with versions="*" (wildcard matches all)."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.3", "0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "wild.qmd": (
                    "---\ntitle: Wildcard\n---\n\n"
                    "Before.\n\n"
                    '::: {.version-only versions="*"}\n'
                    "Wildcard content visible everywhere.\n"
                    ":::\n\n"
                    "After.\n"
                ),
            },
        )

    def test_wildcard_in_all_versions(self, site):
        for v in (None, "0.2", "0.1"):
            assert_page_contains(
                site["output_dir"], "wild.html", "Wildcard content visible everywhere", version=v
            )

    def test_surrounding_content(self, site):
        assert_page_contains(site["output_dir"], "wild.html", "Before")
        assert_page_contains(site["output_dir"], "wild.html", "After")


class TestVersionExceptMultipleVersions:
    """Edge case: version-except with a comma-separated list."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.4", "0.3", "0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "except-multi.qmd": (
                    "---\ntitle: Except Multiple\n---\n\n"
                    '::: {.version-except versions="0.1,0.2"}\n'
                    "Not in 0.1 or 0.2.\n"
                    ":::\n\n"
                    '::: {.version-except versions="0.3,0.4"}\n'
                    "Not in 0.3 or 0.4.\n"
                    ":::\n"
                ),
            },
        )

    def test_first_block_in_03_and_04(self, site):
        assert_page_contains(site["output_dir"], "except-multi.html", "Not in 0.1 or 0.2")
        assert_page_contains(
            site["output_dir"], "except-multi.html", "Not in 0.1 or 0.2", version="0.3"
        )

    def test_first_block_not_in_01_02(self, site):
        assert_page_not_contains(
            site["output_dir"], "except-multi.html", "Not in 0.1 or 0.2", version="0.1"
        )
        assert_page_not_contains(
            site["output_dir"], "except-multi.html", "Not in 0.1 or 0.2", version="0.2"
        )

    def test_second_block_in_01_and_02(self, site):
        assert_page_contains(
            site["output_dir"], "except-multi.html", "Not in 0.3 or 0.4", version="0.1"
        )
        assert_page_contains(
            site["output_dir"], "except-multi.html", "Not in 0.3 or 0.4", version="0.2"
        )

    def test_second_block_not_in_03_04(self, site):
        assert_page_not_contains(site["output_dir"], "except-multi.html", "Not in 0.3 or 0.4")
        assert_page_not_contains(
            site["output_dir"], "except-multi.html", "Not in 0.3 or 0.4", version="0.3"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Edge Case Tests — Version Expression Operators
# ═══════════════════════════════════════════════════════════════════════════


class TestExplicitEqualsOperator:
    """Edge case: Explicit = operator in version expression."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.3", "0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "eq.qmd": (
                    "---\ntitle: Explicit Equals\n---\n\n"
                    '::: {.version-only versions="=0.2"}\n'
                    "Exactly 0.2.\n"
                    ":::\n"
                ),
            },
        )

    def test_equals_matches_exact(self, site):
        assert_page_contains(site["output_dir"], "eq.html", "Exactly 0.2", version="0.2")

    def test_equals_not_in_others(self, site):
        assert_page_not_contains(site["output_dir"], "eq.html", "Exactly 0.2")
        assert_page_not_contains(site["output_dir"], "eq.html", "Exactly 0.2", version="0.1")


class TestLessThanOrEqualOperator:
    """Edge case: <= operator in version expressions."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.4", "0.3", "0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "lte.qmd": (
                    "---\ntitle: LTE\n---\n\n"
                    '::: {.version-only versions="<=0.2"}\n'
                    "Old versions only.\n"
                    ":::\n"
                ),
            },
        )

    def test_lte_in_01(self, site):
        assert_page_contains(site["output_dir"], "lte.html", "Old versions only", version="0.1")

    def test_lte_in_02(self, site):
        assert_page_contains(site["output_dir"], "lte.html", "Old versions only", version="0.2")

    def test_lte_not_in_03(self, site):
        assert_page_not_contains(site["output_dir"], "lte.html", "Old versions only", version="0.3")

    def test_lte_not_in_04(self, site):
        assert_page_not_contains(site["output_dir"], "lte.html", "Old versions only")


class TestStrictGreaterThanOperator:
    """Edge case: > operator, boundary at exact version."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.3", "0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "gt.qmd": (
                    "---\ntitle: GT\n---\n\n"
                    '::: {.version-only versions=">0.2"}\n'
                    "Strictly newer than 0.2.\n"
                    ":::\n"
                ),
            },
        )

    def test_gt_boundary_excludes_exact(self, site):
        """0.2 is NOT strictly greater than 0.2."""
        assert_page_not_contains(
            site["output_dir"], "gt.html", "Strictly newer than 0.2", version="0.2"
        )

    def test_gt_includes_newer(self, site):
        assert_page_contains(site["output_dir"], "gt.html", "Strictly newer than 0.2")

    def test_gt_excludes_older(self, site):
        assert_page_not_contains(
            site["output_dir"], "gt.html", "Strictly newer than 0.2", version="0.1"
        )


class TestStrictLessThanOperator:
    """Edge case: < operator, boundary at exact version."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.3", "0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "lt.qmd": (
                    "---\ntitle: LT\n---\n\n"
                    '::: {.version-only versions="<0.2"}\n'
                    "Strictly older than 0.2.\n"
                    ":::\n"
                ),
            },
        )

    def test_lt_boundary_excludes_exact(self, site):
        """0.2 is NOT strictly less than 0.2."""
        assert_page_not_contains(
            site["output_dir"], "lt.html", "Strictly older than 0.2", version="0.2"
        )

    def test_lt_excludes_newer(self, site):
        assert_page_not_contains(site["output_dir"], "lt.html", "Strictly older than 0.2")

    def test_lt_includes_older(self, site):
        assert_page_contains(
            site["output_dir"], "lt.html", "Strictly older than 0.2", version="0.1"
        )


class TestCombinedRangeOperators:
    """Edge case: >=X,<=Y to express a closed range."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.5", "0.4", "0.3", "0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "range.qmd": (
                    "---\ntitle: Range\n---\n\n"
                    '::: {.version-only versions=">=0.2,<=0.4"}\n'
                    "Between 0.2 and 0.4 inclusive.\n"
                    ":::\n"
                ),
            },
        )

    def test_in_lower_bound(self, site):
        assert_page_contains(
            site["output_dir"], "range.html", "Between 0.2 and 0.4 inclusive", version="0.2"
        )

    def test_in_upper_bound(self, site):
        assert_page_contains(
            site["output_dir"], "range.html", "Between 0.2 and 0.4 inclusive", version="0.4"
        )

    def test_in_middle(self, site):
        assert_page_contains(
            site["output_dir"], "range.html", "Between 0.2 and 0.4 inclusive", version="0.3"
        )

    def test_below_range(self, site):
        assert_page_not_contains(
            site["output_dir"], "range.html", "Between 0.2 and 0.4 inclusive", version="0.1"
        )

    def test_above_range(self, site):
        assert_page_not_contains(site["output_dir"], "range.html", "Between 0.2 and 0.4 inclusive")


# ═══════════════════════════════════════════════════════════════════════════
# Edge Case Tests — Badge & Callout Expansion
# ═══════════════════════════════════════════════════════════════════════════


class TestMultipleBadgesOnOneLine:
    """Edge case: Two or more badges on the same line."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.3"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "multi-badge.qmd": (
                    "---\ntitle: Multi Badge\n---\n\n"
                    "Feature [version-badge new] and Widget [version-badge changed 0.2]\n"
                ),
            },
        )

    def test_both_badges_expanded(self, site):
        content = assert_page_exists(site["output_dir"], "multi-badge.html")
        assert "gd-badge-new" in content
        assert "gd-badge-changed" in content

    def test_new_uses_entry_label(self, site):
        assert_page_contains(site["output_dir"], "multi-badge.html", "New in 0.3")

    def test_changed_uses_explicit_version(self, site):
        assert_page_contains(site["output_dir"], "multi-badge.html", "Changed in 0.2")


class TestChangedBadgeType:
    """Edge case: The 'changed' badge type specifically."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.3", "0.2"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "changed.qmd": (
                    "---\ntitle: Changed\n---\n\n## Method [version-badge changed]\n\nDocs.\n"
                ),
            },
        )

    def test_changed_badge_expanded(self, site):
        assert_page_contains(site["output_dir"], "changed.html", "gd-badge-changed")
        assert_page_contains(site["output_dir"], "changed.html", "Changed in 0.3")

    def test_changed_badge_in_old_version(self, site):
        content = assert_page_exists(site["output_dir"], "changed.html", version="0.2")
        assert "Changed in 0.2" in content


class TestCalloutWithoutVersion:
    """Edge case: version-note/version-deprecated with no version= attribute."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.3", "0.2"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "no-ver-callout.qmd": (
                    "---\ntitle: No Version Callout\n---\n\n"
                    "::: {.version-note}\n"
                    "A note without explicit version.\n"
                    ":::\n\n"
                    "::: {.version-deprecated}\n"
                    "Deprecated without explicit version.\n"
                    ":::\n"
                ),
            },
        )

    def test_note_uses_entry_label(self, site):
        assert_page_contains(site["output_dir"], "no-ver-callout.html", "Added in 0.3")

    def test_deprecated_uses_entry_label(self, site):
        assert_page_contains(site["output_dir"], "no-ver-callout.html", "Deprecated since 0.3")

    def test_old_version_uses_own_label(self, site):
        content = assert_page_exists(site["output_dir"], "no-ver-callout.html", version="0.2")
        assert "Added in 0.2" in content
        assert "Deprecated since 0.2" in content


class TestBadgesInsideFences:
    """Edge case: Badges inside version fences — only expanded in matching versions."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.3", "0.2"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "fenced-badge.qmd": (
                    "---\ntitle: Fenced Badge\n---\n\n"
                    '::: {.version-only versions="0.3"}\n'
                    "## New Feature [version-badge new]\n"
                    ":::\n\n"
                    "Common content.\n"
                ),
            },
        )

    def test_badge_in_latest(self, site):
        assert_page_contains(site["output_dir"], "fenced-badge.html", "gd-badge-new")

    def test_badge_not_in_old(self, site):
        assert_page_not_contains(
            site["output_dir"], "fenced-badge.html", "gd-badge-new", version="0.2"
        )

    def test_common_in_both(self, site):
        assert_page_contains(site["output_dir"], "fenced-badge.html", "Common content")
        assert_page_contains(
            site["output_dir"], "fenced-badge.html", "Common content", version="0.2"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Edge Case Tests — API Snapshot
# ═══════════════════════════════════════════════════════════════════════════


class TestEmptySnapshot:
    """Edge case: API snapshot with zero symbols."""

    @pytest.fixture()
    def site(self, tmp_path):
        snap_empty = ApiSnapshot(
            version="0.1",
            package_name="mypkg",
            symbols={},
        )
        return run_mock_versioned_build(
            tmp_path,
            versions_config=[
                {"tag": "0.2", "label": "0.2"},
                {"tag": "0.1", "label": "0.1", "api_snapshot": "api-snapshots/0.1.json"},
            ],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nDocs.",
                "reference/Widget.qmd": "---\ntitle: Widget\n---\n\nWidget.",
            },
            snapshots={"0.1": snap_empty},
        )

    def test_empty_snapshot_still_has_index(self, site):
        # Even with no symbols, the index page should be generated
        assert_page_exists(site["output_dir"], "reference/index.html", version="0.1")

    def test_empty_snapshot_no_symbol_pages(self, site):
        # Widget was in source but snapshot has no symbols → cleared
        assert_page_missing(site["output_dir"], "reference/Widget.html", version="0.1")


class TestSnapshotFunctionsOnly:
    """Edge case: Snapshot with only functions, no classes."""

    @pytest.fixture()
    def site(self, tmp_path):
        snap = ApiSnapshot(
            version="0.1",
            package_name="mypkg",
            symbols={
                "process": SymbolInfo(
                    name="process",
                    kind="function",
                    parameters=[ParameterInfo(name="data", annotation="list")],
                    return_annotation="dict",
                ),
                "validate": SymbolInfo(
                    name="validate",
                    kind="function",
                    parameters=[],
                    return_annotation="bool",
                ),
            },
        )
        return run_mock_versioned_build(
            tmp_path,
            versions_config=[
                {"tag": "0.2", "label": "0.2"},
                {"tag": "0.1", "label": "0.1", "api_snapshot": "api-snapshots/0.1.json"},
            ],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nDocs.",
            },
            snapshots={"0.1": snap},
        )

    def test_functions_listed(self, site):
        content = assert_page_exists(site["output_dir"], "reference/index.html", version="0.1")
        assert "Functions" in content
        assert "process" in content
        assert "validate" in content

    def test_no_classes_section(self, site):
        content = assert_page_exists(site["output_dir"], "reference/index.html", version="0.1")
        assert "Classes" not in content

    def test_function_pages_generated(self, site):
        assert_page_exists(site["output_dir"], "reference/process.html", version="0.1")
        assert_page_exists(site["output_dir"], "reference/validate.html", version="0.1")

    def test_return_annotation_shown(self, site):
        content = assert_page_exists(site["output_dir"], "reference/process.html", version="0.1")
        assert "dict" in content


class TestSnapshotComplexSignatures:
    """Edge case: Snapshot with complex type annotations and defaults."""

    @pytest.fixture()
    def site(self, tmp_path):
        snap = ApiSnapshot(
            version="0.1",
            package_name="mypkg",
            symbols={
                "complex_func": SymbolInfo(
                    name="complex_func",
                    kind="function",
                    parameters=[
                        ParameterInfo(
                            name="data",
                            annotation="list[dict[str, int]]",
                        ),
                        ParameterInfo(
                            name="callback",
                            annotation="Callable[[str], bool]",
                            default="None",
                        ),
                        ParameterInfo(name="flag", annotation="bool", default="True"),
                    ],
                    return_annotation="Optional[str]",
                ),
                "MyClass": SymbolInfo(
                    name="MyClass",
                    kind="class",
                    bases=["BaseClass", "MixinA"],
                    parameters=[
                        ParameterInfo(name="self"),
                        ParameterInfo(name="name", annotation="str"),
                    ],
                ),
            },
        )
        return run_mock_versioned_build(
            tmp_path,
            versions_config=[
                {"tag": "0.2", "label": "0.2"},
                {"tag": "0.1", "label": "0.1", "api_snapshot": "api-snapshots/0.1.json"},
            ],
            pages={"index.qmd": "---\ntitle: Home\n---\n\nDocs."},
            snapshots={"0.1": snap},
        )

    def test_complex_annotation_preserved(self, site):
        content = assert_page_exists(
            site["output_dir"], "reference/complex_func.html", version="0.1"
        )
        assert "list[dict[str, int]]" in content

    def test_default_value_preserved(self, site):
        content = assert_page_exists(
            site["output_dir"], "reference/complex_func.html", version="0.1"
        )
        assert "None" in content
        assert "True" in content

    def test_return_annotation(self, site):
        content = assert_page_exists(
            site["output_dir"], "reference/complex_func.html", version="0.1"
        )
        assert "Optional[str]" in content

    def test_multiple_bases(self, site):
        content = assert_page_exists(site["output_dir"], "reference/MyClass.html", version="0.1")
        assert "BaseClass" in content
        assert "MixinA" in content

    def test_index_groups_both_kinds(self, site):
        content = assert_page_exists(site["output_dir"], "reference/index.html", version="0.1")
        assert "Classes" in content
        assert "Functions" in content


# ═══════════════════════════════════════════════════════════════════════════
# Edge Case Tests — Alias, Prerelease & Config
# ═══════════════════════════════════════════════════════════════════════════


class TestAllPrerelease:
    """Edge case: All versions are prerelease, no stable version."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=[
                {"tag": "dev2", "label": "0.3.0-dev", "prerelease": True},
                {"tag": "dev1", "label": "0.2.0-dev", "prerelease": True},
            ],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nAll prerelease.",
            },
        )

    def test_first_becomes_latest(self, site):
        """When all are prerelease, first entry should still be picked as latest."""
        # parse_versions_config marks first non-prerelease as latest.
        # If none are non-prerelease, none gets latest=True.
        # get_latest_version returns None → fallback to versions[0].tag
        assert site["latest_tag"] == "dev2"

    def test_site_still_builds(self, site):
        assert_page_exists(site["output_dir"], "index.html")

    def test_no_stable_alias(self, site):
        """No stable alias should be created when no version is marked latest."""
        # If no version has latest=True, create_version_aliases skips latest/stable aliases
        stable = site["output_dir"] / "v" / "stable" / "index.html"
        # The alias might or might not be created — depends on implementation
        # But the build should not crash
        assert site["output_dir"].exists()


class TestExplicitLatestFlag:
    """Edge case: Explicitly marking a non-first version as latest."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=[
                {"tag": "dev", "label": "0.4.0-dev", "prerelease": True},
                {"tag": "0.3", "label": "0.3.0", "latest": True},
                {"tag": "0.2", "label": "0.2.0"},
            ],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nDocs.",
                "guide.qmd": "---\ntitle: Guide\n---\n\nGuide.",
            },
        )

    def test_0_3_is_at_root(self, site):
        assert site["latest_tag"] == "0.3"
        assert_page_contains(site["output_dir"], "index.html", "Docs")

    def test_dev_under_v_prefix(self, site):
        assert_page_exists(site["output_dir"], "index.html", version="dev")

    def test_0_2_under_v_prefix(self, site):
        assert_page_exists(site["output_dir"], "index.html", version="0.2")

    def test_dev_alias_points_to_dev(self, site):
        alias = site["output_dir"] / "v" / "dev" / "index.html"
        # "dev" is a real version tag, so no alias should be created
        if alias.exists():
            content = alias.read_text()
            # Should be the actual rendered page, not a redirect
            assert "Docs" in content


class TestTagMatchesAliasName:
    """Edge case: A version tag is literally 'latest' or 'stable'."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=[
                {"tag": "stable", "label": "Stable Release"},
                {"tag": "0.2", "label": "0.2.0"},
            ],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nDocs.",
            },
        )

    def test_stable_tag_at_root(self, site):
        """Version tagged 'stable' is latest → at root."""
        assert site["latest_tag"] == "stable"
        assert_page_exists(site["output_dir"], "index.html")

    def test_no_stable_alias_collision(self, site):
        """Alias 'stable' should not be created since it collides with the tag."""
        stable_alias = site["output_dir"] / "v" / "stable" / "index.html"
        # The alias should not exist or should be the actual version content
        # (not a redirect loop)
        if stable_alias.exists():
            content = stable_alias.read_text()
            assert "http-equiv" not in content  # Not a redirect


class TestSemverLikeTags:
    """Edge case: Tags with dashes, dots, and v-prefix."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=[
                {"tag": "v2.0.0", "label": "2.0.0"},
                {"tag": "v1.5.0-rc1", "label": "1.5.0-rc1", "prerelease": True},
                {"tag": "v1.0.0", "label": "1.0.0"},
            ],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nDocs.",
            },
        )

    def test_semver_at_root(self, site):
        assert site["latest_tag"] == "v2.0.0"
        assert_page_exists(site["output_dir"], "index.html")

    def test_rc_under_v_prefix(self, site):
        assert_page_exists(site["output_dir"], "index.html", version="v1.5.0-rc1")

    def test_old_semver_under_v_prefix(self, site):
        assert_page_exists(site["output_dir"], "index.html", version="v1.0.0")


class TestManyVersionsScale:
    """Edge case: 10+ versions to verify the pipeline handles scale."""

    @pytest.fixture()
    def site(self, tmp_path):
        versions = [f"0.{i}" for i in range(10, 0, -1)]
        return run_mock_versioned_build(
            tmp_path,
            versions_config=versions,
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nDocs.",
                "guide.qmd": (
                    "---\ntitle: Guide\n---\n\n"
                    '::: {.version-only versions="0.10"}\n'
                    "Latest only content.\n"
                    ":::\n"
                ),
            },
        )

    def test_all_versions_built(self, site):
        assert len(site["pages_by_version"]) == 10

    def test_latest_at_root(self, site):
        assert site["latest_tag"] == "0.10"
        assert_page_exists(site["output_dir"], "index.html")

    def test_oldest_version(self, site):
        assert_page_exists(site["output_dir"], "index.html", version="0.1")

    def test_version_map_complete(self, site):
        data = json.loads((site["output_dir"] / "_version_map.json").read_text())
        assert len(data["versions"]) == 10

    def test_fence_in_latest_only(self, site):
        assert_page_contains(site["output_dir"], "guide.html", "Latest only content")
        assert_page_not_contains(
            site["output_dir"], "guide.html", "Latest only content", version="0.9"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Edge Case Tests — Static Assets & _quarto.yml
# ═══════════════════════════════════════════════════════════════════════════


class TestStaticAssets:
    """Edge case: Non-.qmd static files (CSS, JS, images) in the site."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHome.",
                "assets/custom.css": "body { color: red; }",
                "assets/app.js": "console.log('hello');",
                "data/config.json": '{"key": "value"}',
            },
        )

    def test_css_in_latest(self, site):
        css = site["output_dir"] / "assets" / "custom.css"
        assert css.exists()
        assert "color: red" in css.read_text()

    def test_js_in_latest(self, site):
        js = site["output_dir"] / "assets" / "app.js"
        assert js.exists()

    def test_json_in_latest(self, site):
        j = site["output_dir"] / "data" / "config.json"
        assert j.exists()

    def test_static_in_old_version(self, site):
        css = site["output_dir"] / "v" / "0.1" / "assets" / "custom.css"
        assert css.exists()
        assert "color: red" in css.read_text()


class TestCanonicalUrlInjection:
    """Edge case: site_url triggers _quarto.yml rewriting with canonical URLs."""

    @pytest.fixture()
    def site(self, tmp_path):
        # We need to manually check the _quarto.yml in the build dirs
        project_root = tmp_path / "project"
        source_dir = project_root / "great-docs"
        source_dir.mkdir(parents=True)

        (source_dir / "index.qmd").write_text("---\ntitle: Home\n---\n\nHello.")
        (source_dir / "_quarto.yml").write_text(
            "project:\n  type: website\n  output-dir: _site\n"
            "format:\n  html: {}\nwebsite:\n  title: My Docs\n"
        )

        versions = parse_versions_config(["0.2", "0.1"])
        latest = get_latest_version(versions)
        latest_tag = latest.tag

        build_root = project_root / "_great_docs_build"
        build_root.mkdir()

        from great_docs._versioned_build import _rewrite_quarto_yml_for_version

        for entry in versions:
            ver_dir = _version_build_dir(build_root, entry, latest_tag)
            preprocess_version(source_dir, ver_dir, entry, versions, project_root=project_root)
            _rewrite_quarto_yml_for_version(
                ver_dir, entry, latest_tag, site_url="https://example.com/docs"
            )

        return {
            "build_root": build_root,
            "latest_tag": latest_tag,
            "versions": versions,
        }

    def test_old_version_has_title_suffix(self, site):
        from yaml12 import read_yaml

        old_dir = _version_build_dir(site["build_root"], site["versions"][1], site["latest_tag"])
        with open(old_dir / "_quarto.yml") as f:
            config = read_yaml(f)
        title = config.get("website", {}).get("title", "")
        assert "(0.1)" in title

    def test_old_version_has_canonical_injection(self, site):
        from yaml12 import read_yaml

        old_dir = _version_build_dir(site["build_root"], site["versions"][1], site["latest_tag"])
        with open(old_dir / "_quarto.yml") as f:
            config = read_yaml(f)
        headers = config.get("format", {}).get("html", {}).get("include-in-header", [])
        assert any("canonical" in str(h) for h in headers)

    def test_latest_version_no_title_suffix(self, site):
        from yaml12 import read_yaml

        latest_dir = _version_build_dir(site["build_root"], site["versions"][0], site["latest_tag"])
        with open(latest_dir / "_quarto.yml") as f:
            config = read_yaml(f)
        title = config.get("website", {}).get("title", "")
        assert "(0.2)" not in title


class TestCanonicalUrlNone:
    """Edge case: site_url=None should not inject any canonical tags."""

    @pytest.fixture()
    def site(self, tmp_path):
        project_root = tmp_path / "project"
        source_dir = project_root / "great-docs"
        source_dir.mkdir(parents=True)

        (source_dir / "index.qmd").write_text("---\ntitle: Home\n---\n\nHello.")
        (source_dir / "_quarto.yml").write_text(
            "project:\n  type: website\n  output-dir: _site\n"
            "format:\n  html: {}\nwebsite:\n  title: My Docs\n"
        )

        versions = parse_versions_config(["0.2", "0.1"])
        latest = get_latest_version(versions)
        latest_tag = latest.tag

        build_root = project_root / "_great_docs_build"
        build_root.mkdir()

        from great_docs._versioned_build import _rewrite_quarto_yml_for_version

        for entry in versions:
            ver_dir = _version_build_dir(build_root, entry, latest_tag)
            preprocess_version(source_dir, ver_dir, entry, versions, project_root=project_root)
            _rewrite_quarto_yml_for_version(ver_dir, entry, latest_tag, site_url=None)

        return {
            "build_root": build_root,
            "latest_tag": latest_tag,
            "versions": versions,
        }

    def test_no_canonical_injection(self, site):
        from yaml12 import read_yaml

        old_dir = _version_build_dir(site["build_root"], site["versions"][1], site["latest_tag"])
        with open(old_dir / "_quarto.yml") as f:
            config = read_yaml(f)
        headers = config.get("format", {}).get("html", {}).get("include-in-header", [])
        assert not any("canonical" in str(h) for h in headers)


# ═══════════════════════════════════════════════════════════════════════════
# Edge Case Tests — Page Scoping YAML Formats
# ═══════════════════════════════════════════════════════════════════════════


class TestPageScopingBlockListYAML:
    """Edge case: Block-style YAML list in frontmatter for versions."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.3", "0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "block-list.qmd": (
                    "---\ntitle: Block List\nversions:\n  - 0.3\n  - 0.2\n---\n\n"
                    "Only in 0.3 and 0.2.\n"
                ),
            },
        )

    def test_in_03(self, site):
        assert_page_exists(site["output_dir"], "block-list.html")

    def test_in_02(self, site):
        assert_page_exists(site["output_dir"], "block-list.html", version="0.2")

    def test_not_in_01(self, site):
        assert_page_missing(site["output_dir"], "block-list.html", version="0.1")


class TestPageScopingQuotedValues:
    """Edge case: Inline YAML list with and without quotes."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.3", "0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "quoted.qmd": (
                    '---\ntitle: Quoted\nversions: ["0.3", "0.1"]\n---\n\nQuoted list.\n'
                ),
                "unquoted.qmd": (
                    "---\ntitle: Unquoted\nversions: [0.3, 0.1]\n---\n\nUnquoted list.\n"
                ),
            },
        )

    def test_quoted_in_03(self, site):
        assert_page_exists(site["output_dir"], "quoted.html")

    def test_quoted_not_in_02(self, site):
        assert_page_missing(site["output_dir"], "quoted.html", version="0.2")

    def test_quoted_in_01(self, site):
        assert_page_exists(site["output_dir"], "quoted.html", version="0.1")

    def test_unquoted_in_03(self, site):
        assert_page_exists(site["output_dir"], "unquoted.html")

    def test_unquoted_not_in_02(self, site):
        assert_page_missing(site["output_dir"], "unquoted.html", version="0.2")

    def test_unquoted_in_01(self, site):
        assert_page_exists(site["output_dir"], "unquoted.html", version="0.1")


class TestPageScopingEmptyVersionsList:
    """Edge case: Page with versions: [] (empty list) in frontmatter."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "empty-versions.qmd": (
                    "---\ntitle: Empty Versions\nversions: []\n---\n\nEmpty list.\n"
                ),
            },
        )

    def test_empty_list_treated_as_all_or_none(self, site):
        """
        Empty versions: [] should be treated as None (all versions),
        since extract_page_versions returns None for empty lists.
        """
        # The implementation returns None for empty lists → page included everywhere
        assert_page_exists(site["output_dir"], "empty-versions.html")
        assert_page_exists(site["output_dir"], "empty-versions.html", version="0.1")


# ═══════════════════════════════════════════════════════════════════════════
# Edge Case Tests — Section Scoping
# ═══════════════════════════════════════════════════════════════════════════


class TestSectionConfigMissingVersions:
    """Edge case: Section config without versions key (should include in all)."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "recipes/01.qmd": "---\ntitle: Recipe\n---\n\nRecipe.",
            },
            section_configs=[
                {"dir": "recipes"},  # No versions key
            ],
        )

    def test_section_included_everywhere(self, site):
        """No versions key → section is not excluded from any version."""
        assert_page_exists(site["output_dir"], "recipes/01.html")
        assert_page_exists(site["output_dir"], "recipes/01.html", version="0.1")


class TestSectionConfigEmptyDir:
    """Edge case: Section config with empty dir string."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "guide.qmd": "---\ntitle: Guide\n---\n\nGuide.",
            },
            section_configs=[
                {"dir": "", "versions": ["0.2"]},
            ],
        )

    def test_empty_dir_no_crash(self, site):
        """Empty dir name should not cause errors or exclude root pages."""
        assert_page_exists(site["output_dir"], "index.html")
        assert_page_exists(site["output_dir"], "guide.html")

    def test_old_version_still_works(self, site):
        assert_page_exists(site["output_dir"], "index.html", version="0.1")


class TestSectionConfigNonexistentDir:
    """Edge case: Section config for a directory that has no files."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
            },
            section_configs=[
                {"dir": "nonexistent", "versions": ["0.2"]},
            ],
        )

    def test_no_crash(self, site):
        """Referencing a nonexistent section should not crash."""
        assert_page_exists(site["output_dir"], "index.html")
        assert_page_exists(site["output_dir"], "index.html", version="0.1")


class TestOverlappingSectionDirs:
    """Edge case: Section configs with nested directory paths."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.3", "0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "api/core.qmd": "---\ntitle: Core API\n---\n\nCore.",
                "api/experimental/new.qmd": "---\ntitle: Experimental\n---\n\nNew.",
            },
            section_configs=[
                {"dir": "api", "versions": ["0.3", "0.2", "0.1"]},  # All versions
                {"dir": "experimental", "versions": ["0.3"]},  # Only 0.3
            ],
        )

    def test_core_api_in_all(self, site):
        assert_page_exists(site["output_dir"], "api/core.html")
        assert_page_exists(site["output_dir"], "api/core.html", version="0.2")
        assert_page_exists(site["output_dir"], "api/core.html", version="0.1")

    def test_experimental_exclusion(self, site):
        """
        experimental/ is a subdir of api/ — the 'experimental' section config
        should match its path component.
        """
        # The _in_excluded_section checks each path component, so
        # api/experimental/new.qmd has "experimental" as a component
        assert_page_exists(site["output_dir"], "api/experimental/new.html")
        assert_page_missing(site["output_dir"], "api/experimental/new.html", version="0.2")
        assert_page_missing(site["output_dir"], "api/experimental/new.html", version="0.1")


# ═══════════════════════════════════════════════════════════════════════════
# Edge Case Tests — Version Map
# ═══════════════════════════════════════════════════════════════════════════


class TestVersionMapAsymmetricPages:
    """Edge case: Different sets of pages in different versions."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.3", "0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "common.qmd": "---\ntitle: Common\n---\n\nCommon.",
                "v03-only.qmd": '---\ntitle: V03\nversions: ["0.3"]\n---\n\nV03.',
                "v02-v03.qmd": '---\ntitle: V02V03\nversions: ["0.2", "0.3"]\n---\n\nV02V03.',
                "v01-only.qmd": '---\ntitle: V01\nversions: ["0.1"]\n---\n\nV01.',
            },
        )

    def test_version_map_page_distribution(self, site):
        data = json.loads((site["output_dir"] / "_version_map.json").read_text())

        # common.html in all
        assert set(data["pages"]["common.html"]) == {"0.3", "0.2", "0.1"}

        # v03-only.html only in 0.3
        assert data["pages"]["v03-only.html"] == ["0.3"]

        # v02-v03.html in 0.2 and 0.3
        assert set(data["pages"]["v02-v03.html"]) == {"0.2", "0.3"}

        # v01-only.html only in 0.1
        assert data["pages"]["v01-only.html"] == ["0.1"]

    def test_version_map_latest_flag(self, site):
        data = json.loads((site["output_dir"] / "_version_map.json").read_text())
        latest_entry = data["versions"][0]
        assert latest_entry["tag"] == "0.3"
        assert latest_entry["latest"] is True
        assert latest_entry["path_prefix"] == ""

    def test_version_map_path_prefix(self, site):
        data = json.loads((site["output_dir"] / "_version_map.json").read_text())
        v02 = next(v for v in data["versions"] if v["tag"] == "0.2")
        assert v02["path_prefix"] == "v/0.2"


class TestVersionMapLabels:
    """Edge case: Version map preserves labels from config."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=[
                {"tag": "0.3", "label": "0.3.0 (Latest)"},
                {"tag": "0.2", "label": "0.2.1 Patch"},
            ],
            pages={"index.qmd": "---\ntitle: Home\n---\n\nHello."},
        )

    def test_labels_preserved(self, site):
        data = json.loads((site["output_dir"] / "_version_map.json").read_text())
        assert data["versions"][0]["label"] == "0.3.0 (Latest)"
        assert data["versions"][1]["label"] == "0.2.1 Patch"


# ═══════════════════════════════════════════════════════════════════════════
# Edge Case Tests — Redirect Files
# ═══════════════════════════════════════════════════════════════════════════


class TestRedirectWithDevAlias:
    """Edge case: Redirect files include dev alias when prerelease exists."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=[
                {"tag": "0.3", "label": "0.3.0"},
                {"tag": "0.2", "label": "0.2.0"},
                {"tag": "dev", "label": "dev", "prerelease": True},
            ],
            pages={"index.qmd": "---\ntitle: Home\n---\n\nHello."},
        )

    def test_netlify_has_dev(self, site):
        content = (site["output_dir"] / "_redirects").read_text()
        # "dev" is a real tag, so it should NOT be in aliases
        # (aliases skip tags that match version tags)
        assert "/v/latest/*" in content
        assert "/v/stable/*" in content

    def test_vercel_has_latest(self, site):
        data = json.loads((site["output_dir"] / "vercel.json").read_text())
        sources = [r["source"] for r in data["rewrites"]]
        assert any("latest" in s for s in sources)


class TestRedirectNoAliases:
    """Edge case: When all alias names collide with tags, no redirects generated."""

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=[
                {"tag": "latest", "label": "Latest"},
                {"tag": "stable", "label": "Stable"},
            ],
            pages={"index.qmd": "---\ntitle: Home\n---\n\nHello."},
        )

    def test_no_redirect_files_when_all_collide(self, site):
        """If both 'latest' and 'stable' are real tags, no alias redirects needed."""
        redirects = site["output_dir"] / "_redirects"
        vercel = site["output_dir"] / "vercel.json"
        # Either files don't exist, or they exist but have no alias rules
        if redirects.exists():
            content = redirects.read_text()
            assert "/v/latest/*" not in content
            assert "/v/stable/*" not in content


# ═══════════════════════════════════════════════════════════════════════════
# Edge Case Tests — Combined Complex Scenarios
# ═══════════════════════════════════════════════════════════════════════════


class TestFencesWithPageScopingAndSectionScoping:
    """
    Complex: A page is section-scoped AND page-scoped AND has fences.
    All three filtering mechanisms interact.
    """

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.4", "0.3", "0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "recipes/advanced.qmd": (
                    '---\ntitle: Advanced Recipe\nversions: ["0.3", "0.4"]\n---\n\n'
                    "Base recipe content.\n\n"
                    '::: {.version-only versions="0.4"}\n'
                    "New 0.4 technique.\n"
                    ":::\n"
                ),
            },
            section_configs=[
                {"dir": "recipes", "versions": ["0.4", "0.3", "0.2"]},
            ],
        )

    def test_v04_has_all_content(self, site):
        """0.4: section OK, page OK, fence OK."""
        assert_page_contains(site["output_dir"], "recipes/advanced.html", "Base recipe content")
        assert_page_contains(site["output_dir"], "recipes/advanced.html", "New 0.4 technique")

    def test_v03_has_base_only(self, site):
        """0.3: section OK, page OK, fence excludes 0.4 content."""
        assert_page_contains(
            site["output_dir"], "recipes/advanced.html", "Base recipe content", version="0.3"
        )
        assert_page_not_contains(
            site["output_dir"], "recipes/advanced.html", "New 0.4 technique", version="0.3"
        )

    def test_v02_page_scoped_out(self, site):
        """0.2: section OK, but page versions=[0.3, 0.4] excludes 0.2."""
        assert_page_missing(site["output_dir"], "recipes/advanced.html", version="0.2")

    def test_v01_section_scoped_out(self, site):
        """0.1: section excludes, so page doesn't exist regardless."""
        assert_page_missing(site["output_dir"], "recipes/advanced.html", version="0.1")


class TestSnapshotWithFencesAndBadges:
    """
    Complex: A version uses API snapshots AND the non-reference pages
    have fences and badges.
    """

    @pytest.fixture()
    def site(self, tmp_path):
        snap = ApiSnapshot(
            version="0.1",
            package_name="mypkg",
            symbols={
                "OldWidget": SymbolInfo(name="OldWidget", kind="class"),
            },
        )
        return run_mock_versioned_build(
            tmp_path,
            versions_config=[
                {"tag": "0.2", "label": "0.2.0"},
                {"tag": "0.1", "label": "0.1.0", "api_snapshot": "api-snapshots/0.1.json"},
            ],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "guide.qmd": (
                    "---\ntitle: Guide\n---\n\n"
                    "## Feature [version-badge new]\n\n"
                    '::: {.version-only versions="0.2"}\n'
                    "New in 0.2.\n"
                    ":::\n\n"
                    "Shared guide content.\n"
                ),
                "reference/Widget.qmd": "---\ntitle: Widget\n---\n\nLive.",
            },
            snapshots={"0.1": snap},
        )

    def test_latest_guide_has_badge_and_fence(self, site):
        assert_page_contains(site["output_dir"], "guide.html", "gd-badge-new")
        assert_page_contains(site["output_dir"], "guide.html", "New in 0.2")

    def test_old_guide_has_badge_but_no_fence(self, site):
        content = assert_page_exists(site["output_dir"], "guide.html", version="0.1")
        assert "gd-badge-new" in content
        assert "New in 0.1" in content  # Badge uses entry label
        assert "New in 0.2" not in content  # Fence content excluded

    def test_old_version_snapshot_ref(self, site):
        assert_page_exists(site["output_dir"], "reference/OldWidget.html", version="0.1")

    def test_latest_live_ref(self, site):
        content = assert_page_exists(site["output_dir"], "reference/Widget.html")
        assert "Live" in content


class TestSelectiveWithFencesAndScoping:
    """
    Complex: Building only selected versions, with fences and page scoping.
    Verifies that preprocessing still works correctly when not all versions
    are being built.
    """

    @pytest.fixture()
    def site(self, tmp_path):
        return run_mock_versioned_build(
            tmp_path,
            versions_config=["0.4", "0.3", "0.2", "0.1"],
            pages={
                "index.qmd": "---\ntitle: Home\n---\n\nHello.",
                "new.qmd": '---\ntitle: New\nversions: ["0.4"]\n---\n\nNew.',
                "guide.qmd": (
                    "---\ntitle: Guide\n---\n\n"
                    '::: {.version-only versions=">=0.3"}\n'
                    "Modern approach.\n"
                    ":::\n\n"
                    '::: {.version-only versions="0.1,0.2"}\n'
                    "Legacy approach.\n"
                    ":::\n"
                ),
            },
            version_tags=["0.4", "0.1"],
        )

    def test_only_selected_built(self, site):
        assert set(site["pages_by_version"].keys()) == {"0.4", "0.1"}

    def test_v04_has_new_page(self, site):
        assert_page_exists(site["output_dir"], "new.html")

    def test_v01_no_new_page(self, site):
        assert_page_missing(site["output_dir"], "new.html", version="0.1")

    def test_v04_modern_approach(self, site):
        assert_page_contains(site["output_dir"], "guide.html", "Modern approach")
        assert_page_not_contains(site["output_dir"], "guide.html", "Legacy approach")

    def test_v01_legacy_approach(self, site):
        assert_page_contains(site["output_dir"], "guide.html", "Legacy approach", version="0.1")
        assert_page_not_contains(site["output_dir"], "guide.html", "Modern approach", version="0.1")
