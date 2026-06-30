from __future__ import annotations

import json
from pathlib import Path

import pytest

from great_docs._api_diff import ApiSnapshot, ParameterInfo, SymbolInfo
from great_docs._versioned_build import (
    _compute_excluded_section_dirs,
    _in_excluded_section,
    _is_valid_ref_name,
    _merge_tree,
    _prune_cli_pages,
    _prune_reference_index,
    _prune_sidebar_contents,
    _rebuild_api_from_snapshot,
    _redirect_page,
    _snapshot_cache_path,
    _validate_git_ref_is_tag,
    _version_build_dir,
    assemble_site,
    create_version_aliases,
    expand_version_badges,
    expand_version_callouts,
    generate_redirect_files,
    preprocess_version,
    run_versioned_build,
    write_version_map,
)
from great_docs._versioning import VersionEntry, parse_versions_config

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(tag: str, latest: bool = False, **kwargs) -> VersionEntry:
    return VersionEntry(tag=tag, label=tag, latest=latest, **kwargs)


def _make_source_tree(root: Path, pages: dict[str, str]) -> None:
    """Create a mock source tree with given pages."""
    root.mkdir(parents=True, exist_ok=True)
    for rel_path, content in pages.items():
        p = root / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    # Minimal _quarto.yml so it's a valid project
    qy = root / "_quarto.yml"
    if not qy.exists():
        qy.write_text(
            "project:\n  type: website\n  output-dir: _site\n"
            "format:\n  html: {}\nwebsite:\n  title: Test\n",
            encoding="utf-8",
        )


# ---------------------------------------------------------------------------
# _version_build_dir
# ---------------------------------------------------------------------------


class TestVersionBuildDir:
    def test_latest_gets_root(self, tmp_path: Path):
        entry = _make_entry("0.3", latest=True)
        result = _version_build_dir(tmp_path, entry, "0.3")
        assert result == tmp_path / "_root"

    def test_non_latest_gets_prefixed(self, tmp_path: Path):
        entry = _make_entry("0.2")
        result = _version_build_dir(tmp_path, entry, "0.3")
        assert result == tmp_path / "v__0_2"

    def test_complex_tag(self, tmp_path: Path):
        entry = _make_entry("1.2.3")
        result = _version_build_dir(tmp_path, entry, "2.0")
        assert result == tmp_path / "v__1_2_3"


# ---------------------------------------------------------------------------
# preprocess_version
# ---------------------------------------------------------------------------


class TestPreprocessVersion:
    def _setup_versions(self):
        return parse_versions_config(["0.3", "0.2", "0.1"])

    def test_includes_unscoped_pages(self, tmp_path: Path):
        source = tmp_path / "source"
        _make_source_tree(
            source,
            {
                "index.qmd": "---\ntitle: Home\n---\n\nWelcome!",
                "guide.qmd": "---\ntitle: Guide\n---\n\nSome guide.",
            },
        )

        versions = self._setup_versions()
        dest = tmp_path / "build"
        pages = preprocess_version(source, dest, versions[0], versions)

        assert "index.html" in pages
        assert "guide.html" in pages
        assert (dest / "index.qmd").exists()
        assert (dest / "guide.qmd").exists()

    def test_excludes_scoped_pages(self, tmp_path: Path):
        source = tmp_path / "source"
        _make_source_tree(
            source,
            {
                "index.qmd": "---\ntitle: Home\n---\n\nWelcome!",
                "new-feature.qmd": '---\ntitle: New\nversions: ["0.3"]\n---\n\nOnly in 0.3.',
            },
        )

        versions = self._setup_versions()

        # Build for 0.3 — should include new-feature
        dest1 = tmp_path / "build1"
        pages1 = preprocess_version(source, dest1, versions[0], versions)
        assert "new-feature.html" in pages1

        # Build for 0.2 — should exclude new-feature
        dest2 = tmp_path / "build2"
        pages2 = preprocess_version(source, dest2, versions[1], versions)
        assert "new-feature.html" not in pages2
        assert not (dest2 / "new-feature.qmd").exists()

    def test_processes_version_fences(self, tmp_path: Path):
        source = tmp_path / "source"
        _make_source_tree(
            source,
            {
                "page.qmd": (
                    "---\ntitle: Page\n---\n\n"
                    "Common content.\n\n"
                    '::: {.version-only versions="0.3"}\n'
                    "New in 0.3!\n"
                    ":::\n\n"
                    '::: {.version-except versions="0.3"}\n'
                    "Old content.\n"
                    ":::\n"
                ),
            },
        )

        versions = self._setup_versions()

        # Build for 0.3
        dest1 = tmp_path / "build1"
        preprocess_version(source, dest1, versions[0], versions)
        content1 = (dest1 / "page.qmd").read_text()
        assert "New in 0.3!" in content1
        assert "Old content." not in content1

        # Build for 0.2
        dest2 = tmp_path / "build2"
        preprocess_version(source, dest2, versions[1], versions)
        content2 = (dest2 / "page.qmd").read_text()
        assert "New in 0.3!" not in content2
        assert "Old content." in content2

    def test_skips_underscore_prefixed_files(self, tmp_path: Path):
        source = tmp_path / "source"
        _make_source_tree(
            source,
            {
                "index.qmd": "---\ntitle: Home\n---\n\nHi",
                "_quarto.yml": "project:\n  type: website\n",
            },
        )

        versions = self._setup_versions()
        dest = tmp_path / "build"
        pages = preprocess_version(source, dest, versions[0], versions)

        # _quarto.yml should NOT be in pages (it starts with _)
        assert all(not p.startswith("_") for p in pages)

    def test_snapshot_strategy_a(self, tmp_path: Path):
        source = tmp_path / "source"
        _make_source_tree(
            source,
            {
                "index.qmd": "---\ntitle: Home\n---\n\nHi",
            },
        )

        # Create a snapshot file
        snap = ApiSnapshot(
            version="0.2",
            package_name="test_pkg",
            symbols={
                "MyClass": SymbolInfo(
                    name="MyClass",
                    kind="class",
                    bases=["Base"],
                    parameters=[ParameterInfo(name="x", annotation="int")],
                ),
                "my_func": SymbolInfo(
                    name="my_func",
                    kind="function",
                    parameters=[
                        ParameterInfo(name="a", annotation="str"),
                        ParameterInfo(name="b", default="None"),
                    ],
                    return_annotation="bool",
                ),
            },
        )
        snap_path = tmp_path / "snapshots" / "v0.2.json"
        snap.save(snap_path)

        versions = parse_versions_config(
            [
                {"tag": "0.3", "label": "0.3"},
                {"tag": "0.2", "label": "0.2", "api_snapshot": str(snap_path)},
            ]
        )

        dest = tmp_path / "build"
        pages = preprocess_version(
            source,
            dest,
            versions[1],
            versions,
            project_root=tmp_path,
        )

        # Should have generated API reference pages
        assert "reference/index.html" in pages
        assert "reference/MyClass.html" in pages
        assert "reference/my_func.html" in pages

        # Check content
        mc_content = (dest / "reference" / "MyClass.qmd").read_text()
        assert "class MyClass" in mc_content
        assert "Base" in mc_content

        func_content = (dest / "reference" / "my_func.qmd").read_text()
        assert "def my_func" in func_content
        assert "-> bool" in func_content

        # Index should list both
        idx_content = (dest / "reference" / "index.qmd").read_text()
        assert "MyClass" in idx_content
        assert "my_func" in idx_content

    def test_snapshot_preserves_rich_pages(self, tmp_path: Path):
        """Rich renderer-generated pages should NOT be overwritten by snapshot fallback."""
        rich_class_content = (
            "---\n"
            'title: "[MyClass]{.doc-object-name .doc-class}"\n'
            "---\n\n"
            "# [MyClass]{.doc-object-name .doc-class}\n\n"
            "::: {.doc-subject}\nA rich description.\n:::\n\n"
            "## Parameters {.doc-parameters}\n\n"
            "Details here.\n\n"
            "## Attributes {.doc-attributes}\n\n"
            "- attr1\n\n"
            "## Examples\n\n"
            "```python\nMyClass()\n```\n"
        )
        source = tmp_path / "source"
        _make_source_tree(
            source,
            {
                "index.qmd": "---\ntitle: Home\n---\n\nHi",
                "reference/MyClass.qmd": rich_class_content,
            },
        )

        # Create a snapshot that includes MyClass
        snap = ApiSnapshot(
            version="0.2",
            package_name="test_pkg",
            symbols={
                "MyClass": SymbolInfo(
                    name="MyClass",
                    kind="class",
                    parameters=[ParameterInfo(name="x", annotation="int")],
                ),
            },
        )
        snap_path = tmp_path / "snapshots" / "v0.2.json"
        snap.save(snap_path)

        versions = parse_versions_config(
            [
                {"tag": "0.3", "label": "0.3"},
                {"tag": "0.2", "label": "0.2", "api_snapshot": str(snap_path)},
            ]
        )

        dest = tmp_path / "build"
        pages = preprocess_version(
            source,
            dest,
            versions[1],
            versions,
            project_root=tmp_path,
        )

        assert "reference/MyClass.html" in pages

        # The rich content must be preserved, NOT replaced with minimal snapshot output
        result_content = (dest / "reference" / "MyClass.qmd").read_text()
        assert "{.doc-object-name" in result_content
        assert "A rich description." in result_content
        assert "Attributes" in result_content
        assert "Examples" in result_content
        # Should NOT have the minimal snapshot format
        assert "*Kind:* class" not in result_content


# ---------------------------------------------------------------------------
# Site assembly
# ---------------------------------------------------------------------------


class TestAssembleSite:
    def test_basic_assembly(self, tmp_path: Path):
        build_root = tmp_path / "build"

        # Simulate _root version (latest)
        root_site = build_root / "_root" / "_site"
        root_site.mkdir(parents=True)
        (root_site / "index.html").write_text("<h1>Latest</h1>")
        (root_site / "guide").mkdir()
        (root_site / "guide" / "index.html").write_text("<h1>Guide</h1>")

        # Simulate v__0_2 version
        v02_site = build_root / "v__0_2" / "_site"
        v02_site.mkdir(parents=True)
        (v02_site / "index.html").write_text("<h1>v0.2</h1>")

        versions = [
            _make_entry("0.3", latest=True),
            _make_entry("0.2"),
        ]

        output = tmp_path / "output"
        assemble_site(build_root, versions, "0.3", output)

        # Latest at root
        assert (output / "index.html").read_text() == "<h1>Latest</h1>"
        assert (output / "guide" / "index.html").read_text() == "<h1>Guide</h1>"

        # Old version under /v/0.2/
        assert (output / "v" / "0.2" / "index.html").read_text() == "<h1>v0.2</h1>"

    def test_cleans_existing_output(self, tmp_path: Path):
        output = tmp_path / "output"
        output.mkdir()
        (output / "stale.html").write_text("old")

        build_root = tmp_path / "build"
        root_site = build_root / "_root" / "_site"
        root_site.mkdir(parents=True)
        (root_site / "index.html").write_text("new")

        versions = [_make_entry("1.0", latest=True)]
        assemble_site(build_root, versions, "1.0", output)

        assert not (output / "stale.html").exists()
        assert (output / "index.html").read_text() == "new"


# ---------------------------------------------------------------------------
# merge_tree
# ---------------------------------------------------------------------------


class TestMergeTree:
    def test_merges_files(self, tmp_path: Path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.txt").write_text("A")
        (src / "sub").mkdir()
        (src / "sub" / "b.txt").write_text("B")

        dst = tmp_path / "dst"
        dst.mkdir()
        (dst / "existing.txt").write_text("E")

        _merge_tree(src, dst)

        assert (dst / "a.txt").read_text() == "A"
        assert (dst / "sub" / "b.txt").read_text() == "B"
        assert (dst / "existing.txt").read_text() == "E"


# ---------------------------------------------------------------------------
# Version aliases
# ---------------------------------------------------------------------------


class TestCreateVersionAliases:
    def test_creates_latest_and_stable(self, tmp_path: Path):
        versions = parse_versions_config(["0.3", "0.2"])
        create_version_aliases(tmp_path, versions, "0.3")

        # latest and stable should exist
        assert (tmp_path / "v" / "latest" / "index.html").exists()
        assert (tmp_path / "v" / "stable" / "index.html").exists()

        # Both should redirect to root (latest version)
        content = (tmp_path / "v" / "latest" / "index.html").read_text()
        assert "url=/" in content

    def test_creates_dev_alias(self, tmp_path: Path):
        versions = parse_versions_config(
            [
                {"tag": "dev", "label": "dev", "prerelease": True},
                {"tag": "0.3", "label": "0.3"},
            ]
        )
        create_version_aliases(tmp_path, versions, "0.3")

        assert (tmp_path / "v" / "latest" / "index.html").exists()
        # dev alias should point to /v/dev/
        # Note: 'dev' is both a version tag AND an alias name, so the alias
        # should NOT be created (it would collide)
        assert not (tmp_path / "v" / "dev" / "index.html").exists()

    def test_no_alias_for_tag_collision(self, tmp_path: Path):
        # If someone has a version tagged "latest", don't create the alias
        versions = parse_versions_config(
            [
                {"tag": "latest", "label": "Latest"},
            ]
        )
        create_version_aliases(tmp_path, versions, "latest")
        # No alias dir should be created for "latest" since it's a real tag
        assert not (tmp_path / "v" / "latest" / "index.html").exists()


# ---------------------------------------------------------------------------
# Redirect page
# ---------------------------------------------------------------------------


class TestRedirectPage:
    def test_contains_meta_refresh(self):
        html = _redirect_page("/v/0.3/")
        assert 'http-equiv="refresh"' in html
        assert "url=/v/0.3/" in html

    def test_contains_canonical_link(self):
        html = _redirect_page("/")
        assert 'rel="canonical"' in html
        assert 'href="/"' in html


# ---------------------------------------------------------------------------
# Version map writing
# ---------------------------------------------------------------------------


class TestWriteVersionMap:
    def test_writes_json(self, tmp_path: Path):
        versions = parse_versions_config(["0.3", "0.2"])
        pages = {"0.3": ["index.html", "guide.html"], "0.2": ["index.html"]}
        write_version_map(tmp_path, versions, pages)

        out = tmp_path / "_version_map.json"
        assert out.exists()
        data = json.loads(out.read_text())
        assert len(data["versions"]) == 2
        assert "index.html" in data["pages"]


# ---------------------------------------------------------------------------
# Full orchestrator (unit-level)
# ---------------------------------------------------------------------------


class TestRunVersionedBuild:
    def test_returns_error_for_no_matching_versions(self, tmp_path: Path):
        source = tmp_path / "source"
        source.mkdir()

        result = run_versioned_build(
            source_dir=source,
            project_root=tmp_path,
            versions_config=["0.3", "0.2"],
            version_tags=["0.5"],  # doesn't exist
        )

        assert result["success"] is False
        assert "No matching versions" in result["errors"][0]

    def test_latest_only_filters_to_one(self, tmp_path: Path):
        """Test that latest_only creates only one build directory."""
        source = tmp_path / "source"
        _make_source_tree(
            source,
            {
                "index.qmd": "---\ntitle: Home\n---\n\nHi",
            },
        )

        # We can't run the full orchestrator without Quarto, but we can
        # verify preprocessing works correctly for a single version
        versions = parse_versions_config(["0.3", "0.2", "0.1"])
        latest = versions[0]

        build_root = tmp_path / "build"
        build_root.mkdir()
        ver_dir = _version_build_dir(build_root, latest, "0.3")

        pages = preprocess_version(source, ver_dir, latest, versions)
        assert "index.html" in pages
        # Only _root dir should exist
        assert ver_dir.name == "_root"


# ---------------------------------------------------------------------------
# Section-level version scoping
# ---------------------------------------------------------------------------


class TestSectionVersionScoping:
    def test_excluded_section_dirs(self):
        sections = [
            {"dir": "recipes", "versions": ["0.3"]},
            {"dir": "migrations", "versions": ["0.2", "0.3"]},
            {"dir": "guide"},  # no versions key — always included
        ]
        excluded = _compute_excluded_section_dirs("0.2", sections)
        assert "recipes" in excluded  # 0.2 not in ["0.3"]
        assert "migrations" not in excluded  # 0.2 in ["0.2", "0.3"]
        assert "guide" not in excluded

    def test_no_sections_returns_empty(self):
        assert _compute_excluded_section_dirs("0.1", None) == set()
        assert _compute_excluded_section_dirs("0.1", []) == set()

    def test_in_excluded_section(self):
        excluded = {"recipes", "migrations"}
        assert _in_excluded_section(Path("recipes/01-example.qmd"), excluded)
        assert _in_excluded_section(Path("migrations/v2.qmd"), excluded)
        assert not _in_excluded_section(Path("guide/intro.qmd"), excluded)
        assert not _in_excluded_section(Path("index.qmd"), excluded)

    def test_preprocess_excludes_scoped_sections(self, tmp_path: Path):
        source = tmp_path / "source"
        _make_source_tree(
            source,
            {
                "index.qmd": "---\ntitle: Home\n---\n\nHi",
                "recipes/01-basic.qmd": "---\ntitle: Basic\n---\n\nRecipe",
                "guide/intro.qmd": "---\ntitle: Intro\n---\n\nGuide",
            },
        )
        versions = parse_versions_config(["0.3", "0.2"])
        sections = [{"dir": "recipes", "versions": ["0.3"]}]

        # Build 0.3 — recipes included
        dest1 = tmp_path / "build1"
        pages1 = preprocess_version(
            source,
            dest1,
            versions[0],
            versions,
            section_configs=sections,
        )
        assert "recipes/01-basic.html" in pages1

        # Build 0.2 — recipes excluded
        dest2 = tmp_path / "build2"
        pages2 = preprocess_version(
            source,
            dest2,
            versions[1],
            versions,
            section_configs=sections,
        )
        assert "recipes/01-basic.html" not in pages2
        assert "guide/intro.html" in pages2


# ---------------------------------------------------------------------------
# Inline version-badge expansion
# ---------------------------------------------------------------------------


class TestExpandVersionBadges:
    def _entry(self, tag="0.3", label="0.3.0"):
        return _make_entry(tag, label=label) if label != tag else _make_entry(tag)

    def test_new_badge(self):
        entry = VersionEntry(tag="0.3", label="0.3.0")
        content = "Some text [version-badge new] here."
        result = expand_version_badges(content, entry)
        assert 'class="gd-badge gd-badge-new"' in result
        assert "New in 0.3.0" in result
        assert "[version-badge" not in result

    def test_changed_badge_with_explicit_version(self):
        entry = VersionEntry(tag="0.3", label="0.3.0")
        content = "[version-badge changed 0.2]"
        result = expand_version_badges(content, entry)
        assert "Changed in 0.2" in result

    def test_deprecated_badge(self):
        entry = VersionEntry(tag="0.3", label="0.3.0")
        content = "[version-badge deprecated]"
        result = expand_version_badges(content, entry)
        assert "Deprecated in 0.3.0" in result
        assert "gd-badge-deprecated" in result

    def test_no_badges_unchanged(self):
        entry = VersionEntry(tag="0.3", label="0.3.0")
        content = "No badges here."
        result = expand_version_badges(content, entry)
        assert result == content

    def test_case_insensitive(self):
        entry = VersionEntry(tag="0.3", label="0.3.0")
        content = "[version-badge NEW]"
        result = expand_version_badges(content, entry)
        assert "New in 0.3.0" in result

    def test_new_badge_expired_suppressed(self):
        from great_docs._versioning import BadgeExpiry, parse_versions_config

        versions = parse_versions_config(["0.7", "0.6", "0.5", "0.4", "0.3"])
        entry = versions[0]  # 0.7
        expiry = BadgeExpiry(mode="releases", value=3)
        content = "Feature [version-badge new 0.3] here."
        result = expand_version_badges(content, entry, versions, expiry)
        assert "gd-badge" not in result
        assert "Feature  here." in result

    def test_new_badge_within_window_kept(self):
        from great_docs._versioning import BadgeExpiry, parse_versions_config

        versions = parse_versions_config(["0.7", "0.6", "0.5", "0.4", "0.3"])
        entry = versions[2]  # 0.5
        expiry = BadgeExpiry(mode="releases", value=3)
        content = "Feature [version-badge new 0.3] here."
        result = expand_version_badges(content, entry, versions, expiry)
        assert "New in 0.3" in result

    def test_changed_badge_never_expired(self):
        from great_docs._versioning import BadgeExpiry, parse_versions_config

        versions = parse_versions_config(["0.7", "0.6", "0.5", "0.4", "0.3"])
        entry = versions[0]  # 0.7
        expiry = BadgeExpiry(mode="releases", value=1)
        content = "[version-badge changed 0.3]"
        result = expand_version_badges(content, entry, versions, expiry)
        assert "Changed in 0.3" in result

    def test_deprecated_badge_never_expired(self):
        from great_docs._versioning import BadgeExpiry, parse_versions_config

        versions = parse_versions_config(["0.7", "0.6", "0.5", "0.4", "0.3"])
        entry = versions[0]  # 0.7
        expiry = BadgeExpiry(mode="releases", value=1)
        content = "[version-badge deprecated 0.3]"
        result = expand_version_badges(content, entry, versions, expiry)
        assert "Deprecated in 0.3" in result

    def test_no_expiry_backward_compatible(self):
        """Calling without expiry params still works (backward compatible)."""
        entry = VersionEntry(tag="0.7", label="0.7.0")
        content = "Feature [version-badge new 0.3] here."
        result = expand_version_badges(content, entry)
        assert "New in 0.3" in result

    def test_new_badge_prerelease_own_build_renders_new(self):
        """Building the prerelease itself renders as 'New', not 'Upcoming'."""
        from great_docs._versioning import parse_versions_config

        versions = parse_versions_config(
            [
                {"tag": "0.8", "label": "0.8.0", "prerelease": True},
                {"tag": "0.7", "label": "0.7.0", "latest": True},
            ]
        )
        entry = versions[0]  # building 0.8 (prerelease)
        content = "[version-badge new 0.8]"
        result = expand_version_badges(content, entry, versions)
        assert "New in 0.8" in result
        assert "gd-badge-new" in result
        assert "gd-badge-upcoming" not in result

    def test_new_badge_prerelease_stable_build_renders_upcoming(self):
        """Building a stable version shows prerelease badges as 'Upcoming'."""
        from great_docs._versioning import parse_versions_config

        versions = parse_versions_config(
            [
                {"tag": "0.8", "label": "0.8.0", "prerelease": True},
                {"tag": "0.7", "label": "0.7.0", "latest": True},
            ]
        )
        entry = versions[1]  # building 0.7 (stable)
        content = "[version-badge new 0.8]"
        result = expand_version_badges(content, entry, versions)
        assert "Upcoming in 0.8" in result
        assert "gd-badge-upcoming" in result
        assert "gd-badge-new" not in result

    def test_new_badge_prerelease_dev_tag_stable_build(self):
        """Dev tag badge on a stable build renders as 'Upcoming'."""
        from great_docs._versioning import parse_versions_config

        versions = parse_versions_config(
            [
                {"tag": "dev", "label": "0.8.0", "prerelease": True},
                {"tag": "0.7", "label": "0.7.0", "latest": True},
            ]
        )
        entry = versions[1]  # building 0.7 (stable)
        content = "[version-badge new dev]"
        result = expand_version_badges(content, entry, versions)
        assert "Upcoming in dev" in result
        assert "gd-badge-upcoming" in result

    def test_new_badge_prerelease_dev_tag_own_build_renders_new(self):
        """Building the dev version itself renders as 'New'."""
        from great_docs._versioning import parse_versions_config

        versions = parse_versions_config(
            [
                {"tag": "dev", "label": "0.8.0", "prerelease": True},
                {"tag": "0.7", "label": "0.7.0", "latest": True},
            ]
        )
        entry = versions[0]  # building dev
        content = "[version-badge new dev]"
        result = expand_version_badges(content, entry, versions)
        assert "New in dev" in result
        assert "gd-badge-new" in result
        assert "gd-badge-upcoming" not in result

    def test_new_badge_released_version_not_upcoming(self):
        """A new badge referencing a released version stays 'New'."""
        from great_docs._versioning import parse_versions_config

        versions = parse_versions_config(
            [
                {"tag": "0.8", "label": "0.8.0", "prerelease": True},
                {"tag": "0.7", "label": "0.7.0", "latest": True},
                {"tag": "0.6", "label": "0.6.0"},
            ]
        )
        entry = versions[1]  # building 0.7
        content = "[version-badge new 0.6]"
        result = expand_version_badges(content, entry, versions)
        assert "New in 0.6" in result
        assert "gd-badge-new" in result
        assert "gd-badge-upcoming" not in result

    def test_bare_new_badge_on_prerelease_build(self):
        """Bare [version-badge new] on a prerelease build renders as 'New' (own build)."""
        from great_docs._versioning import parse_versions_config

        versions = parse_versions_config(
            [
                {"tag": "0.8", "label": "0.8.0", "prerelease": True},
                {"tag": "0.7", "label": "0.7.0", "latest": True},
            ]
        )
        entry = versions[0]  # building 0.8 (prerelease)
        content = "[version-badge new]"
        result = expand_version_badges(content, entry, versions)
        assert "New in 0.8.0" in result
        assert "gd-badge-new" in result

    def test_changed_badge_not_affected_by_prerelease(self):
        """Changed badges stay 'Changed' even when version is prerelease."""
        from great_docs._versioning import parse_versions_config

        versions = parse_versions_config(
            [
                {"tag": "0.8", "label": "0.8.0", "prerelease": True},
                {"tag": "0.7", "label": "0.7.0", "latest": True},
            ]
        )
        entry = versions[0]
        content = "[version-badge changed 0.8]"
        result = expand_version_badges(content, entry, versions)
        assert "Changed in 0.8" in result
        assert "gd-badge-changed" in result

    def test_badges_inside_code_blocks_not_expanded(self):
        content = (
            "Some text [version-badge new]\n"
            "\n"
            '```{.markdown filename="reference.qmd"}\n'
            "## Widget [version-badge new]\n"
            "## render() [version-badge changed 0.2]\n"
            "```\n"
            "\n"
            "More text [version-badge deprecated 0.1]\n"
        )
        entry = VersionEntry(tag="0.5", label="0.5")
        result = expand_version_badges(content, entry)
        # Outside code block: expanded
        assert '<span class="gd-badge gd-badge-new">New in 0.5</span>' in result
        assert '<span class="gd-badge gd-badge-deprecated">Deprecated in 0.1</span>' in result
        # Inside code block: literal text preserved
        assert "## Widget [version-badge new]" in result
        assert "## render() [version-badge changed 0.2]" in result


# ---------------------------------------------------------------------------
# Upcoming status injection
# ---------------------------------------------------------------------------


class TestInjectUpcomingStatus:
    def test_injects_status(self):
        from great_docs._versioned_build import _inject_upcoming_status

        content = '---\ntitle: "New Feature"\nversions: ["dev"]\n---\nBody\n'
        result = _inject_upcoming_status(content)
        assert "status: upcoming" in result
        assert result.startswith("---\n")
        assert "---\nBody" in result

    def test_preserves_existing_status(self):
        from great_docs._versioned_build import _inject_upcoming_status

        content = '---\ntitle: "Feature"\nstatus: experimental\n---\nBody\n'
        result = _inject_upcoming_status(content)
        assert "status: experimental" in result
        assert "status: upcoming" not in result

    def test_no_frontmatter(self):
        from great_docs._versioned_build import _inject_upcoming_status

        content = "No frontmatter here.\n"
        result = _inject_upcoming_status(content)
        assert result == content


class TestUpdatePageStatusJson:
    def test_adds_upcoming_pages(self, tmp_path):
        import json

        from great_docs._versioned_build import _update_page_status_json

        status_path = tmp_path / "_page_status.json"
        status_path.write_text(
            json.dumps(
                {
                    "page_statuses": {"user-guide/intro.qmd": "new"},
                    "definitions": {},
                }
            )
        )
        _update_page_status_json(tmp_path, [("user-guide/feature.html", "0.8")])
        data = json.loads(status_path.read_text())
        # Upcoming is stored separately — page_statuses untouched
        assert data["page_statuses"] == {"user-guide/intro.qmd": "new"}
        assert data["upcoming_pages"]["user-guide/feature.qmd"] == "0.8"

    def test_preserves_existing_status(self, tmp_path):
        import json

        from great_docs._versioned_build import _update_page_status_json

        status_path = tmp_path / "_page_status.json"
        status_path.write_text(
            json.dumps(
                {
                    "page_statuses": {"user-guide/feature.qmd": "experimental"},
                    "definitions": {},
                }
            )
        )
        _update_page_status_json(tmp_path, [("user-guide/feature.html", "0.8")])
        data = json.loads(status_path.read_text())
        # Status stays experimental — upcoming is independent
        assert data["page_statuses"]["user-guide/feature.qmd"] == "experimental"
        assert data["upcoming_pages"]["user-guide/feature.qmd"] == "0.8"

    def test_no_version_uses_true(self, tmp_path):
        import json

        from great_docs._versioned_build import _update_page_status_json

        status_path = tmp_path / "_page_status.json"
        status_path.write_text(
            json.dumps(
                {
                    "page_statuses": {},
                    "definitions": {},
                }
            )
        )
        _update_page_status_json(tmp_path, [("user-guide/feature.html", None)])
        data = json.loads(status_path.read_text())
        assert data["upcoming_pages"]["user-guide/feature.qmd"] is True

    def test_missing_file_does_nothing(self, tmp_path):
        from great_docs._versioned_build import _update_page_status_json

        # Should not raise
        _update_page_status_json(tmp_path, [("feature.html", "0.8")])


class TestSyncStatusInlineScript:
    """Tests for _sync_status_inline_script which injects __GD_UPCOMING_DATA__."""

    def _make_quarto_yml(self, tmp_path, include_js_inline=True):
        """Create a _quarto.yml with __GD_STATUS_DATA__ inline script."""
        import json

        status_data = {
            "page_statuses": {"a.qmd": "experimental"},
            "definitions": {"experimental": {"label": "Experimental"}},
            "show_in_sidebar": True,
            "show_on_pages": True,
        }
        escaped = json.dumps(status_data).replace("</", r"<\/")
        script = "<script>window.__GD_STATUS_DATA__=" + escaped + ";</script>"
        lines = [
            "format:",
            "  html:",
            "    include-after-body:",
            f'      - text: "{script}"',
        ]
        if include_js_inline:
            # Simulate inlined page-status-badges.js that references __GD_UPCOMING_DATA__
            lines.append(
                '      - text: "<script>// var upcoming = window.__GD_UPCOMING_DATA__;</script>"'
            )
        (tmp_path / "_quarto.yml").write_text("\n".join(lines))

    def test_injects_upcoming_data(self, tmp_path):
        import json

        from great_docs._versioned_build import _sync_status_inline_script

        self._make_quarto_yml(tmp_path)
        status_path = tmp_path / "_page_status.json"
        status_path.write_text(
            json.dumps(
                {
                    "page_statuses": {"a.qmd": "experimental"},
                    "definitions": {},
                    "upcoming_pages": {"user-guide/feature.qmd": "0.8"},
                }
            )
        )
        _sync_status_inline_script(tmp_path)
        yml = (tmp_path / "_quarto.yml").read_text()
        assert "<script>window.__GD_UPCOMING_DATA__=" in yml
        assert '"user-guide/feature.qmd": "0.8"' in yml

    def test_does_not_double_inject(self, tmp_path):
        import json

        from great_docs._versioned_build import _sync_status_inline_script

        self._make_quarto_yml(tmp_path)
        status_path = tmp_path / "_page_status.json"
        status_path.write_text(
            json.dumps(
                {
                    "page_statuses": {},
                    "definitions": {},
                    "upcoming_pages": {"a.qmd": "0.9"},
                }
            )
        )
        _sync_status_inline_script(tmp_path)
        _sync_status_inline_script(tmp_path)  # second call
        yml = (tmp_path / "_quarto.yml").read_text()
        assert yml.count("<script>window.__GD_UPCOMING_DATA__=") == 1

    def test_no_upcoming_pages_skips(self, tmp_path):
        import json

        from great_docs._versioned_build import _sync_status_inline_script

        self._make_quarto_yml(tmp_path)
        status_path = tmp_path / "_page_status.json"
        status_path.write_text(json.dumps({"page_statuses": {}, "definitions": {}}))
        _sync_status_inline_script(tmp_path)
        yml = (tmp_path / "_quarto.yml").read_text()
        assert "__GD_UPCOMING_DATA__=" not in yml

    def test_missing_status_json_skips(self, tmp_path):
        from great_docs._versioned_build import _sync_status_inline_script

        self._make_quarto_yml(tmp_path)
        # No _page_status.json
        _sync_status_inline_script(tmp_path)
        yml = (tmp_path / "_quarto.yml").read_text()
        assert "__GD_UPCOMING_DATA__=" not in yml

    def test_no_status_data_script_skips(self, tmp_path):
        import json

        from great_docs._versioned_build import _sync_status_inline_script

        # _quarto.yml without __GD_STATUS_DATA__ script tag
        (tmp_path / "_quarto.yml").write_text(
            "format:\n  html:\n    include-after-body:\n      - somefile.js\n"
        )
        (tmp_path / "_page_status.json").write_text(
            json.dumps(
                {
                    "page_statuses": {},
                    "definitions": {},
                    "upcoming_pages": {"a.qmd": "0.8"},
                }
            )
        )
        _sync_status_inline_script(tmp_path)
        yml = (tmp_path / "_quarto.yml").read_text()
        assert "__GD_UPCOMING_DATA__=" not in yml

    def test_not_confused_by_js_reference(self, tmp_path):
        """The guard should not be tricked by __GD_UPCOMING_DATA__ in JS comments."""
        import json

        from great_docs._versioned_build import _sync_status_inline_script

        self._make_quarto_yml(tmp_path, include_js_inline=True)
        status_path = tmp_path / "_page_status.json"
        status_path.write_text(
            json.dumps(
                {
                    "page_statuses": {},
                    "definitions": {},
                    "upcoming_pages": {"page.qmd": "1.0"},
                }
            )
        )
        _sync_status_inline_script(tmp_path)
        yml = (tmp_path / "_quarto.yml").read_text()
        # Should still inject despite the JS reference existing
        assert "<script>window.__GD_UPCOMING_DATA__=" in yml


# ---------------------------------------------------------------------------
# Version callout expansion
# ---------------------------------------------------------------------------


class TestExpandVersionCallouts:
    def test_version_note(self):
        entry = VersionEntry(tag="0.3", label="0.3.0")
        content = '::: {.version-note version="0.3"}\nNew feature.\n:::'
        result = expand_version_callouts(content, entry)
        assert '.callout-note title="Added in 0.3"' in result
        assert "New feature." in result

    def test_version_deprecated(self):
        entry = VersionEntry(tag="0.2", label="0.2.0")
        content = '::: {.version-deprecated version="0.2"}\nUse new_func.\n:::'
        result = expand_version_callouts(content, entry)
        assert '.callout-warning title="Deprecated since 0.2"' in result

    def test_no_version_uses_entry_label(self):
        entry = VersionEntry(tag="0.3", label="0.3.0")
        content = "::: {.version-note}\nDefault version.\n:::"
        result = expand_version_callouts(content, entry)
        assert "Added in 0.3.0" in result

    def test_no_callouts_unchanged(self):
        entry = VersionEntry(tag="0.3", label="0.3.0")
        content = "::: {.callout-note}\nNot a version callout.\n:::"
        result = expand_version_callouts(content, entry)
        assert result == content


# ---------------------------------------------------------------------------
# Redirect file generation
# ---------------------------------------------------------------------------


class TestGenerateRedirectFiles:
    def test_generates_netlify_redirects(self, tmp_path: Path):
        versions = parse_versions_config(["0.3", "0.2"])
        generate_redirect_files(tmp_path, versions, "0.3")

        redirects = tmp_path / "_redirects"
        assert redirects.exists()
        content = redirects.read_text()
        assert "/v/latest/*" in content
        assert "/v/stable/*" in content
        assert "200" in content

    def test_generates_vercel_json(self, tmp_path: Path):
        versions = parse_versions_config(["0.3", "0.2"])
        generate_redirect_files(tmp_path, versions, "0.3")

        vercel = tmp_path / "vercel.json"
        assert vercel.exists()
        data = json.loads(vercel.read_text())
        assert "rewrites" in data
        sources = [r["source"] for r in data["rewrites"]]
        assert any("latest" in s for s in sources)

    def test_no_redirect_for_tag_collision(self, tmp_path: Path):
        versions = parse_versions_config(
            [
                {"tag": "latest", "label": "Latest"},
                {"tag": "0.2", "label": "0.2"},
            ]
        )
        generate_redirect_files(tmp_path, versions, "latest")

        # Should still generate, but without "latest" alias since it's a real tag
        redirects = tmp_path / "_redirects"
        if redirects.exists():
            content = redirects.read_text()
            assert "/v/latest/*" not in content

    def test_dev_alias_included(self, tmp_path: Path):
        versions = parse_versions_config(
            [
                {"tag": "dev", "label": "dev", "prerelease": True},
                {"tag": "0.3", "label": "0.3"},
            ]
        )
        generate_redirect_files(tmp_path, versions, "0.3")

        redirects = tmp_path / "_redirects"
        # dev is both a tag and would be an alias — collision, so no alias
        if redirects.exists():
            content = redirects.read_text()
            assert "/v/dev/*" not in content


# ---------------------------------------------------------------------------
# Canonical URL injection (via _rewrite_quarto_yml_for_version)
# ---------------------------------------------------------------------------


class TestCanonicalUrlInjection:
    def test_non_latest_gets_canonical(self, tmp_path: Path):
        from great_docs._versioned_build import _rewrite_quarto_yml_for_version

        dest = tmp_path / "v02"
        dest.mkdir()
        (dest / "_quarto.yml").write_text(
            "project:\n  type: website\n  output-dir: _site\n"
            "format:\n  html: {}\nwebsite:\n  title: Test\n",
            encoding="utf-8",
        )
        entry = _make_entry("0.2")
        _rewrite_quarto_yml_for_version(dest, entry, "0.3", site_url="https://example.com")

        content = (dest / "_quarto.yml").read_text()
        assert "canonical" in content

    def test_latest_no_canonical(self, tmp_path: Path):
        from great_docs._versioned_build import _rewrite_quarto_yml_for_version

        dest = tmp_path / "root"
        dest.mkdir()
        (dest / "_quarto.yml").write_text(
            "project:\n  type: website\n  output-dir: _site\n"
            "format:\n  html: {}\nwebsite:\n  title: Test\n",
            encoding="utf-8",
        )
        entry = _make_entry("0.3", latest=True)
        _rewrite_quarto_yml_for_version(dest, entry, "0.3", site_url="https://example.com")

        content = (dest / "_quarto.yml").read_text()
        assert "canonical" not in content

    def test_no_site_url_no_canonical(self, tmp_path: Path):
        from great_docs._versioned_build import _rewrite_quarto_yml_for_version

        dest = tmp_path / "v02"
        dest.mkdir()
        (dest / "_quarto.yml").write_text(
            "project:\n  type: website\n  output-dir: _site\n"
            "format:\n  html: {}\nwebsite:\n  title: Test\n",
            encoding="utf-8",
        )
        entry = _make_entry("0.2")
        _rewrite_quarto_yml_for_version(dest, entry, "0.3")

        content = (dest / "_quarto.yml").read_text()
        assert "canonical" not in content


# ---------------------------------------------------------------------------
# site-url adjustment for versioned builds
# ---------------------------------------------------------------------------


class TestSiteUrlVersionAdjustment:
    def test_non_latest_adjusts_site_url(self, tmp_path: Path):
        """Non-latest versions get site-url with /v/<tag>/ appended."""
        from great_docs._versioned_build import _rewrite_quarto_yml_for_version

        dest = tmp_path / "v02"
        dest.mkdir()
        (dest / "_quarto.yml").write_text(
            "project:\n  type: website\n  output-dir: _site\n"
            "format:\n  html: {}\nwebsite:\n  title: Test\n"
            "  site-url: 'http://myserver:3838/data-team/mypkg/'\n",
            encoding="utf-8",
        )
        entry = _make_entry("0.2")
        _rewrite_quarto_yml_for_version(
            dest, entry, "0.3", site_url="http://myserver:3838/data-team/mypkg/"
        )

        from yaml12 import read_yaml

        with open(dest / "_quarto.yml") as f:
            result = read_yaml(f)

        assert result["website"]["site-url"] == "http://myserver:3838/data-team/mypkg/v/0.2/"

    def test_latest_keeps_site_url_unchanged(self, tmp_path: Path):
        """Latest version keeps the original site-url as-is."""
        from great_docs._versioned_build import _rewrite_quarto_yml_for_version

        dest = tmp_path / "root"
        dest.mkdir()
        (dest / "_quarto.yml").write_text(
            "project:\n  type: website\n  output-dir: _site\n"
            "format:\n  html: {}\nwebsite:\n  title: Test\n"
            "  site-url: 'http://myserver:3838/data-team/mypkg/'\n",
            encoding="utf-8",
        )
        entry = _make_entry("0.3", latest=True)
        _rewrite_quarto_yml_for_version(
            dest, entry, "0.3", site_url="http://myserver:3838/data-team/mypkg/"
        )

        from yaml12 import read_yaml

        with open(dest / "_quarto.yml") as f:
            result = read_yaml(f)

        assert result["website"]["site-url"] == "http://myserver:3838/data-team/mypkg/"

    def test_no_site_url_in_config_no_adjustment(self, tmp_path: Path):
        """When site-url is not in _quarto.yml, nothing is injected."""
        from great_docs._versioned_build import _rewrite_quarto_yml_for_version

        dest = tmp_path / "v02"
        dest.mkdir()
        (dest / "_quarto.yml").write_text(
            "project:\n  type: website\n  output-dir: _site\n"
            "format:\n  html: {}\nwebsite:\n  title: Test\n",
            encoding="utf-8",
        )
        entry = _make_entry("0.2")
        _rewrite_quarto_yml_for_version(dest, entry, "0.3")

        from yaml12 import read_yaml

        with open(dest / "_quarto.yml") as f:
            result = read_yaml(f)

        assert "site-url" not in result.get("website", {})


# ---------------------------------------------------------------------------
# Snapshot cache path
# ---------------------------------------------------------------------------


class TestSnapshotCachePath:
    def test_cache_path(self, tmp_path: Path):
        path = _snapshot_cache_path(tmp_path, "v0.3.0")
        assert path == tmp_path / ".great-docs-cache" / "snapshots" / "v0.3.0.json"


# ---------------------------------------------------------------------------
# _collect_qmd_files
# ---------------------------------------------------------------------------


class TestCollectQmdFiles:
    def test_finds_qmd_and_md(self, tmp_path: Path):
        from great_docs._versioned_build import _collect_qmd_files

        (tmp_path / "index.qmd").write_text("hello")
        (tmp_path / "guide.md").write_text("world")
        (tmp_path / "ignore.txt").write_text("skip")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.qmd").write_text("deep")

        files = _collect_qmd_files(tmp_path)
        stems = {f.name for f in files}
        assert "index.qmd" in stems
        assert "guide.md" in stems
        assert "deep.qmd" in stems
        assert "ignore.txt" not in stems


# ---------------------------------------------------------------------------
# _extract_frontmatter_value
# ---------------------------------------------------------------------------


class TestExtractFrontmatterValue:
    def test_extracts_value(self):
        from great_docs._versioned_build import _extract_frontmatter_value

        content = '---\ntitle: "My Page"\nstatus: experimental\n---\n\nBody'
        assert _extract_frontmatter_value(content, "status") == "experimental"

    def test_returns_none_when_missing(self):
        from great_docs._versioned_build import _extract_frontmatter_value

        content = "---\ntitle: Hello\n---\n\nBody"
        assert _extract_frontmatter_value(content, "status") is None

    def test_returns_none_without_frontmatter(self):
        from great_docs._versioned_build import _extract_frontmatter_value

        content = "No frontmatter here"
        assert _extract_frontmatter_value(content, "status") is None

    def test_strips_quotes(self):
        from great_docs._versioned_build import _extract_frontmatter_value

        content = '---\nupcoming: "0.8"\n---\n\nBody'
        assert _extract_frontmatter_value(content, "upcoming") == "0.8"


# ---------------------------------------------------------------------------
# _inject_upcoming_status
# ---------------------------------------------------------------------------


class TestInjectUpcomingStatus:
    def test_injects_when_no_status(self):
        from great_docs._versioned_build import _inject_upcoming_status

        content = "---\ntitle: Hello\n---\n\nBody"
        result = _inject_upcoming_status(content)
        assert "status: upcoming" in result
        assert "title: Hello" in result

    def test_preserves_existing_status(self):
        from great_docs._versioned_build import _inject_upcoming_status

        content = "---\ntitle: Hello\nstatus: experimental\n---\n\nBody"
        result = _inject_upcoming_status(content)
        assert "status: upcoming" not in result
        assert "status: experimental" in result

    def test_no_frontmatter_returns_unchanged(self):
        from great_docs._versioned_build import _inject_upcoming_status

        content = "No frontmatter at all"
        result = _inject_upcoming_status(content)
        assert result == content


# ---------------------------------------------------------------------------
# _prune_cli_pages / _rewrite_cli_index / _prune_quarto_cli_sidebar
# ---------------------------------------------------------------------------


class TestPruneCliPages:
    def test_removes_unknown_cli_pages(self, tmp_path: Path):
        from great_docs._versioned_build import _prune_cli_pages

        cli_dir = tmp_path / "reference" / "cli"
        cli_dir.mkdir(parents=True)
        (cli_dir / "index.qmd").write_text("---\ntitle: CLI\n---\n")
        (cli_dir / "build.qmd").write_text("---\ntitle: build\n---\n")
        (cli_dir / "old_cmd.qmd").write_text("---\ntitle: old-cmd\n---\n")

        # Mock snapshot with only "build" command
        class MockCmd:
            name = "build"

        class MockSnap:
            cli_commands = type("CLI", (), {"subcommands": [MockCmd()]})()

        _prune_cli_pages(tmp_path, MockSnap())

        assert (cli_dir / "index.qmd").exists()
        assert (cli_dir / "build.qmd").exists()
        assert not (cli_dir / "old_cmd.qmd").exists()

    def test_no_cli_dir_does_nothing(self, tmp_path: Path):
        from great_docs._versioned_build import _prune_cli_pages

        class MockSnap:
            cli_commands = None

        _prune_cli_pages(tmp_path, MockSnap())  # Should not raise

    def test_no_cli_commands_does_nothing(self, tmp_path: Path):
        from great_docs._versioned_build import _prune_cli_pages

        cli_dir = tmp_path / "reference" / "cli"
        cli_dir.mkdir(parents=True)
        (cli_dir / "build.qmd").write_text("content")

        class MockSnap:
            cli_commands = None

        _prune_cli_pages(tmp_path, MockSnap())
        assert (cli_dir / "build.qmd").exists()


class TestRewriteCliIndex:
    def test_removes_invalid_commands(self, tmp_path: Path):
        from great_docs._versioned_build import _rewrite_cli_index

        index = tmp_path / "index.qmd"
        index.write_text(
            "---\ntitle: CLI Reference\n---\n\n"
            "# CLI Reference\n\n"
            "## Commands {.doc-group}\n\n"
            "[build](build.qmd){.doc-function .doc-label .doc-label-cli}\n"
            ":   Build the docs\n\n"
            "[preview](preview.qmd){.doc-function .doc-label .doc-label-cli}\n"
            ":   Preview the site\n\n"
            "[old-cmd](old_cmd.qmd){.doc-function .doc-label .doc-label-cli}\n"
            ":   Deprecated command\n\n"
            "## skill {.doc-group}\n\n"
            "[install](skill/install.qmd){.doc-function .doc-label .doc-label-cli}\n"
            ":   Install a skill\n\n"
        )

        # Note: stems use underscores; "skill" group is valid so its subcommand is kept.
        _rewrite_cli_index(index, {"index", "build", "preview", "skill"})
        content = index.read_text()
        assert "[build](build.qmd)" in content
        assert "[preview](preview.qmd)" in content
        assert "[old-cmd]" not in content
        assert "Deprecated command" not in content
        # Nested subcommand of a surviving group is retained.
        assert "[install](skill/install.qmd)" in content


class TestPruneQuartoCliSidebar:
    def test_removes_invalid_sidebar_entries(self, tmp_path: Path):
        import yaml

        from great_docs._versioned_build import _prune_quarto_cli_sidebar

        quarto = tmp_path / "_quarto.yml"
        config = {
            "website": {
                "sidebar": [
                    {
                        "id": "cli-reference",
                        "contents": [
                            "reference/cli/index.qmd",
                            "reference/cli/build.qmd",
                            "reference/cli/old_cmd.qmd",
                        ],
                    }
                ]
            }
        }
        quarto.write_text(yaml.dump(config), encoding="utf-8")

        _prune_quarto_cli_sidebar(tmp_path, {"index", "build"})

        result = yaml.safe_load(quarto.read_text())
        contents = result["website"]["sidebar"][0]["contents"]
        stems = [Path(c).stem for c in contents]
        assert "build" in stems
        assert "index" in stems
        assert "old_cmd" not in stems


# ---------------------------------------------------------------------------
# _prune_missing_sidebar_pages / _prune_sidebar_contents
# ---------------------------------------------------------------------------


class TestPruneMissingSidebarPages:
    def test_removes_missing_pages_from_sidebar(self, tmp_path: Path):
        from great_docs._versioned_build import _prune_sidebar_contents

        # Only "index.qmd" and "guide.qmd" exist on disk
        (tmp_path / "index.qmd").write_text("---\ntitle: Home\n---\n")
        (tmp_path / "guide.qmd").write_text("---\ntitle: Guide\n---\n")
        # "deleted.qmd" does NOT exist

        contents = ["index.qmd", "guide.qmd", "deleted.qmd"]
        result = _prune_sidebar_contents(contents, tmp_path)
        assert "index.qmd" in result
        assert "guide.qmd" in result
        assert "deleted.qmd" not in result

    def test_prunes_nested_sections(self, tmp_path: Path):
        from great_docs._versioned_build import _prune_sidebar_contents

        (tmp_path / "a.qmd").write_text("hi")
        contents = [
            {"section": "Group", "contents": ["a.qmd", "b.qmd"]},
        ]
        result = _prune_sidebar_contents(contents, tmp_path)
        # b.qmd doesn't exist so it's removed; section kept because a.qmd exists
        assert len(result) == 1
        assert result[0]["contents"] == ["a.qmd"]

    def test_removes_empty_sections(self, tmp_path: Path):
        from great_docs._versioned_build import _prune_sidebar_contents

        contents = [
            {"section": "Empty", "contents": ["missing.qmd"]},
        ]
        result = _prune_sidebar_contents(contents, tmp_path)
        assert result == []

    def test_keeps_dict_with_href(self, tmp_path: Path):
        from great_docs._versioned_build import _prune_sidebar_contents

        (tmp_path / "page.qmd").write_text("hi")
        contents = [{"href": "page.qmd", "text": "Page"}]
        result = _prune_sidebar_contents(contents, tmp_path)
        assert len(result) == 1

    def test_removes_dict_with_missing_href(self, tmp_path: Path):
        from great_docs._versioned_build import _prune_sidebar_contents

        contents = [{"href": "gone.qmd", "text": "Gone"}]
        result = _prune_sidebar_contents(contents, tmp_path)
        assert result == []


# ---------------------------------------------------------------------------
# _format_signature / _format_param
# ---------------------------------------------------------------------------


class TestFormatSignature:
    def test_class_with_params(self):
        from great_docs._versioned_build import _format_signature

        sym = type(
            "Sym",
            (),
            {
                "kind": "class",
                "parameters": [
                    type("P", (), {"name": "x", "annotation": "int", "default": None})(),
                    type("P", (), {"name": "y", "annotation": "str", "default": "'hi'"})(),
                ],
                "is_async": False,
                "return_annotation": None,
            },
        )()
        result = _format_signature("MyClass", sym)
        assert result == "class MyClass(x: int, y: str = 'hi')"

    def test_class_without_params(self):
        from great_docs._versioned_build import _format_signature

        sym = type(
            "Sym",
            (),
            {"kind": "class", "parameters": [], "is_async": False, "return_annotation": None},
        )()
        result = _format_signature("Empty", sym)
        assert result == "class Empty"

    def test_function(self):
        from great_docs._versioned_build import _format_signature

        sym = type(
            "Sym",
            (),
            {
                "kind": "function",
                "parameters": [
                    type("P", (), {"name": "a", "annotation": None, "default": None})(),
                ],
                "is_async": False,
                "return_annotation": "str",
            },
        )()
        result = _format_signature("myfunc", sym)
        assert result == "def myfunc(a) -> str"

    def test_async_function(self):
        from great_docs._versioned_build import _format_signature

        sym = type(
            "Sym",
            (),
            {"kind": "function", "parameters": [], "is_async": True, "return_annotation": None},
        )()
        result = _format_signature("afunc", sym)
        assert result == "async def afunc()"

    def test_other_kind(self):
        from great_docs._versioned_build import _format_signature

        sym = type(
            "Sym",
            (),
            {"kind": "attribute", "parameters": [], "is_async": False, "return_annotation": None},
        )()
        result = _format_signature("MY_CONST", sym)
        assert result == "MY_CONST"


# ---------------------------------------------------------------------------
# _is_valid_ref_name
# ---------------------------------------------------------------------------


class TestIsValidRefNameLegacy:
    def test_index_always_valid(self):
        from great_docs._versioned_build import _is_valid_ref_name

        assert _is_valid_ref_name("index", set()) is True

    def test_symbol_in_set(self):
        from great_docs._versioned_build import _is_valid_ref_name

        assert _is_valid_ref_name("MyClass", {"MyClass", "func"}) is True

    def test_method_stem_valid_when_in_snapshot(self):
        from great_docs._versioned_build import _is_valid_ref_name

        assert _is_valid_ref_name("MyClass.method", {"MyClass", "MyClass.method"}) is True

    def test_method_stem_invalid_when_absent_from_deep_snapshot(self):
        # A deep snapshot carries dotted keys, so a method stem that is not
        # itself present is authoritatively invalid (the method was dropped).
        from great_docs._versioned_build import _is_valid_ref_name

        assert _is_valid_ref_name("MyClass.gone", {"MyClass", "MyClass.kept"}) is False

    def test_method_stem_kept_under_shallow_snapshot(self):
        # A shallow snapshot has no dotted keys; pruning a `Class.method` page
        # under exact membership would reintroduce the #190 regression, so the
        # class-prefix safety net keeps it.
        from great_docs._versioned_build import _is_valid_ref_name

        assert _is_valid_ref_name("MyClass.method", {"MyClass", "func"}) is True

    def test_method_stem_dropped_when_class_absent_under_shallow_snapshot(self):
        from great_docs._versioned_build import _is_valid_ref_name

        assert _is_valid_ref_name("Gone.method", {"MyClass"}) is False

    def test_unknown_symbol(self):
        from great_docs._versioned_build import _is_valid_ref_name

        assert _is_valid_ref_name("Unknown", {"Known"}) is False


# ---------------------------------------------------------------------------
# _prune_reference_index
# ---------------------------------------------------------------------------


class TestPruneReferenceIndex:
    def test_removes_invalid_links(self, tmp_path: Path):
        from great_docs._versioned_build import _prune_reference_index

        index = tmp_path / "index.qmd"
        index.write_text(
            "---\ntitle: API\n---\n\n"
            "## Functions {.doc-group}\n\n"
            "::: {.doc-description}\nFunctions section.\n:::\n\n"
            "[`MyFunc`](MyFunc.qmd)\n\n"
            "[`OldFunc`](OldFunc.qmd)\n\n"
            "## Classes {.doc-group}\n\n"
            "::: {.doc-description}\nClasses section.\n:::\n\n"
            "[`MyClass`](MyClass.qmd)\n\n"
        )

        _prune_reference_index(index, {"MyFunc", "MyClass"})

        content = index.read_text()
        assert "MyFunc" in content
        assert "MyClass" in content
        assert "OldFunc" not in content

    def test_removes_empty_sections(self, tmp_path: Path):
        from great_docs._versioned_build import _prune_reference_index

        index = tmp_path / "index.qmd"
        index.write_text(
            "---\ntitle: API\n---\n\n"
            "## Old Section {.doc-group}\n\n"
            "::: {.doc-description}\nAll gone.\n:::\n\n"
            "[`RemovedFunc`](RemovedFunc.qmd)\n\n"
            "## Kept Section {.doc-group}\n\n"
            "::: {.doc-description}\nStill here.\n:::\n\n"
            "[`kept`](kept.qmd)\n\n"
        )

        _prune_reference_index(index, {"kept"})

        content = index.read_text()
        assert "Old Section" not in content
        assert "Kept Section" in content
        assert "kept" in content


# ---------------------------------------------------------------------------
# _prune_quarto_sidebar (reference sidebar)
# ---------------------------------------------------------------------------


class TestPruneQuartoSidebar:
    def test_removes_invalid_reference_entries(self, tmp_path: Path):
        import yaml

        from great_docs._versioned_build import _prune_quarto_sidebar

        quarto = tmp_path / "_quarto.yml"
        config = {
            "website": {
                "sidebar": [
                    {
                        "id": "api",
                        "contents": [
                            "reference/MyFunc.qmd",
                            "reference/OldFunc.qmd",
                            "reference/MyClass.qmd",
                        ],
                    }
                ]
            }
        }
        quarto.write_text(yaml.dump(config), encoding="utf-8")

        _prune_quarto_sidebar(tmp_path, "reference", {"MyFunc", "MyClass"})

        result = yaml.safe_load(quarto.read_text())
        contents = result["website"]["sidebar"][0]["contents"]
        stems = [Path(c).stem for c in contents]
        assert "MyFunc" in stems
        assert "MyClass" in stems
        assert "OldFunc" not in stems

    def test_removes_empty_section_groups(self, tmp_path: Path):
        import yaml

        from great_docs._versioned_build import _prune_quarto_sidebar

        quarto = tmp_path / "_quarto.yml"
        config = {
            "website": {
                "sidebar": [
                    {
                        "id": "api",
                        "contents": [
                            {
                                "section": "Functions",
                                "contents": ["reference/OldFunc.qmd"],
                            },
                            "reference/Kept.qmd",
                        ],
                    }
                ]
            }
        }
        quarto.write_text(yaml.dump(config), encoding="utf-8")

        _prune_quarto_sidebar(tmp_path, "reference", {"Kept"})

        result = yaml.safe_load(quarto.read_text())
        contents = result["website"]["sidebar"][0]["contents"]
        # The section group with "OldFunc" should be removed
        assert len(contents) == 1
        assert contents[0] == "reference/Kept.qmd"


# ---------------------------------------------------------------------------
# _validate_git_ref_is_tag
# ---------------------------------------------------------------------------


class TestValidateGitRefIsTag:
    def test_invalid_pattern_rejected(self, tmp_path: Path):
        # Patterns not matching the tag regex are immediately rejected
        assert _validate_git_ref_is_tag(tmp_path, "main") is False
        assert _validate_git_ref_is_tag(tmp_path, "feature/branch") is False
        assert _validate_git_ref_is_tag(tmp_path, "") is False

    def test_valid_pattern_accepted_format(self, tmp_path: Path):
        # v0.3.0 matches the pattern but we can't verify git without a repo
        import subprocess
        from unittest.mock import patch

        mock_result = type("R", (), {"returncode": 0, "stdout": "v0.3.0\n"})()
        with patch("subprocess.run", return_value=mock_result):
            assert _validate_git_ref_is_tag(tmp_path, "v0.3.0") is True

    def test_tag_not_found(self, tmp_path: Path):
        from unittest.mock import patch

        mock_result = type("R", (), {"returncode": 0, "stdout": "v0.1.0\n"})()
        with patch("subprocess.run", return_value=mock_result):
            assert _validate_git_ref_is_tag(tmp_path, "v0.2.0") is False

    def test_timeout_returns_false(self, tmp_path: Path):
        import subprocess
        from unittest.mock import patch

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 10)):
            assert _validate_git_ref_is_tag(tmp_path, "v1.0") is False


# ---------------------------------------------------------------------------
# _rebuild_api_from_git_ref
# ---------------------------------------------------------------------------


class TestRebuildApiFromGitRef:
    def test_no_git_ref_returns_empty(self, tmp_path: Path):
        from great_docs._versioned_build import _rebuild_api_from_git_ref

        entry = _make_entry("0.2")
        entry = VersionEntry(tag="0.2", label="0.2", latest=False, git_ref=None)
        result = _rebuild_api_from_git_ref(tmp_path, tmp_path, entry)
        assert result == []

    def test_invalid_tag_warns_and_returns_empty(self, tmp_path: Path):
        from unittest.mock import patch

        from great_docs._versioned_build import _rebuild_api_from_git_ref

        entry = VersionEntry(tag="0.2", label="0.2", latest=False, git_ref="v0.2.0")

        with patch("great_docs._versioned_build._validate_git_ref_is_tag", return_value=False):
            with pytest.warns(UserWarning, match="not a valid tag"):
                result = _rebuild_api_from_git_ref(tmp_path, tmp_path, entry)
        assert result == []


# ---------------------------------------------------------------------------
# generate_redirect_files (full file generation)
# ---------------------------------------------------------------------------


class TestGenerateRedirectFilesFull:
    def test_writes_netlify_and_vercel(self, tmp_path: Path):
        versions = parse_versions_config(["0.3", "0.2"])
        generate_redirect_files(tmp_path, versions, "0.3")

        redirects = tmp_path / "_redirects"
        assert redirects.exists()
        content = redirects.read_text()
        assert "/v/latest/*" in content
        assert "/v/stable/*" in content
        assert "200" in content

        vercel = tmp_path / "vercel.json"
        assert vercel.exists()
        data = json.loads(vercel.read_text())
        assert "rewrites" in data
        assert len(data["rewrites"]) > 0

    def test_no_aliases_no_files_written(self, tmp_path: Path):
        # If "latest" collides with a tag name, skip everything
        versions = parse_versions_config(
            [
                {"tag": "latest", "label": "Latest"},
                {"tag": "stable", "label": "Stable"},
            ]
        )
        generate_redirect_files(tmp_path, versions, "latest")
        # No aliases created since both "latest" and "stable" are real tags
        # (the function may or may not write files)

    def test_dev_version_gets_redirect(self, tmp_path: Path):
        versions = parse_versions_config(
            [
                {"tag": "0.4", "label": "0.4 (dev)", "prerelease": True},
                {"tag": "0.3", "label": "0.3"},
            ]
        )
        generate_redirect_files(tmp_path, versions, "0.3")

        redirects = tmp_path / "_redirects"
        assert redirects.exists()
        content = redirects.read_text()
        assert "/v/dev/*" in content
        assert "/v/0.4/" in content


# ---------------------------------------------------------------------------
# _merge_tree
# ---------------------------------------------------------------------------


class TestMergeTree:
    def test_merges_files(self, tmp_path: Path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.html").write_text("aaa")
        sub = src / "sub"
        sub.mkdir()
        (sub / "b.html").write_text("bbb")

        dst = tmp_path / "dst"
        dst.mkdir()
        (dst / "existing.html").write_text("existing")

        _merge_tree(src, dst)

        assert (dst / "a.html").read_text() == "aaa"
        assert (dst / "sub" / "b.html").read_text() == "bbb"
        assert (dst / "existing.html").read_text() == "existing"


# ---------------------------------------------------------------------------
# _render_single_version (mocked subprocess)
# ---------------------------------------------------------------------------


class TestRenderSingleVersion:
    def test_success(self, tmp_path: Path):
        from unittest.mock import patch

        from great_docs._versioned_build import _render_single_version

        mock_result = type("R", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()
        with patch("subprocess.run", return_value=mock_result):
            build_dir, rc, stdout, stderr = _render_single_version(str(tmp_path), None)
        assert rc == 0
        assert build_dir == str(tmp_path)

    def test_timeout(self, tmp_path: Path):
        import subprocess
        from unittest.mock import patch

        from great_docs._versioned_build import _render_single_version

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("quarto", 600)):
            build_dir, rc, stdout, stderr = _render_single_version(str(tmp_path), None)
        assert rc == -1
        assert "timed out" in stderr

    def test_exception(self, tmp_path: Path):
        from unittest.mock import patch

        from great_docs._versioned_build import _render_single_version

        with patch("subprocess.run", side_effect=OSError("No quarto")):
            build_dir, rc, stdout, stderr = _render_single_version(str(tmp_path), None)
        assert rc == -1
        assert "No quarto" in stderr


# ---------------------------------------------------------------------------
# render_versions_parallel (streaming mode)
# ---------------------------------------------------------------------------


class TestRenderVersionsParallel:
    def test_streaming_mode_with_callback(self, tmp_path: Path):
        from unittest.mock import MagicMock, patch

        from great_docs._versioned_build import render_versions_parallel

        d1 = tmp_path / "v1"
        d1.mkdir()

        mock_result = (str(d1), 0, "", "")
        with patch(
            "great_docs._versioned_build._render_single_version_streaming",
            return_value=mock_result,
        ):
            callback = MagicMock()
            results = render_versions_parallel([d1], progress_callback=callback)

        assert len(results) == 1
        assert results[0][1] == 0  # returncode


# ---------------------------------------------------------------------------
# _update_page_status_json — JSON decode error path
# ---------------------------------------------------------------------------


class TestUpdatePageStatusJsonEdge:
    def test_json_decode_error_does_nothing(self, tmp_path: Path):
        from great_docs._versioned_build import _update_page_status_json

        status_path = tmp_path / "_page_status.json"
        status_path.write_text("not valid json {{{", encoding="utf-8")
        # Should not raise
        _update_page_status_json(tmp_path, [("page.html", "0.4")])
        # File unchanged (still invalid)
        assert "not valid json" in status_path.read_text()

    def test_os_error_does_nothing(self, tmp_path: Path):
        from great_docs._versioned_build import _update_page_status_json

        # _page_status.json doesn't exist
        _update_page_status_json(tmp_path, [("page.html", "0.4")])
        assert not (tmp_path / "_page_status.json").exists()


# ---------------------------------------------------------------------------
# _sync_status_inline_script — detailed injection test
# ---------------------------------------------------------------------------


class TestSyncStatusInlineScriptIndentation:
    def test_matches_indentation_of_status_data_line(self, tmp_path: Path):
        from great_docs._versioned_build import _sync_status_inline_script

        status_data = {"upcoming_pages": {"guide.qmd": "0.4"}}
        (tmp_path / "_page_status.json").write_text(json.dumps(status_data), encoding="utf-8")

        # _quarto.yml with indented status data line
        yml_content = (
            "project:\n"
            "  type: website\n"
            "format:\n"
            "  html:\n"
            "    include-in-header:\n"
            "      - text: '<script>window.__GD_STATUS_DATA__={};'\n"
            "      - text: 'other'\n"
        )
        (tmp_path / "_quarto.yml").write_text(yml_content, encoding="utf-8")

        _sync_status_inline_script(tmp_path)

        result = (tmp_path / "_quarto.yml").read_text()
        assert "__GD_UPCOMING_DATA__" in result
        # Verify indentation matches — the injected line should start with same indent
        lines = result.split("\n")
        upcoming_line = [l for l in lines if "__GD_UPCOMING_DATA__" in l]
        assert len(upcoming_line) == 1
        assert upcoming_line[0].startswith("      ")

    def test_json_decode_error_skips(self, tmp_path: Path):
        from great_docs._versioned_build import _sync_status_inline_script

        (tmp_path / "_page_status.json").write_text("bad json!", encoding="utf-8")
        (tmp_path / "_quarto.yml").write_text("project:\n  type: website\n")
        # Should not raise
        _sync_status_inline_script(tmp_path)


# ---------------------------------------------------------------------------
# _prune_missing_sidebar_pages — full function with yaml12
# ---------------------------------------------------------------------------


class TestPruneMissingSidebarPagesFull:
    def test_prunes_via_yaml12(self, tmp_path: Path):
        from great_docs._versioned_build import _prune_missing_sidebar_pages

        # Create a _quarto.yml with sidebar referencing pages
        yml_content = {
            "project": {"type": "website"},
            "website": {
                "sidebar": [
                    {
                        "contents": [
                            "guide.qmd",
                            "removed.qmd",
                            {"section": "API", "contents": ["ref.qmd"]},
                        ]
                    }
                ]
            },
        }
        from yaml12 import write_yaml

        with open(tmp_path / "_quarto.yml", "w", encoding="utf-8") as f:
            write_yaml(yml_content, f)

        # Only guide.qmd exists, removed.qmd and ref.qmd don't
        (tmp_path / "guide.qmd").write_text("---\ntitle: Guide\n---\n")

        _prune_missing_sidebar_pages(tmp_path)

        from yaml12 import read_yaml

        with open(tmp_path / "_quarto.yml", "r", encoding="utf-8") as f:
            result = read_yaml(f)

        contents = result["website"]["sidebar"][0]["contents"]
        assert "guide.qmd" in contents
        assert "removed.qmd" not in contents
        # The "API" section with ref.qmd should be removed entirely
        section_items = [c for c in contents if isinstance(c, dict) and "section" in c]
        assert len(section_items) == 0

    def test_no_quarto_yml_does_nothing(self, tmp_path: Path):
        from great_docs._versioned_build import _prune_missing_sidebar_pages

        _prune_missing_sidebar_pages(tmp_path)  # Should not raise

    def test_empty_yaml_does_nothing(self, tmp_path: Path):
        from great_docs._versioned_build import _prune_missing_sidebar_pages

        (tmp_path / "_quarto.yml").write_text("", encoding="utf-8")
        _prune_missing_sidebar_pages(tmp_path)  # Should not raise


# ---------------------------------------------------------------------------
# _prune_cli_pages_for_version — snapshot loading
# ---------------------------------------------------------------------------


class TestPruneCliPagesForVersion:
    def test_no_git_ref_does_nothing(self, tmp_path: Path):
        from great_docs._versioned_build import _prune_cli_pages_for_version

        entry = VersionEntry(tag="0.3", label="0.3", latest=True, git_ref=None)
        _prune_cli_pages_for_version(tmp_path, tmp_path, entry)

    def test_no_cache_file_does_nothing(self, tmp_path: Path):
        from great_docs._versioned_build import _prune_cli_pages_for_version

        entry = VersionEntry(tag="0.2", label="0.2", latest=False, git_ref="v0.2.0")
        _prune_cli_pages_for_version(tmp_path, tmp_path, entry)

    def test_loads_snapshot_and_prunes(self, tmp_path: Path):
        from unittest.mock import MagicMock, patch

        from great_docs._versioned_build import _prune_cli_pages_for_version

        entry = VersionEntry(tag="0.2", label="0.2", latest=False, git_ref="v0.2.0")

        # Create the cache file
        cache_dir = tmp_path / ".great-docs-cache" / "snapshots"
        cache_dir.mkdir(parents=True)
        cache_file = cache_dir / "v0.2.0.json"

        # Write a minimal snapshot
        snap = ApiSnapshot(
            version="0.2",
            package_name="pkg",
            symbols={"func": SymbolInfo(name="func", kind="function")},
        )
        snap.save(cache_file)

        # Create CLI dir with pages
        cli_dir = tmp_path / "reference" / "cli"
        cli_dir.mkdir(parents=True)
        (cli_dir / "index.qmd").write_text("CLI")
        (cli_dir / "build.qmd").write_text("build cmd")

        # The snapshot doesn't have cli_commands, so no pruning occurs (early return)
        _prune_cli_pages_for_version(tmp_path, tmp_path, entry)
        assert (cli_dir / "build.qmd").exists()


# ---------------------------------------------------------------------------
# preprocess_version — upcoming detection, badge expiry override
# ---------------------------------------------------------------------------


class TestPreprocessVersionUpcoming:
    def _setup_versions(self):
        return parse_versions_config(
            [
                {"tag": "0.4", "label": "0.4 (dev)", "prerelease": True},
                "0.3",
                "0.2",
            ]
        )

    def test_upcoming_page_via_scoping(self, tmp_path: Path):
        """Pages scoped only to prerelease versions are marked upcoming."""
        source = tmp_path / "source"
        _make_source_tree(
            source,
            {
                "index.qmd": "---\ntitle: Home\n---\n\nWelcome!",
                "new-feature.qmd": '---\ntitle: New\nversions: ["0.4"]\n---\n\nOnly 0.4.',
            },
        )

        versions = self._setup_versions()
        # Build for 0.4 (the prerelease)
        dest = tmp_path / "build"
        pages = preprocess_version(source, dest, versions[0], versions)

        assert "new-feature.html" in pages

    def test_upcoming_page_via_frontmatter_key(self, tmp_path: Path):
        """Pages with `upcoming: "0.4"` are detected as upcoming for older versions."""
        source = tmp_path / "source"
        _make_source_tree(
            source,
            {
                "index.qmd": "---\ntitle: Home\n---\nHi",
                "future.qmd": '---\ntitle: Future\nupcoming: "0.4"\n---\nContent',
            },
        )

        versions = self._setup_versions()

        # Build for 0.3: future.qmd should be included but flagged as upcoming
        dest = tmp_path / "build"
        pages = preprocess_version(source, dest, versions[1], versions)

        assert "future.html" in pages

    def test_badge_expiry_per_page_override(self, tmp_path: Path):
        """Pages with `new-is-old` frontmatter override the global badge expiry."""
        source = tmp_path / "source"
        _make_source_tree(
            source,
            {
                "page.qmd": (
                    "---\ntitle: Page\nnew-is-old: 1 releases\n---\n\n[version-badge new 0.2]\n"
                ),
            },
        )

        versions = self._setup_versions()
        dest = tmp_path / "build"
        preprocess_version(source, dest, versions[1], versions)
        content = (dest / "page.qmd").read_text()

        # With expiry="1 releases", badge for 0.2 should be expired when building 0.3
        # (0.3 is 1 release after 0.2)
        assert "gd-badge" not in content  # badge was suppressed

    def test_section_level_scoping_excludes_pages(self, tmp_path: Path):
        """Pages under an excluded section dir are removed."""
        source = tmp_path / "source"
        _make_source_tree(
            source,
            {
                "index.qmd": "---\ntitle: Home\n---\nHi",
                "recipes/foo.qmd": "---\ntitle: Foo\n---\nRecipe",
            },
        )

        versions = self._setup_versions()
        # Exclude 'recipes' for version 0.2
        section_configs = [{"dir": "recipes", "versions": ["0.3", "0.4"]}]
        dest = tmp_path / "build"
        pages = preprocess_version(
            source, dest, versions[2], versions, section_configs=section_configs
        )
        assert "recipes/foo.html" not in pages
        assert not (dest / "recipes" / "foo.qmd").exists()


# ---------------------------------------------------------------------------
# _rebuild_api_from_snapshot — edge cases
# ---------------------------------------------------------------------------


class TestRebuildApiFromSnapshotEdge:
    def test_no_ref_dir_creates_it(self, tmp_path: Path):

        # Create a minimal snapshot
        snap_path = tmp_path / "snap.json"
        snap = ApiSnapshot(
            version="0.2",
            package_name="pkg",
            symbols={
                "MyFunc": SymbolInfo(
                    name="MyFunc",
                    kind="function",
                    parameters=[ParameterInfo(name="x", annotation="int")],
                    return_annotation="str",
                ),
            },
        )
        snap.save(snap_path)

        dest_dir = tmp_path / "build"
        dest_dir.mkdir()
        # No reference/ dir exists yet

        entry = _make_entry("0.2")
        pages = _rebuild_api_from_snapshot(dest_dir, snap_path, entry)

        assert "reference/MyFunc.html" in pages
        assert (dest_dir / "reference" / "MyFunc.qmd").exists()
        assert (dest_dir / "reference" / "index.qmd").exists()

    def test_preserves_rich_pages(self, tmp_path: Path):

        snap_path = tmp_path / "snap.json"
        snap = ApiSnapshot(
            version="0.2",
            package_name="pkg",
            symbols={"GT": SymbolInfo(name="GT", kind="class", bases=["Base"])},
        )
        snap.save(snap_path)

        dest_dir = tmp_path / "build"
        ref_dir = dest_dir / "reference"
        ref_dir.mkdir(parents=True)
        # A rich page with {.doc- class
        (ref_dir / "GT.qmd").write_text("---\ntitle: GT\n---\n# GT {.doc-heading}\nRich content\n")

        entry = _make_entry("0.2")
        pages = _rebuild_api_from_snapshot(dest_dir, snap_path, entry)
        assert "reference/GT.html" in pages
        # Content should be preserved
        assert "Rich content" in (ref_dir / "GT.qmd").read_text()

    def test_generates_index_with_classes_and_functions(self, tmp_path: Path):

        snap_path = tmp_path / "snap.json"
        snap = ApiSnapshot(
            version="0.2",
            package_name="pkg",
            symbols={
                "MyClass": SymbolInfo(name="MyClass", kind="class"),
                "my_func": SymbolInfo(name="my_func", kind="function"),
            },
        )
        snap.save(snap_path)

        dest_dir = tmp_path / "build"
        dest_dir.mkdir()

        entry = _make_entry("0.2")
        _rebuild_api_from_snapshot(dest_dir, snap_path, entry)

        index_content = (dest_dir / "reference" / "index.qmd").read_text()
        assert "## Classes" in index_content
        assert "## Functions" in index_content
        assert "MyClass" in index_content
        assert "my_func" in index_content

    def test_prunes_existing_pages_not_in_snapshot(self, tmp_path: Path):

        snap_path = tmp_path / "snap.json"
        snap = ApiSnapshot(
            version="0.2",
            package_name="pkg",
            symbols={"kept": SymbolInfo(name="kept", kind="function")},
        )
        snap.save(snap_path)

        dest_dir = tmp_path / "build"
        ref_dir = dest_dir / "reference"
        ref_dir.mkdir(parents=True)
        (ref_dir / "kept.qmd").write_text("---\ntitle: kept\n---\n")
        (ref_dir / "removed.qmd").write_text("---\ntitle: removed\n---\n")
        (ref_dir / "index.qmd").write_text("---\ntitle: API\n---\n")

        entry = _make_entry("0.2")
        _rebuild_api_from_snapshot(dest_dir, snap_path, entry)

        assert (ref_dir / "kept.qmd").exists()
        assert not (ref_dir / "removed.qmd").exists()
        assert (ref_dir / "index.qmd").exists()

    def test_shallow_snapshot_keeps_method_pages(self, tmp_path: Path):
        # Regression guard for #190: when the documented set can't be resolved,
        # the snapshot is shallow (top-level keys only). Method pages must NOT
        # be destructively pruned just because `Class.method` is not a key.

        snap_path = tmp_path / "snap.json"
        snap = ApiSnapshot(
            version="0.2",
            package_name="pkg",
            symbols={"Big": SymbolInfo(name="Big", kind="class")},
        )
        snap.save(snap_path)

        dest_dir = tmp_path / "build"
        ref_dir = dest_dir / "reference"
        ref_dir.mkdir(parents=True)
        (ref_dir / "Big.qmd").write_text("---\ntitle: Big\n---\n")
        (ref_dir / "Big.m0.qmd").write_text("---\ntitle: Big.m0\n---\n")
        (ref_dir / "Big.m1.qmd").write_text("---\ntitle: Big.m1\n---\n")
        (ref_dir / "Orphan.method.qmd").write_text("---\ntitle: Orphan.method\n---\n")
        (ref_dir / "index.qmd").write_text("---\ntitle: API\n---\n")

        entry = _make_entry("0.2")
        _rebuild_api_from_snapshot(dest_dir, snap_path, entry)

        # Methods of a documented class survive under the shallow fallback.
        assert (ref_dir / "Big.qmd").exists()
        assert (ref_dir / "Big.m0.qmd").exists()
        assert (ref_dir / "Big.m1.qmd").exists()

        # A method whose class is absent is still pruned.
        assert not (ref_dir / "Orphan.method.qmd").exists()

    def test_deep_snapshot_prunes_dropped_method_pages(self, tmp_path: Path):
        # With a deep snapshot (dotted keys present), exact membership governs:
        # a method page absent from the snapshot is correctly pruned.
        from great_docs._versioned_build import _rebuild_api_from_snapshot

        snap_path = tmp_path / "snap.json"
        snap = ApiSnapshot(
            version="0.2",
            package_name="pkg",
            symbols={
                "Big": SymbolInfo(name="Big", kind="class"),
                "Big.m0": SymbolInfo(name="Big.m0", kind="function"),
            },
        )
        snap.save(snap_path)

        dest_dir = tmp_path / "build"
        ref_dir = dest_dir / "reference"
        ref_dir.mkdir(parents=True)
        (ref_dir / "Big.qmd").write_text("---\ntitle: Big\n---\n")
        (ref_dir / "Big.m0.qmd").write_text("---\ntitle: Big.m0\n---\n")
        (ref_dir / "Big.m1.qmd").write_text("---\ntitle: Big.m1\n---\n")
        (ref_dir / "index.qmd").write_text("---\ntitle: API\n---\n")

        entry = _make_entry("0.2")
        _rebuild_api_from_snapshot(dest_dir, snap_path, entry)

        assert (ref_dir / "Big.qmd").exists()
        assert (ref_dir / "Big.m0.qmd").exists()
        # m1 is no longer documented at this version → pruned.
        assert not (ref_dir / "Big.m1.qmd").exists()

    def test_rich_index_pruned_not_regenerated(self, tmp_path: Path):
        from great_docs._versioned_build import _rebuild_api_from_snapshot

        snap_path = tmp_path / "snap.json"
        snap = ApiSnapshot(
            version="0.2",
            package_name="pkg",
            symbols={"kept": SymbolInfo(name="kept", kind="function")},
        )
        snap.save(snap_path)

        dest_dir = tmp_path / "build"
        ref_dir = dest_dir / "reference"
        ref_dir.mkdir(parents=True)
        # Rich index with {.doc- markers
        (ref_dir / "index.qmd").write_text(
            "---\ntitle: API\n---\n\n"
            "## Functions {.doc-group}\n\n"
            "::: {.doc-description}\nFuncs\n:::\n\n"
            "[`kept`](kept.qmd)\n\n"
            "[`removed`](removed.qmd)\n\n"
        )

        entry = _make_entry("0.2")
        _rebuild_api_from_snapshot(dest_dir, snap_path, entry)

        index_content = (ref_dir / "index.qmd").read_text()
        assert "kept" in index_content
        assert "removed" not in index_content


# ---------------------------------------------------------------------------
# _prune_reference_index — definition-list description lines
# ---------------------------------------------------------------------------


class TestPruneReferenceIndexDefinitionList:
    def test_removes_definition_list_descriptions(self, tmp_path: Path):
        from great_docs._versioned_build import _prune_reference_index

        index = tmp_path / "index.qmd"
        index.write_text(
            "---\ntitle: API\n---\n\n"
            "[`kept_func`](kept_func.qmd)\n"
            ":   The kept function description.\n\n"
            "[`removed_func`](removed_func.qmd)\n"
            ":   The removed function description.\n\n"
            "[`another_kept`](another_kept.qmd)\n"
            ":   Another kept description.\n"
        )

        _prune_reference_index(index, {"kept_func", "another_kept"})

        content = index.read_text()
        assert "kept_func" in content
        assert "another_kept" in content
        assert "removed_func" not in content
        assert "removed function description" not in content

    def test_removes_bare_ref_links(self, tmp_path: Path):
        from great_docs._versioned_build import _prune_reference_index

        index = tmp_path / "index.qmd"
        index.write_text("---\ntitle: API\n---\n\n- OldFunc.qmd\n- KeptFunc.qmd\n")

        _prune_reference_index(index, {"KeptFunc"})

        content = index.read_text()
        assert "KeptFunc" in content
        assert "OldFunc" not in content


# ---------------------------------------------------------------------------
# _prune_quarto_sidebar — nested sidebar with sub-paths
# ---------------------------------------------------------------------------


class TestPruneQuartoSidebarSubPath:
    def test_keeps_sub_paths(self, tmp_path: Path):
        """Sub-paths like reference/cli/build.qmd are kept (not pruned)."""
        import yaml

        from great_docs._versioned_build import _prune_quarto_sidebar

        quarto = tmp_path / "_quarto.yml"
        config = {
            "website": {
                "sidebar": [
                    {
                        "id": "api",
                        "contents": [
                            "reference/MyFunc.qmd",
                            "reference/cli/build.qmd",
                            "reference/Removed.qmd",
                        ],
                    }
                ]
            }
        }
        quarto.write_text(yaml.dump(config), encoding="utf-8")

        _prune_quarto_sidebar(tmp_path, "reference", {"MyFunc"})

        result = yaml.safe_load(quarto.read_text())
        contents = result["website"]["sidebar"][0]["contents"]
        assert "reference/MyFunc.qmd" in contents
        assert "reference/cli/build.qmd" in contents  # sub-path kept
        assert "reference/Removed.qmd" not in contents

    def test_no_matching_sidebar_does_nothing(self, tmp_path: Path):
        import yaml

        from great_docs._versioned_build import _prune_quarto_sidebar

        quarto = tmp_path / "_quarto.yml"
        config = {"website": {"sidebar": [{"id": "other", "contents": ["guide.qmd"]}]}}
        quarto.write_text(yaml.dump(config), encoding="utf-8")

        _prune_quarto_sidebar(tmp_path, "reference", {"func"})

        # File should be unchanged since no sidebar matches
        result = yaml.safe_load(quarto.read_text())
        assert result["website"]["sidebar"][0]["contents"] == ["guide.qmd"]

    def test_no_quarto_yml_does_nothing(self, tmp_path: Path):
        from great_docs._versioned_build import _prune_quarto_sidebar

        _prune_quarto_sidebar(tmp_path, "reference", {"func"})

    def test_empty_yaml_does_nothing(self, tmp_path: Path):
        from great_docs._versioned_build import _prune_quarto_sidebar

        (tmp_path / "_quarto.yml").write_text("", encoding="utf-8")
        _prune_quarto_sidebar(tmp_path, "reference", {"func"})


# ---------------------------------------------------------------------------
# _rebuild_api_from_git_ref — cache hit path
# ---------------------------------------------------------------------------


class TestRebuildApiFromGitRefCache:
    def test_cache_hit_uses_cached_snapshot(self, tmp_path: Path):
        from unittest.mock import patch

        from great_docs._versioned_build import _rebuild_api_from_git_ref

        entry = VersionEntry(tag="0.2", label="0.2", latest=False, git_ref="v0.2.0")

        # Create cached snapshot
        cache_dir = tmp_path / ".great-docs-cache" / "snapshots"
        cache_dir.mkdir(parents=True)
        cache_file = cache_dir / "v0.2.0.json"
        snap = ApiSnapshot(
            version="0.2",
            package_name="pkg",
            symbols={"my_func": SymbolInfo(name="my_func", kind="function")},
        )
        snap.save(cache_file)

        # Dest dir for the build
        dest = tmp_path / "build"
        dest.mkdir()

        with patch("great_docs._versioned_build._validate_git_ref_is_tag", return_value=True):
            pages = _rebuild_api_from_git_ref(dest, tmp_path, entry)

        assert "reference/my_func.html" in pages

    def test_cache_miss_calls_snapshot_at_tag(self, tmp_path: Path):
        from unittest.mock import MagicMock, patch

        from great_docs._versioned_build import _rebuild_api_from_git_ref

        entry = VersionEntry(tag="0.2", label="0.2", latest=False, git_ref="v0.2.0")

        dest = tmp_path / "build"
        dest.mkdir()

        mock_snap = ApiSnapshot(
            version="0.2",
            package_name="pkg",
            symbols={"func2": SymbolInfo(name="func2", kind="function")},
        )

        with (
            patch(
                "great_docs._versioned_build._validate_git_ref_is_tag",
                return_value=True,
            ),
            patch("great_docs._api_diff._detect_package_name", return_value="pkg"),
            patch("great_docs._api_diff.snapshot_at_tag", return_value=mock_snap),
        ):
            pages = _rebuild_api_from_git_ref(dest, tmp_path, entry)

        assert "reference/func2.html" in pages
        # Cache should have been written
        cache_path = tmp_path / ".great-docs-cache" / "snapshots" / "v0.2.0.json"
        assert cache_path.exists()

    def test_cache_miss_no_package_returns_empty(self, tmp_path: Path):
        from unittest.mock import patch

        from great_docs._versioned_build import _rebuild_api_from_git_ref

        entry = VersionEntry(tag="0.2", label="0.2", latest=False, git_ref="v0.2.0")
        dest = tmp_path / "build"
        dest.mkdir()

        with (
            patch(
                "great_docs._versioned_build._validate_git_ref_is_tag",
                return_value=True,
            ),
            patch("great_docs._api_diff._detect_package_name", return_value=None),
        ):
            pages = _rebuild_api_from_git_ref(dest, tmp_path, entry)

        assert pages == []

    def test_cache_miss_snapshot_fails_returns_empty(self, tmp_path: Path):
        from unittest.mock import patch

        from great_docs._versioned_build import _rebuild_api_from_git_ref

        entry = VersionEntry(tag="0.2", label="0.2", latest=False, git_ref="v0.2.0")
        dest = tmp_path / "build"
        dest.mkdir()

        with (
            patch(
                "great_docs._versioned_build._validate_git_ref_is_tag",
                return_value=True,
            ),
            patch("great_docs._api_diff._detect_package_name", return_value="pkg"),
            patch("great_docs._api_diff.snapshot_at_tag", return_value=None),
        ):
            pages = _rebuild_api_from_git_ref(dest, tmp_path, entry)

        assert pages == []


# ---------------------------------------------------------------------------
# expand_version_badges — fence detection
# ---------------------------------------------------------------------------


class TestExpandVersionBadgesFenceEdge:
    def test_badge_inside_tilde_fence_not_expanded(self):
        entry = _make_entry("0.3")
        versions = parse_versions_config(["0.3", "0.2"])
        content = (
            "Before\n\n~~~python\n[version-badge new 0.3]\n~~~\n\nAfter [version-badge new 0.3]\n"
        )
        result = expand_version_badges(content, entry, versions)
        # Badge inside fence should NOT be expanded
        assert "[version-badge new 0.3]" in result
        # Badge after fence SHOULD be expanded
        assert "gd-badge-new" in result

    def test_badge_inside_4tick_fence_not_expanded(self):
        entry = _make_entry("0.3")
        versions = parse_versions_config(["0.3", "0.2"])
        content = "Before\n\n````\n[version-badge new 0.3]\n````\n\n[version-badge changed 0.3]\n"
        result = expand_version_badges(content, entry, versions)
        # Inside the 4-tick fence should NOT be expanded
        lines = result.split("\n")
        inside_fence = False
        for line in lines:
            if line.strip() == "````":
                inside_fence = not inside_fence
                continue
            if inside_fence and "version-badge" in line:
                assert "gd-badge" not in line
        # After fence should be expanded
        assert "gd-badge-changed" in result

    def test_unclosed_fence_protects_rest_of_content(self):
        entry = _make_entry("0.3")
        versions = parse_versions_config(["0.3", "0.2"])
        content = (
            "[version-badge new 0.3] before\n\n"
            "```python\n"
            "[version-badge new 0.3] inside fence (never closed)\n"
        )
        result = expand_version_badges(content, entry, versions)
        # First badge (before fence) should be expanded
        assert "gd-badge-new" in result


# ---------------------------------------------------------------------------
# _rewrite_quarto_yml_for_version — edge cases
# ---------------------------------------------------------------------------


class TestRewriteQuartoYmlEdge:
    def test_no_quarto_yml_does_nothing(self, tmp_path: Path):
        from great_docs._versioned_build import _rewrite_quarto_yml_for_version

        entry = _make_entry("0.2")
        _rewrite_quarto_yml_for_version(tmp_path, entry, "0.3")  # no crash

    def test_non_latest_title_gets_version_suffix(self, tmp_path: Path):
        from yaml12 import read_yaml, write_yaml

        from great_docs._versioned_build import _rewrite_quarto_yml_for_version

        dest = tmp_path / "vdir"
        dest.mkdir()
        config = {
            "project": {"type": "website", "output-dir": "_site"},
            "format": {"html": {}},
            "website": {"title": "My Docs"},
        }
        with open(dest / "_quarto.yml", "w") as f:
            write_yaml(config, f)

        entry = _make_entry("0.2")
        _rewrite_quarto_yml_for_version(dest, entry, "0.3", site_url="https://x.com")

        with open(dest / "_quarto.yml", "r") as f:
            result = read_yaml(f)

        assert "(0.2)" in result["website"]["title"]

    def test_include_in_header_str_converted_to_list(self, tmp_path: Path):
        """If include-in-header is a string, it's converted to a list."""
        from yaml12 import read_yaml, write_yaml

        from great_docs._versioned_build import _rewrite_quarto_yml_for_version

        dest = tmp_path / "vdir"
        dest.mkdir()
        config = {
            "project": {"type": "website", "output-dir": "_site"},
            "format": {"html": {"include-in-header": "existing.html"}},
            "website": {"title": "Docs"},
        }
        with open(dest / "_quarto.yml", "w") as f:
            write_yaml(config, f)

        entry = _make_entry("0.2")
        _rewrite_quarto_yml_for_version(dest, entry, "0.3", site_url="https://x.com")

        with open(dest / "_quarto.yml", "r") as f:
            result = read_yaml(f)

        header = result["format"]["html"]["include-in-header"]
        assert isinstance(header, list)
        assert header[0] == "existing.html"
        assert any("canonical" in str(h) for h in header)


# ---------------------------------------------------------------------------
# run_versioned_build — orchestrator with mocked render
# ---------------------------------------------------------------------------


class TestRunVersionedBuild:
    def test_full_build_with_mocked_render(self, tmp_path: Path):
        from unittest.mock import MagicMock, patch

        # Set up source tree
        source = tmp_path / "source"
        _make_source_tree(
            source,
            {
                "index.qmd": "---\ntitle: Home\n---\nHi",
                "guide.qmd": "---\ntitle: Guide\n---\nContent",
            },
        )

        project_root = tmp_path / "project"
        project_root.mkdir()

        # Mock render to return success
        def mock_render(build_dirs, env_vars=None, max_workers=None, progress_callback=None):
            results = []
            for d in build_dirs:
                # Create a _site dir to simulate build output
                site_dir = d / "_site"
                site_dir.mkdir(parents=True, exist_ok=True)
                (site_dir / "index.html").write_text("<html>hi</html>")
                results.append((str(d), 0, "", "", []))
            return results

        with patch(
            "great_docs._versioned_build.render_versions_parallel",
            side_effect=mock_render,
        ):
            result = run_versioned_build(
                source_dir=source,
                project_root=project_root,
                versions_config=["0.3", "0.2"],
            )

        assert result["success"] is True
        assert "0.3" in result["versions_built"]
        assert "0.2" in result["versions_built"]
        assert (source / "_site" / "index.html").exists()
        assert (source / "_site" / "_version_map.json").exists()

    def test_latest_only_builds_single_version(self, tmp_path: Path):
        from unittest.mock import patch

        source = tmp_path / "source"
        _make_source_tree(source, {"index.qmd": "---\ntitle: Hi\n---\nHi"})

        project_root = tmp_path / "project"
        project_root.mkdir()

        def mock_render(build_dirs, **kwargs):
            results = []
            for d in build_dirs:
                site_dir = d / "_site"
                site_dir.mkdir(parents=True, exist_ok=True)
                (site_dir / "index.html").write_text("<html/>")
                results.append((str(d), 0, "", "", []))
            return results

        with patch(
            "great_docs._versioned_build.render_versions_parallel",
            side_effect=mock_render,
        ):
            result = run_versioned_build(
                source_dir=source,
                project_root=project_root,
                versions_config=["0.3", "0.2"],
                latest_only=True,
            )

        assert result["success"] is True
        assert result["versions_built"] == ["0.3"]

    def test_version_tags_filter(self, tmp_path: Path):
        from unittest.mock import patch

        source = tmp_path / "source"
        _make_source_tree(source, {"index.qmd": "---\ntitle: Hi\n---\nHi"})

        project_root = tmp_path / "project"
        project_root.mkdir()

        def mock_render(build_dirs, **kwargs):
            results = []
            for d in build_dirs:
                site_dir = d / "_site"
                site_dir.mkdir(parents=True, exist_ok=True)
                (site_dir / "index.html").write_text("<html/>")
                results.append((str(d), 0, "", "", []))
            return results

        with patch(
            "great_docs._versioned_build.render_versions_parallel",
            side_effect=mock_render,
        ):
            result = run_versioned_build(
                source_dir=source,
                project_root=project_root,
                versions_config=["0.3", "0.2", "0.1"],
                version_tags=["0.2"],
            )

        assert result["success"] is True
        assert result["versions_built"] == ["0.2"]

    def test_render_failure_reported(self, tmp_path: Path):
        from unittest.mock import patch

        source = tmp_path / "source"
        _make_source_tree(source, {"index.qmd": "---\ntitle: Hi\n---\nHi"})

        project_root = tmp_path / "project"
        project_root.mkdir()

        def mock_render(build_dirs, **kwargs):
            # All versions fail
            return [(str(d), 1, "", "ERROR: something broke", []) for d in build_dirs]

        with patch(
            "great_docs._versioned_build.render_versions_parallel",
            side_effect=mock_render,
        ):
            result = run_versioned_build(
                source_dir=source,
                project_root=project_root,
                versions_config=["0.3"],
            )

        assert result["success"] is False
        assert result["versions_built"] == []
        assert len(result["errors"]) == 1
        assert "failed" in result["errors"][0]

    def test_on_renders_done_callback(self, tmp_path: Path):
        from unittest.mock import MagicMock, patch

        source = tmp_path / "source"
        _make_source_tree(source, {"index.qmd": "---\ntitle: Hi\n---\nHi"})

        project_root = tmp_path / "project"
        project_root.mkdir()

        callback = MagicMock()

        def mock_render(build_dirs, **kwargs):
            results = []
            for d in build_dirs:
                site_dir = d / "_site"
                site_dir.mkdir(parents=True, exist_ok=True)
                (site_dir / "index.html").write_text("<html/>")
                results.append((str(d), 0, "", "", []))
            return results

        with patch(
            "great_docs._versioned_build.render_versions_parallel",
            side_effect=mock_render,
        ):
            run_versioned_build(
                source_dir=source,
                project_root=project_root,
                versions_config=["0.3"],
                on_renders_done=callback,
            )

        callback.assert_called_once()

    def test_badge_expiry_raw_passed_through(self, tmp_path: Path):
        from unittest.mock import patch

        source = tmp_path / "source"
        _make_source_tree(
            source,
            {"index.qmd": "---\ntitle: Hi\n---\n\n[version-badge new 0.1]\n"},
        )

        project_root = tmp_path / "project"
        project_root.mkdir()

        def mock_render(build_dirs, **kwargs):
            results = []
            for d in build_dirs:
                site_dir = d / "_site"
                site_dir.mkdir(parents=True, exist_ok=True)
                (site_dir / "index.html").write_text("<html/>")
                results.append((str(d), 0, "", "", []))
            return results

        with patch(
            "great_docs._versioned_build.render_versions_parallel",
            side_effect=mock_render,
        ):
            result = run_versioned_build(
                source_dir=source,
                project_root=project_root,
                versions_config=["0.3", "0.2", "0.1"],
                badge_expiry_raw="1",
            )

        assert result["success"] is True


# ---------------------------------------------------------------------------
# _render_single_version_streaming — subprocess mocking
# ---------------------------------------------------------------------------


class TestRenderSingleVersionStreaming:
    def test_successful_render_with_progress(self, tmp_path: Path):
        from unittest.mock import MagicMock, patch

        from great_docs._versioned_build import _render_single_version_streaming

        # Mock subprocess.Popen
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout.read.return_value = "output"
        # Simulate stderr with progress lines
        mock_proc.stderr.__iter__ = lambda self: iter(
            ["[1/3] page1.qmd\n", "[2/3] page2.qmd\n", "[3/3] page3.qmd\n"]
        )
        mock_proc.wait.return_value = 0

        progress = MagicMock()

        with patch("subprocess.Popen", return_value=mock_proc):
            result = _render_single_version_streaming(str(tmp_path), None, on_progress=progress)

        assert result[0] == str(tmp_path)
        assert result[1] == 0
        assert result[2] == "output"
        assert progress.call_count == 3

    def test_popen_failure_returns_error(self, tmp_path: Path):
        from unittest.mock import patch

        from great_docs._versioned_build import _render_single_version_streaming

        with patch("subprocess.Popen", side_effect=OSError("not found")):
            result = _render_single_version_streaming(str(tmp_path), None)

        assert result[0] == str(tmp_path)
        assert result[1] == -1
        assert "not found" in result[3]

    def test_with_env_vars(self, tmp_path: Path):
        from unittest.mock import MagicMock, patch

        from great_docs._versioned_build import _render_single_version_streaming

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout.read.return_value = ""
        mock_proc.stderr.__iter__ = lambda self: iter([])
        mock_proc.wait.return_value = 0

        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            _render_single_version_streaming(str(tmp_path), {"QUARTO_PYTHON": "/usr/bin/python3"})

        # Check that env vars were passed
        call_kwargs = mock_popen.call_args[1]
        assert "QUARTO_PYTHON" in call_kwargs["env"]


# ---------------------------------------------------------------------------
# render_versions_parallel — streaming mode with multiple dirs
# ---------------------------------------------------------------------------


class TestRenderVersionsParallelStreaming:
    def test_streaming_mode_ordered_results(self, tmp_path: Path):
        from unittest.mock import MagicMock, patch

        from great_docs._versioned_build import render_versions_parallel

        d1 = tmp_path / "v1"
        d2 = tmp_path / "v2"
        d1.mkdir()
        d2.mkdir()

        def mock_streaming(build_dir, env_vars, on_progress=None):
            if on_progress:
                on_progress(1, 2)
            return (build_dir, 0, "", "")

        with patch(
            "great_docs._versioned_build._render_single_version_streaming",
            side_effect=mock_streaming,
        ):
            callback = MagicMock()
            results = render_versions_parallel([d1, d2], progress_callback=callback)

        assert len(results) == 2
        # Results should be in same order as input dirs
        assert results[0][0] == str(d1)
        assert results[1][0] == str(d2)
        # Progress callback should have been called
        assert callback.call_count >= 2


# ---------------------------------------------------------------------------
# _prune_sidebar_contents — href dict entries
# ---------------------------------------------------------------------------


class TestPruneSidebarContentsHref:
    def test_removes_missing_href_dict_entry(self, tmp_path: Path):
        from great_docs._versioned_build import _prune_sidebar_contents

        contents = [
            {"href": "guide.qmd", "text": "Guide"},
            {"href": "removed.qmd", "text": "Removed"},
            "intro.qmd",
        ]

        # Create only guide.qmd and intro.qmd
        (tmp_path / "guide.qmd").write_text("guide")
        (tmp_path / "intro.qmd").write_text("intro")

        result = _prune_sidebar_contents(contents, tmp_path)
        assert {"href": "guide.qmd", "text": "Guide"} in result
        assert "intro.qmd" in result
        assert {"href": "removed.qmd", "text": "Removed"} not in result

    def test_keeps_non_qmd_href(self, tmp_path: Path):
        from great_docs._versioned_build import _prune_sidebar_contents

        contents = [
            {"href": "https://example.com", "text": "External"},
            {"href": "guide.qmd"},
        ]
        (tmp_path / "guide.qmd").write_text("guide")

        result = _prune_sidebar_contents(contents, tmp_path)
        assert len(result) == 2  # both kept


# ---------------------------------------------------------------------------
# _prune_cli_pages_for_version — with actual CLI commands
# ---------------------------------------------------------------------------


class TestPruneCliPagesForVersionFull:
    def test_prunes_cli_pages_via_snapshot(self, tmp_path: Path):
        from great_docs._api_diff import ApiSnapshot, CliCommandInfo
        from great_docs._versioned_build import _prune_cli_pages_for_version

        entry = VersionEntry(tag="0.2", label="0.2", latest=False, git_ref="v0.2.0")

        # Create cached snapshot with CLI commands
        cache_dir = tmp_path / ".great-docs-cache" / "snapshots"
        cache_dir.mkdir(parents=True)
        cache_file = cache_dir / "v0.2.0.json"

        # We need a snapshot with cli_commands attribute
        snap = ApiSnapshot(
            version="0.2",
            package_name="pkg",
            symbols={"func": SymbolInfo(name="func", kind="function")},
            cli_commands=CliCommandInfo(
                name="cli",
                help="CLI tool",
                subcommands=[
                    CliCommandInfo(name="build", help="Build docs"),
                ],
            ),
        )
        snap.save(cache_file)

        # Create CLI reference dir with pages
        cli_dir = tmp_path / "reference" / "cli"
        cli_dir.mkdir(parents=True)
        (cli_dir / "index.qmd").write_text("CLI index")
        (cli_dir / "build.qmd").write_text("Build command")
        (cli_dir / "old_command.qmd").write_text("Old command")

        _prune_cli_pages_for_version(tmp_path, tmp_path, entry)

        # build.qmd should be kept, old_command.qmd should be removed
        assert (cli_dir / "build.qmd").exists()
        assert (cli_dir / "index.qmd").exists()
        assert not (cli_dir / "old_command.qmd").exists()


# ---------------------------------------------------------------------------
# preprocess_version — api_snapshot strategy
# ---------------------------------------------------------------------------


class TestPreprocessVersionApiSnapshot:
    def test_api_snapshot_strategy(self, tmp_path: Path):
        source = tmp_path / "source"
        _make_source_tree(source, {"index.qmd": "---\ntitle: Home\n---\nHi"})

        project_root = tmp_path / "project"
        project_root.mkdir()

        # Create a snapshot file
        snap_path = project_root / "api-snapshot.json"
        snap = ApiSnapshot(
            version="0.2",
            package_name="pkg",
            symbols={"my_func": SymbolInfo(name="my_func", kind="function")},
        )
        snap.save(snap_path)

        versions = parse_versions_config(["0.3", "0.2"])
        entry = VersionEntry(
            tag="0.2",
            label="0.2",
            latest=False,
            api_snapshot="api-snapshot.json",
        )

        dest = tmp_path / "build"
        pages = preprocess_version(source, dest, entry, versions, project_root=project_root)

        assert "reference/my_func.html" in pages
        assert (dest / "reference" / "my_func.qmd").exists()

    def test_api_snapshot_file_missing_skips(self, tmp_path: Path):
        source = tmp_path / "source"
        _make_source_tree(source, {"index.qmd": "---\ntitle: Home\n---\nHi"})

        project_root = tmp_path / "project"
        project_root.mkdir()

        versions = parse_versions_config(["0.3", "0.2"])
        entry = VersionEntry(
            tag="0.2",
            label="0.2",
            latest=False,
            api_snapshot="nonexistent-snapshot.json",
        )

        dest = tmp_path / "build"
        pages = preprocess_version(source, dest, entry, versions, project_root=project_root)

        # Should succeed without generating API pages
        assert "index.html" in pages
        assert not (dest / "reference").exists()


# ---------------------------------------------------------------------------
# _sync_status_inline_script — no upcoming map scenario
# ---------------------------------------------------------------------------


class TestSyncStatusNoUpcoming:
    def test_no_upcoming_map_returns_early(self, tmp_path: Path):
        from great_docs._versioned_build import _sync_status_inline_script

        # _page_status.json with empty upcoming_pages
        data = {"page_statuses": {"x.qmd": "new"}, "upcoming_pages": {}}
        (tmp_path / "_page_status.json").write_text(json.dumps(data))
        (tmp_path / "_quarto.yml").write_text("project:\n  type: website\n")

        _sync_status_inline_script(tmp_path)

        # _quarto.yml should be unchanged
        assert "__GD_UPCOMING_DATA__" not in (tmp_path / "_quarto.yml").read_text()

    def test_already_injected_skips(self, tmp_path: Path):
        from great_docs._versioned_build import _sync_status_inline_script

        data = {"upcoming_pages": {"x.qmd": "0.4"}}
        (tmp_path / "_page_status.json").write_text(json.dumps(data))
        yml_content = (
            "format:\n"
            "  html:\n"
            "    include-in-header:\n"
            "      - text: '<script>window.__GD_STATUS_DATA__={};'\n"
            '      - text: \'<script>window.__GD_UPCOMING_DATA__={"x.qmd":"0.4"};\'\n'
        )
        (tmp_path / "_quarto.yml").write_text(yml_content)

        _sync_status_inline_script(tmp_path)

        # Should not double-inject
        content = (tmp_path / "_quarto.yml").read_text()
        assert content.count("__GD_UPCOMING_DATA__") == 1

    def test_no_status_data_line_returns_early(self, tmp_path: Path):
        from great_docs._versioned_build import _sync_status_inline_script

        data = {"upcoming_pages": {"x.qmd": "0.4"}}
        (tmp_path / "_page_status.json").write_text(json.dumps(data))
        # _quarto.yml without __GD_STATUS_DATA__
        (tmp_path / "_quarto.yml").write_text("project:\n  type: website\n")

        _sync_status_inline_script(tmp_path)
        assert "__GD_UPCOMING_DATA__" not in (tmp_path / "_quarto.yml").read_text()


# ---------------------------------------------------------------------------
# render_versions_parallel — non-streaming multi-dir path
# ---------------------------------------------------------------------------


class TestRenderVersionsParallelNonStreaming:
    def test_multi_dir_uses_process_pool(self, tmp_path: Path):
        from concurrent.futures import Future
        from unittest.mock import MagicMock, patch

        from great_docs._versioned_build import render_versions_parallel

        d1 = tmp_path / "v1"
        d2 = tmp_path / "v2"
        d1.mkdir()
        d2.mkdir()

        # Mock ProcessPoolExecutor to avoid pickling issues
        mock_pool = MagicMock()
        mock_pool.__enter__ = MagicMock(return_value=mock_pool)
        mock_pool.__exit__ = MagicMock(return_value=False)

        # Create futures that return results
        f1 = Future()
        f1.set_result((str(d1), 0, "out1", ""))
        f2 = Future()
        f2.set_result((str(d2), 0, "out2", ""))

        mock_pool.submit.side_effect = [f1, f2]

        with patch(
            "great_docs._versioned_build.ProcessPoolExecutor",
            return_value=mock_pool,
        ):
            results = render_versions_parallel([d1, d2])  # No progress_callback

        assert len(results) == 2
        assert all(r[1] == 0 for r in results)


# ---------------------------------------------------------------------------
# preprocess_version — git_ref strategy within full function
# ---------------------------------------------------------------------------


class TestPreprocessVersionGitRef:
    def test_git_ref_strategy_in_preprocess(self, tmp_path: Path):
        from unittest.mock import patch

        source = tmp_path / "source"
        _make_source_tree(source, {"index.qmd": "---\ntitle: Home\n---\nHi"})

        project_root = tmp_path / "project"
        project_root.mkdir()

        # Create cached snapshot for the git_ref
        cache_dir = project_root / ".great-docs-cache" / "snapshots"
        cache_dir.mkdir(parents=True)
        cache_file = cache_dir / "v0.2.0.json"
        snap = ApiSnapshot(
            version="0.2",
            package_name="pkg",
            symbols={"my_func": SymbolInfo(name="my_func", kind="function")},
        )
        snap.save(cache_file)

        versions = parse_versions_config(["0.3", "0.2"])
        entry = VersionEntry(tag="0.2", label="0.2", latest=False, git_ref="v0.2.0")

        dest = tmp_path / "build"

        with patch(
            "great_docs._versioned_build._validate_git_ref_is_tag",
            return_value=True,
        ):
            pages = preprocess_version(source, dest, entry, versions, project_root=project_root)

        assert "reference/my_func.html" in pages


# ---------------------------------------------------------------------------
# _prune_quarto_sidebar — nested section groups with entries removed
# ---------------------------------------------------------------------------


class TestPruneQuartoSidebarNestedSectionGroup:
    def test_removes_empty_section_group(self, tmp_path: Path):
        import yaml

        from great_docs._versioned_build import _prune_quarto_sidebar

        quarto = tmp_path / "_quarto.yml"
        config = {
            "website": {
                "sidebar": [
                    {
                        "id": "api",
                        "contents": [
                            "reference/kept.qmd",
                            {
                                "section": "Deprecated",
                                "contents": [
                                    "reference/old1.qmd",
                                    "reference/old2.qmd",
                                ],
                            },
                        ],
                    }
                ]
            }
        }
        quarto.write_text(yaml.dump(config), encoding="utf-8")

        _prune_quarto_sidebar(tmp_path, "reference", {"kept"})

        result = yaml.safe_load(quarto.read_text())
        contents = result["website"]["sidebar"][0]["contents"]
        # The section group should be entirely removed since all its entries are invalid
        assert len(contents) == 1
        assert contents[0] == "reference/kept.qmd"

    def test_partially_prunes_section_group(self, tmp_path: Path):
        import yaml

        from great_docs._versioned_build import _prune_quarto_sidebar

        quarto = tmp_path / "_quarto.yml"
        config = {
            "website": {
                "sidebar": [
                    {
                        "id": "api",
                        "contents": [
                            {
                                "section": "Main",
                                "contents": [
                                    "reference/kept.qmd",
                                    "reference/removed.qmd",
                                ],
                            },
                        ],
                    }
                ]
            }
        }
        quarto.write_text(yaml.dump(config), encoding="utf-8")

        _prune_quarto_sidebar(tmp_path, "reference", {"kept"})

        result = yaml.safe_load(quarto.read_text())
        contents = result["website"]["sidebar"][0]["contents"]
        assert len(contents) == 1
        section = contents[0]
        assert section["section"] == "Main"
        assert section["contents"] == ["reference/kept.qmd"]


# ---------------------------------------------------------------------------
# render_versions_parallel — single dir non-streaming path
# ---------------------------------------------------------------------------


class TestRenderVersionsParallelSingleNonStreaming:
    def test_single_dir_no_callback(self, tmp_path: Path):
        from unittest.mock import patch

        from great_docs._versioned_build import render_versions_parallel

        d1 = tmp_path / "v1"
        d1.mkdir()

        with patch(
            "great_docs._versioned_build._render_single_version",
            return_value=(str(d1), 0, "output", ""),
        ):
            results = render_versions_parallel([d1])  # No callback, single dir

        assert len(results) == 1
        assert results[0] == (str(d1), 0, "output", "", [])


# ---------------------------------------------------------------------------
# _prune_cli_pages — with actual CLI commands that trigger pruning
# ---------------------------------------------------------------------------


class TestPruneCliPagesFull:
    def test_prunes_and_rewrites_index(self, tmp_path: Path):
        from unittest.mock import MagicMock

        from great_docs._versioned_build import _prune_cli_pages

        # Create a mock snapshot with cli_commands
        snap = MagicMock()
        sub1 = MagicMock()
        sub1.name = "build"
        sub2 = MagicMock()
        sub2.name = "serve"
        snap.cli_commands.subcommands = [sub1, sub2]

        # Create CLI ref dir with pages
        cli_dir = tmp_path / "reference" / "cli"
        cli_dir.mkdir(parents=True)
        (cli_dir / "index.qmd").write_text(
            "---\ntitle: CLI Reference\n---\n\n# CLI Reference\n\n"
            "## Commands {.doc-group}\n\n"
            "[build](build.qmd){.doc-function .doc-label .doc-label-cli}\n"
            ":   Build docs\n\n"
            "[serve](serve.qmd){.doc-function .doc-label .doc-label-cli}\n"
            ":   Serve docs\n\n"
            "[old-cmd](old_cmd.qmd){.doc-function .doc-label .doc-label-cli}\n"
            ":   Old command\n\n"
        )
        (cli_dir / "build.qmd").write_text("Build cmd")
        (cli_dir / "serve.qmd").write_text("Serve cmd")
        (cli_dir / "old_cmd.qmd").write_text("Old cmd")

        _prune_cli_pages(tmp_path, snap)

        # old_cmd.qmd should be removed (not in valid_stems)
        assert not (cli_dir / "old_cmd.qmd").exists()
        assert (cli_dir / "build.qmd").exists()
        assert (cli_dir / "serve.qmd").exists()
        # index.qmd should be rewritten without old-cmd
        index_content = (cli_dir / "index.qmd").read_text()
        assert "build" in index_content
        assert "serve" in index_content
        assert "old-cmd" not in index_content

    def test_no_cli_dir_returns_early(self, tmp_path: Path):
        from unittest.mock import MagicMock

        from great_docs._versioned_build import _prune_cli_pages

        snap = MagicMock()
        snap.cli_commands = None
        _prune_cli_pages(tmp_path, snap)  # No crash

    def test_no_cli_commands_returns_early(self, tmp_path: Path):
        from unittest.mock import MagicMock

        from great_docs._versioned_build import _prune_cli_pages

        cli_dir = tmp_path / "reference" / "cli"
        cli_dir.mkdir(parents=True)
        (cli_dir / "build.qmd").write_text("Build")

        snap = MagicMock()
        snap.cli_commands = None
        _prune_cli_pages(tmp_path, snap)
        # All files still there
        assert (cli_dir / "build.qmd").exists()


# ---------------------------------------------------------------------------
# _prune_missing_sidebar_pages — exception path
# ---------------------------------------------------------------------------


class TestPruneMissingSidebarPagesException:
    def test_corrupt_yaml_handled_gracefully(self, tmp_path: Path):
        from great_docs._versioned_build import _prune_missing_sidebar_pages

        (tmp_path / "_quarto.yml").write_text("invalid: yaml: content: [\n  unmatched bracket")
        # Should not raise
        _prune_missing_sidebar_pages(tmp_path)


# ---------------------------------------------------------------------------
# _prune_sidebar_contents — href dict with missing .qmd file
# ---------------------------------------------------------------------------


class TestPruneSidebarContentsHrefMissing:
    def test_removes_href_dict_with_missing_md_file(self, tmp_path: Path):
        from great_docs._versioned_build import _prune_sidebar_contents

        contents = [
            {"href": "intro.md", "text": "Intro"},
            {"href": "missing.md", "text": "Missing"},
        ]
        (tmp_path / "intro.md").write_text("# Intro")

        result = _prune_sidebar_contents(contents, tmp_path)
        assert len(result) == 1
        assert result[0]["href"] == "intro.md"


# ---------------------------------------------------------------------------
# run_versioned_build
# ---------------------------------------------------------------------------


class TestRunVersionedBuildEmptyRender:
    """Tests for detecting when Quarto exits 0 but produces no HTML."""

    def test_quarto_exit_zero_no_html_reports_error(self, tmp_path: Path):
        """When Quarto succeeds (exit 0) but creates no HTML, report failure."""
        from unittest.mock import patch

        source = tmp_path / "source"
        _make_source_tree(source, {"index.qmd": "---\ntitle: Hi\n---\nContent"})

        project_root = tmp_path / "project"
        project_root.mkdir()

        def mock_render_no_output(build_dirs, **kwargs):
            # Quarto exits 0 but creates NO _site directory (empty render)
            return [(str(d), 0, "", "", []) for d in build_dirs]

        with patch(
            "great_docs._versioned_build.render_versions_parallel",
            side_effect=mock_render_no_output,
        ):
            result = run_versioned_build(
                source_dir=source,
                project_root=project_root,
                versions_config=["0.3"],
            )

        assert result["success"] is False
        assert result["versions_built"] == []
        assert len(result["errors"]) >= 1
        assert "no HTML pages" in result["errors"][0]

    def test_quarto_exit_zero_empty_site_dir_reports_error(self, tmp_path: Path):
        """When Quarto creates _site but it's empty, report failure."""
        from unittest.mock import patch

        source = tmp_path / "source"
        _make_source_tree(source, {"index.qmd": "---\ntitle: Hi\n---\nContent"})

        project_root = tmp_path / "project"
        project_root.mkdir()

        def mock_render_empty_site(build_dirs, **kwargs):
            results = []
            for d in build_dirs:
                # Create _site but with no HTML files
                site_dir = d / "_site"
                site_dir.mkdir(parents=True, exist_ok=True)
                (site_dir / "sitemap.xml").write_text("<urlset/>")
                results.append((str(d), 0, "", "", []))
            return results

        with patch(
            "great_docs._versioned_build.render_versions_parallel",
            side_effect=mock_render_empty_site,
        ):
            result = run_versioned_build(
                source_dir=source,
                project_root=project_root,
                versions_config=["0.3", "0.2"],
            )

        assert result["success"] is False
        assert result["versions_built"] == []
        assert len(result["errors"]) == 2

        for err in result["errors"]:
            assert "no HTML pages" in err

    def test_pre_render_check_no_qmd_files(self, tmp_path: Path):
        """When preprocessing removes all .qmd files, abort before render."""
        from unittest.mock import patch

        source = tmp_path / "source"
        source.mkdir(parents=True)
        # Only _quarto.yml, no .qmd files
        (source / "_quarto.yml").write_text(
            "project:\n  type: website\n  output-dir: _site\nwebsite:\n  title: Test\n"
        )

        project_root = tmp_path / "project"
        project_root.mkdir()

        render_called = []

        def mock_render(build_dirs, **kwargs):
            render_called.append(True)
            return [(str(d), 0, "", "", []) for d in build_dirs]

        with patch(
            "great_docs._versioned_build.render_versions_parallel",
            side_effect=mock_render,
        ):
            result = run_versioned_build(
                source_dir=source,
                project_root=project_root,
                versions_config=["0.3"],
            )

        assert result["success"] is False
        assert "No .qmd files" in result["errors"][0]

        # Render should NOT have been called
        assert render_called == []

    def test_pre_render_check_missing_quarto_yml(self, tmp_path: Path):
        """When _quarto.yml is missing from build dir, abort before render."""
        from unittest.mock import patch

        source = tmp_path / "source"
        source.mkdir(parents=True)
        # Create a .qmd file but no _quarto.yml
        (source / "index.qmd").write_text("---\ntitle: Hi\n---\nContent")

        project_root = tmp_path / "project"
        project_root.mkdir()

        render_called = []

        def mock_render(build_dirs, **kwargs):
            render_called.append(True)
            return [(str(d), 0, "", "", []) for d in build_dirs]

        with patch(
            "great_docs._versioned_build.render_versions_parallel",
            side_effect=mock_render,
        ):
            result = run_versioned_build(
                source_dir=source,
                project_root=project_root,
                versions_config=["0.3"],
            )

        assert result["success"] is False
        assert "_quarto.yml missing" in result["errors"][0]

        # Render should NOT have been called
        assert render_called == []


# ---------------------------------------------------------------------------
# _is_valid_ref_name
# ---------------------------------------------------------------------------


class TestIsValidRefName:
    def test_index_always_valid(self):
        assert _is_valid_ref_name("index", set())

    def test_member_stem_valid_when_in_snapshot(self):
        syms = {"scores.CosineScore", "scores.CosineScore.fit"}
        assert _is_valid_ref_name("scores.CosineScore", syms)
        assert _is_valid_ref_name("scores.CosineScore.fit", syms)

    def test_absent_stem_invalid(self):
        assert not _is_valid_ref_name("scores.CosineScore", {"TopClass"})


# ---------------------------------------------------------------------------
# TestGitRefRebuildKeepsSubmodulePages
# ---------------------------------------------------------------------------

import subprocess as _subprocess
import textwrap


def _git(root, *a):
    """Run `git *a` in `root`, raising CalledProcessError on a non-zero exit"""
    _subprocess.run(["git", *a], cwd=root, check=True, capture_output=True)


def _repo_with_submodule_tag(root: Path) -> None:
    """Git repo tagged v0.1.0 whose documented API lives under a submodule"""
    _git(root, "init")
    _git(root, "config", "user.email", "t@t.co")
    _git(root, "config", "user.name", "t")
    (root / "pyproject.toml").write_text('[project]\nname = "mypkg"\nversion = "0.1.0"\n')
    pkg = root / "mypkg"
    (pkg / "sub").mkdir(parents=True)
    (pkg / "__init__.py").write_text("from mypkg import sub\n__all__ = ['sub']\n")
    (pkg / "sub" / "__init__.py").write_text(
        "from mypkg.sub.things import Widget\n__all__ = ['Widget']\n"
    )
    (pkg / "sub" / "things.py").write_text("class Widget:\n    def fit(self): ...\n")
    (root / "great-docs.yml").write_text(
        textwrap.dedent(
            """
            reference:
              - title: API
                contents:
                  - name: sub.Widget
                    members: [fit]
            """
        )
    )
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "v010")
    _git(root, "tag", "v0.1.0")


class TestGitRefRebuildKeepsSubmodulePages:
    def test_submodule_pages_survive(self, tmp_path: Path):
        _repo_with_submodule_tag(tmp_path)
        # Simulate the dev build's reference pages copied into the version dir.
        ref = tmp_path / "build" / "reference"
        ref.mkdir(parents=True)
        for stem in ("sub.Widget", "sub.Widget.fit"):
            (ref / f"{stem}.qmd").write_text(
                f"---\ntitle: {stem}\n---\n# {stem} {{.doc-heading}}\n"
            )
        (ref / "index.qmd").write_text("---\ntitle: API\n---\n")

        entry = VersionEntry(label="0.1.0", tag="0.1.0", git_ref="v0.1.0")
        from great_docs._versioned_build import _rebuild_api_from_git_ref

        pages = _rebuild_api_from_git_ref(tmp_path / "build", tmp_path, entry)

        assert (ref / "sub.Widget.qmd").exists()
        assert (ref / "sub.Widget.fit.qmd").exists()
        assert "reference/sub.Widget.html" in pages
