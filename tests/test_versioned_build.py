from __future__ import annotations

import json
from pathlib import Path

import pytest

from great_docs._api_diff import ApiSnapshot, ParameterInfo, SymbolInfo
from great_docs._versioned_build import (
    _compute_excluded_section_dirs,
    _in_excluded_section,
    _merge_tree,
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
        status_path.write_text(
            json.dumps({"page_statuses": {}, "definitions": {}})
        )
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
# Snapshot cache path
# ---------------------------------------------------------------------------


class TestSnapshotCachePath:
    def test_cache_path(self, tmp_path: Path):
        path = _snapshot_cache_path(tmp_path, "v0.3.0")
        assert path == tmp_path / ".great-docs-cache" / "snapshots" / "v0.3.0.json"
