from __future__ import annotations

import pytest

from great_docs._versioning import (
    BADGE_EXPIRY_NEVER,
    BadgeExpiry,
    VersionEntry,
    build_version_map,
    evaluate_version_expr,
    extract_page_versions,
    get_latest_version,
    is_badge_expired,
    page_matches_version,
    parse_badge_expiry,
    parse_versions_config,
    process_version_fences,
)


# ---------------------------------------------------------------------------
# parse_versions_config
# ---------------------------------------------------------------------------


class TestParseVersionsConfig:
    def test_minimal_string_list(self):
        result = parse_versions_config(["0.3", "0.2", "0.1"])
        assert len(result) == 3
        assert result[0].tag == "0.3"
        assert result[0].label == "0.3"
        assert result[0]._index == 0
        assert result[2].tag == "0.1"
        assert result[2]._index == 2

    def test_first_non_prerelease_becomes_latest(self):
        result = parse_versions_config(["0.3", "0.2", "0.1"])
        assert result[0].latest is True
        assert result[1].latest is False

    def test_prerelease_first_skipped_for_auto_latest(self):
        result = parse_versions_config(
            [
                {"tag": "dev", "label": "dev", "prerelease": True},
                {"tag": "0.3", "label": "0.3.0"},
                {"tag": "0.2", "label": "0.2.0"},
            ]
        )
        assert result[0].latest is False  # dev is prerelease
        assert result[1].latest is True  # 0.3 auto-selected

    def test_explicit_latest_honored(self):
        result = parse_versions_config(
            [
                {"tag": "0.3", "label": "0.3.0"},
                {"tag": "0.2", "label": "0.2.0", "latest": True},
            ]
        )
        assert result[0].latest is False
        assert result[1].latest is True

    def test_full_dict_form(self):
        result = parse_versions_config(
            [
                {
                    "tag": "dev",
                    "label": "2.0.0-beta",
                    "prerelease": True,
                },
                {
                    "tag": "1.0",
                    "label": "1.0.0",
                    "latest": True,
                    "api_snapshot": "api-snapshots/v1.0.json",
                },
                {
                    "tag": "0.9",
                    "label": "0.9.0",
                    "eol": True,
                    "git_ref": "v0.9.0",
                },
            ]
        )
        assert result[0].prerelease is True
        assert result[1].api_snapshot == "api-snapshots/v1.0.json"
        assert result[2].eol is True
        assert result[2].git_ref == "v0.9.0"

    def test_empty_list_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            parse_versions_config([])

    def test_duplicate_tag_raises(self):
        with pytest.raises(ValueError, match="duplicate tag"):
            parse_versions_config(["0.3", "0.3"])

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="expected a string or dict"):
            parse_versions_config([42])

    def test_dict_missing_tag_and_label_raises(self):
        with pytest.raises(ValueError, match="must have a 'tag' or 'label'"):
            parse_versions_config([{}])

    def test_label_used_as_tag_fallback(self):
        result = parse_versions_config([{"label": "Version 1"}])
        assert result[0].tag == "Version 1"
        assert result[0].label == "Version 1"


class TestGetLatestVersion:
    def test_returns_latest(self):
        versions = parse_versions_config(["0.3", "0.2"])
        assert get_latest_version(versions).tag == "0.3"

    def test_returns_none_when_all_prerelease(self):
        versions = [
            VersionEntry(tag="dev", label="dev", prerelease=True, _index=0),
        ]
        # No entry marked latest
        assert get_latest_version(versions) is None


# ---------------------------------------------------------------------------
# evaluate_version_expr
# ---------------------------------------------------------------------------


class TestEvaluateVersionExpr:
    @pytest.fixture
    def versions(self) -> list[VersionEntry]:
        return parse_versions_config(
            [
                {"tag": "dev", "label": "dev", "prerelease": True},
                {"tag": "0.3", "label": "0.3.0"},
                {"tag": "0.2", "label": "0.2.0"},
                {"tag": "0.1", "label": "0.1.0"},
            ]
        )

    def test_wildcard(self, versions):
        assert evaluate_version_expr("*", "0.2", versions) is True

    def test_exact_match(self, versions):
        assert evaluate_version_expr("0.2", "0.2", versions) is True
        assert evaluate_version_expr("0.2", "0.3", versions) is False

    def test_comma_separated_exact(self, versions):
        assert evaluate_version_expr("0.1,0.2", "0.2", versions) is True
        assert evaluate_version_expr("0.1,0.2", "0.3", versions) is False

    def test_gte(self, versions):
        # >=0.2 means 0.2 and newer (dev, 0.3, 0.2 but not 0.1)
        assert evaluate_version_expr(">=0.2", "dev", versions) is True
        assert evaluate_version_expr(">=0.2", "0.3", versions) is True
        assert evaluate_version_expr(">=0.2", "0.2", versions) is True
        assert evaluate_version_expr(">=0.2", "0.1", versions) is False

    def test_lte(self, versions):
        # <=0.2 means 0.2 and older (0.2, 0.1 but not 0.3, dev)
        assert evaluate_version_expr("<=0.2", "0.1", versions) is True
        assert evaluate_version_expr("<=0.2", "0.2", versions) is True
        assert evaluate_version_expr("<=0.2", "0.3", versions) is False
        assert evaluate_version_expr("<=0.2", "dev", versions) is False

    def test_gt(self, versions):
        assert evaluate_version_expr(">0.2", "0.3", versions) is True
        assert evaluate_version_expr(">0.2", "0.2", versions) is False

    def test_lt(self, versions):
        assert evaluate_version_expr("<0.2", "0.1", versions) is True
        assert evaluate_version_expr("<0.2", "0.2", versions) is False

    def test_range(self, versions):
        # >0.1,<0.3 means only 0.2
        assert evaluate_version_expr(">0.1,<0.3", "0.2", versions) is True
        assert evaluate_version_expr(">0.1,<0.3", "0.1", versions) is False
        assert evaluate_version_expr(">0.1,<0.3", "0.3", versions) is False

    def test_unknown_target(self, versions):
        assert evaluate_version_expr("0.2", "unknown", versions) is False

    def test_unknown_ref_in_expr(self, versions):
        assert evaluate_version_expr(">=9.9", "0.2", versions) is False

    def test_dev_tag(self, versions):
        assert evaluate_version_expr("dev", "dev", versions) is True
        assert evaluate_version_expr("dev", "0.3", versions) is False

    def test_v_prefix_in_expr(self, versions):
        """Tags with v prefix match versions configured without it."""
        assert evaluate_version_expr("v0.2", "0.2", versions) is True
        assert evaluate_version_expr(">=v0.2", "0.3", versions) is True
        assert evaluate_version_expr(">=v0.2", "0.1", versions) is False

    def test_v_prefix_in_target(self, versions):
        """Target tag with v prefix matches configured bare tag."""
        assert evaluate_version_expr("0.2", "v0.2", versions) is True
        assert evaluate_version_expr(">=0.2", "v0.3", versions) is True

    def test_v_prefix_on_configured_tags(self):
        """Bare tags in content match v-prefixed configured tags."""
        vers = parse_versions_config(
            [
                {"tag": "v0.3", "label": "0.3.0"},
                {"tag": "v0.2", "label": "0.2.0"},
                {"tag": "v0.1", "label": "0.1.0"},
            ]
        )
        assert evaluate_version_expr("0.2", "v0.2", vers) is True
        assert evaluate_version_expr(">=0.2", "v0.3", vers) is True
        assert evaluate_version_expr("0.2", "0.2", vers) is True


# ---------------------------------------------------------------------------
# process_version_fences
# ---------------------------------------------------------------------------


class TestProcessVersionFences:
    @pytest.fixture
    def versions(self) -> list[VersionEntry]:
        return parse_versions_config(["0.3", "0.2", "0.1"])

    def test_no_fences_passthrough(self, versions):
        content = "Hello\nWorld\n"
        assert process_version_fences(content, "0.3", versions) == content

    def test_version_only_matching(self, versions):
        content = 'Before\n::: {.version-only versions=">=0.2"}\nInside\n:::\nAfter\n'
        result = process_version_fences(content, "0.3", versions)
        assert "Before" in result
        assert "Inside" in result
        assert "After" in result
        assert "version-only" not in result

    def test_version_only_non_matching(self, versions):
        content = 'Before\n::: {.version-only versions=">=0.2"}\nInside\n:::\nAfter\n'
        result = process_version_fences(content, "0.1", versions)
        assert "Before" in result
        assert "Inside" not in result
        assert "After" in result

    def test_version_except_matching(self, versions):
        content = 'Before\n::: {.version-except versions="0.1"}\nInside\n:::\nAfter\n'
        # 0.3 is not 0.1, so the block is included (excepted from exclusion)
        result = process_version_fences(content, "0.3", versions)
        assert "Inside" in result

    def test_version_except_excluded(self, versions):
        content = 'Before\n::: {.version-except versions="0.1"}\nInside\n:::\nAfter\n'
        # 0.1 matches the except list, so the block is excluded
        result = process_version_fences(content, "0.1", versions)
        assert "Inside" not in result

    def test_nested_fences(self, versions):
        content = (
            '::: {.version-only versions=">=0.2"}\n'
            "Outer\n"
            '::: {.version-only versions="0.3"}\n'
            "Inner\n"
            ":::\n"
            ":::\n"
        )
        # 0.2 matches outer but not inner
        result = process_version_fences(content, "0.2", versions)
        assert "Outer" in result
        assert "Inner" not in result

    def test_nested_excluded_parent(self, versions):
        content = (
            '::: {.version-only versions="0.3"}\n'
            "Outer\n"
            '::: {.version-only versions=">=0.1"}\n'
            "Inner\n"
            ":::\n"
            ":::\n"
        )
        # 0.1 doesn't match outer, so inner is also excluded
        result = process_version_fences(content, "0.1", versions)
        assert "Outer" not in result
        assert "Inner" not in result

    def test_multiple_blocks(self, versions):
        content = (
            '::: {.version-only versions="0.1"}\n'
            "Old content\n"
            ":::\n"
            "\n"
            '::: {.version-only versions=">=0.2"}\n'
            "New content\n"
            ":::\n"
        )
        result = process_version_fences(content, "0.3", versions)
        assert "Old content" not in result
        assert "New content" in result

    def test_version_singular_attribute(self, versions):
        """Support version= as well as versions= for convenience."""
        content = '::: {.version-only version="0.3"}\nInside\n:::\n'
        result = process_version_fences(content, "0.3", versions)
        assert "Inside" in result

    def test_heading_badge_removes_section_for_old_version(self, versions):
        content = (
            "Intro\n"
            "\n"
            "## Feature A [version-badge new 0.2]\n"
            "\n"
            "Feature A content.\n"
            "\n"
            "## Feature B\n"
            "\n"
            "Feature B content.\n"
        )
        result = process_version_fences(content, "0.1", versions)
        assert "Intro" in result
        assert "Feature A" not in result
        assert "Feature A content" not in result
        assert "Feature B" in result
        assert "Feature B content" in result

    def test_heading_badge_keeps_section_for_matching_version(self, versions):
        content = (
            "## Feature A [version-badge new 0.2]\n"
            "\n"
            "Feature A content.\n"
            "\n"
            "## Feature B\n"
        )
        result = process_version_fences(content, "0.3", versions)
        assert "Feature A" in result
        assert "Feature A content" in result
        assert "Feature B" in result

    def test_heading_badge_skips_sub_headings(self, versions):
        content = (
            "## Feature [version-badge new 0.3]\n"
            "\n"
            "### Sub-section\n"
            "\n"
            "Sub content.\n"
            "\n"
            "## Next Section\n"
            "\n"
            "Next content.\n"
        )
        result = process_version_fences(content, "0.1", versions)
        assert "Feature" not in result
        assert "Sub-section" not in result
        assert "Sub content" not in result
        assert "Next Section" in result
        assert "Next content" in result

    def test_heading_badge_consecutive_badges(self, versions):
        """Multiple consecutive badged headings: each triggers its own skip."""
        content = (
            "## A [version-badge new 0.2]\n"
            "\n"
            "A content.\n"
            "\n"
            "## B [version-badge new 0.3]\n"
            "\n"
            "B content.\n"
            "\n"
            "## C\n"
            "\n"
            "C content.\n"
        )
        result = process_version_fences(content, "0.1", versions)
        assert "A content" not in result
        assert "B content" not in result
        assert "C content" in result

        result2 = process_version_fences(content, "0.2", versions)
        assert "A content" in result2
        assert "B content" not in result2
        assert "C content" in result2

    def test_heading_badge_with_explicit_fence(self, versions):
        """Heading badge + explicit fence inside: both are removed cleanly."""
        content = (
            "## Feature [version-badge new 0.2]\n"
            "\n"
            '::: {.version-only versions=">=0.2"}\n'
            "Fenced content.\n"
            ":::\n"
            "\n"
            "## Next\n"
        )
        result = process_version_fences(content, "0.1", versions)
        assert "Feature" not in result
        assert "Fenced content" not in result
        assert "Next" in result

    def test_heading_badge_changed_not_removed(self, versions):
        """changed badges do NOT trigger section removal."""
        content = (
            "## Feature [version-badge changed 0.3]\n"
            "\n"
            "Content here.\n"
            "\n"
            "## Next\n"
        )
        result = process_version_fences(content, "0.1", versions)
        assert "Feature" in result
        assert "Content here" in result

    def test_heading_badge_in_code_block_ignored(self, versions):
        """Heading badges inside code blocks are not processed."""
        content = (
            "```markdown\n"
            "## Feature [version-badge new 0.3]\n"
            "\n"
            "Example text.\n"
            "```\n"
            "\n"
            "After code block.\n"
        )
        result = process_version_fences(content, "0.1", versions)
        assert "Feature" in result
        assert "Example text" in result
        assert "After code block" in result

    def test_heading_badge_skips_over_callout_with_heading(self, versions):
        """A heading inside a ::: callout must not prematurely end the skip."""
        content = (
            "## Feature A [version-badge new 0.3]\n"
            "\n"
            "Feature A content.\n"
            "\n"
            "::: {.callout-tip}\n"
            "## Pro Tip\n"
            "Tip content here.\n"
            ":::\n"
            "\n"
            "More feature A content.\n"
            "\n"
            "## Feature B\n"
            "\n"
            "Feature B content.\n"
        )
        result = process_version_fences(content, "0.1", versions)
        # Feature A and everything inside it (including the callout) should be gone
        assert "Feature A" not in result
        assert "Pro Tip" not in result
        assert "Tip content" not in result
        assert ":::" not in result
        # Feature B should survive
        assert "## Feature B" in result
        assert "Feature B content" in result

    def test_heading_badge_keeps_callout_for_matching_version(self, versions):
        """Callout with heading preserved when version matches."""
        content = (
            "## Feature A [version-badge new 0.3]\n"
            "\n"
            "::: {.callout-tip}\n"
            "## Pro Tip\n"
            "Tip content.\n"
            ":::\n"
            "\n"
            "## Next Section\n"
        )
        result = process_version_fences(content, "0.3", versions)
        assert "Feature A" in result
        assert "Pro Tip" in result
        assert "Tip content" in result
        assert ":::" in result

    def test_heading_badge_nested_divs_in_skip(self, versions):
        """Nested ::: divs inside a skipped section are fully consumed."""
        content = (
            "## New Feature [version-badge new 0.3]\n"
            "\n"
            ":::: {.panel}\n"
            "::: {.callout-note}\n"
            "## Note Title\n"
            "Nested content.\n"
            ":::\n"
            "::::\n"
            "\n"
            "## After\n"
            "\n"
            "Kept.\n"
        )
        result = process_version_fences(content, "0.1", versions)
        assert "New Feature" not in result
        assert "Note Title" not in result
        assert "Nested content" not in result
        assert "## After" in result
        assert "Kept" in result


# ---------------------------------------------------------------------------
# Page-level version scoping
# ---------------------------------------------------------------------------


class TestExtractPageVersions:
    def test_no_frontmatter(self):
        assert extract_page_versions("# Hello\nWorld\n") is None

    def test_no_versions_key(self):
        content = '---\ntitle: "Hello"\n---\nBody\n'
        assert extract_page_versions(content) is None

    def test_inline_list(self):
        content = '---\ntitle: "Hello"\nversions: ["0.3", "dev"]\n---\nBody\n'
        result = extract_page_versions(content)
        assert result == ["0.3", "dev"]

    def test_inline_list_unquoted(self):
        content = "---\ntitle: Hello\nversions: [0.3, dev]\n---\nBody\n"
        result = extract_page_versions(content)
        assert result == ["0.3", "dev"]

    def test_block_list(self):
        content = '---\ntitle: Hello\nversions:\n  - "0.3"\n  - "dev"\n---\nBody\n'
        result = extract_page_versions(content)
        assert result == ["0.3", "dev"]

    def test_empty_inline_list(self):
        content = "---\nversions: []\n---\nBody\n"
        assert extract_page_versions(content) is None

    def test_scalar_string_expression(self):
        content = '---\nversions: ">=0.5"\n---\nBody\n'
        result = extract_page_versions(content)
        assert result == [">=0.5"]

    def test_scalar_string_single_quotes(self):
        content = "---\nversions: '>=0.3'\n---\nBody\n"
        result = extract_page_versions(content)
        assert result == [">=0.3"]


_EXPR_VERSIONS = [
    VersionEntry(tag="dev", label="dev", prerelease=True, _index=0),
    VersionEntry(tag="0.8", label="0.8", latest=True, _index=1),
    VersionEntry(tag="0.7", label="0.7", _index=2),
    VersionEntry(tag="0.6", label="0.6", _index=3),
    VersionEntry(tag="0.5", label="0.5", _index=4),
]


class TestPageMatchesVersion:
    def test_no_versions_key_matches_all(self):
        content = '---\ntitle: "Hello"\n---\nBody\n'
        assert page_matches_version(content, "0.3") is True
        assert page_matches_version(content, "0.1") is True

    def test_scoped_page_matches(self):
        content = '---\nversions: ["0.3", "dev"]\n---\nBody\n'
        assert page_matches_version(content, "0.3") is True
        assert page_matches_version(content, "dev") is True
        assert page_matches_version(content, "0.1") is False

    def test_expression_gte_with_versions(self):
        content = '---\nversions: ">=0.7"\n---\nBody\n'
        assert page_matches_version(content, "dev", _EXPR_VERSIONS) is True
        assert page_matches_version(content, "0.8", _EXPR_VERSIONS) is True
        assert page_matches_version(content, "0.7", _EXPR_VERSIONS) is True
        assert page_matches_version(content, "0.6", _EXPR_VERSIONS) is False
        assert page_matches_version(content, "0.5", _EXPR_VERSIONS) is False

    def test_expression_in_inline_list(self):
        content = '---\nversions: [">=0.6"]\n---\nBody\n'
        assert page_matches_version(content, "0.8", _EXPR_VERSIONS) is True
        assert page_matches_version(content, "0.6", _EXPR_VERSIONS) is True
        assert page_matches_version(content, "0.5", _EXPR_VERSIONS) is False

    def test_bare_tags_still_work_with_versions(self):
        content = '---\nversions: ["0.7", "dev"]\n---\nBody\n'
        assert page_matches_version(content, "0.7", _EXPR_VERSIONS) is True
        assert page_matches_version(content, "dev", _EXPR_VERSIONS) is True
        assert page_matches_version(content, "0.8", _EXPR_VERSIONS) is False

    def test_bare_tags_without_versions_param(self):
        """Backward compat: without versions param, plain 'in' check is used."""
        content = '---\nversions: ["0.7", "dev"]\n---\nBody\n'
        assert page_matches_version(content, "0.7") is True
        assert page_matches_version(content, "0.5") is False


# ---------------------------------------------------------------------------
# build_version_map
# ---------------------------------------------------------------------------


class TestBuildVersionMap:
    def test_basic_manifest(self):
        versions = parse_versions_config(["0.3", "0.2", "0.1"])
        pages = {
            "0.3": ["user-guide/index.html", "reference/index.html"],
            "0.2": ["user-guide/index.html"],
            "0.1": ["user-guide/index.html"],
        }
        result = build_version_map(versions, pages)

        assert len(result["versions"]) == 3

        # Latest version should have empty path_prefix
        v03 = result["versions"][0]
        assert v03["tag"] == "0.3"
        assert v03["path_prefix"] == ""
        assert v03["latest"] is True

        # Other versions have v/ prefix
        v02 = result["versions"][1]
        assert v02["path_prefix"] == "v/0.2"

        # Pages map
        assert result["pages"]["user-guide/index.html"] == ["0.3", "0.2", "0.1"]
        assert result["pages"]["reference/index.html"] == ["0.3"]

    def test_with_fallbacks(self):
        versions = parse_versions_config(["0.3"])
        pages = {"0.3": ["user-guide/index.html"]}
        fallbacks = {"user-guide/advanced.html": "user-guide/index.html"}
        result = build_version_map(versions, pages, fallbacks=fallbacks)
        assert result["fallbacks"] == fallbacks

    def test_no_fallbacks_key_when_none(self):
        versions = parse_versions_config(["0.3"])
        pages = {"0.3": ["user-guide/index.html"]}
        result = build_version_map(versions, pages)
        assert "fallbacks" not in result

    def test_prerelease_and_eol_flags(self):
        versions = parse_versions_config(
            [
                {"tag": "dev", "label": "dev", "prerelease": True},
                {"tag": "0.3", "label": "0.3.0"},
                {"tag": "0.1", "label": "0.1.0", "eol": True},
            ]
        )
        pages = {"dev": [], "0.3": [], "0.1": []}
        result = build_version_map(versions, pages)

        assert result["versions"][0]["prerelease"] is True
        assert result["versions"][2]["eol"] is True
        # Non-flagged version should not have the keys
        assert "prerelease" not in result["versions"][1]
        assert "eol" not in result["versions"][1]


# ---------------------------------------------------------------------------
# parse_badge_expiry
# ---------------------------------------------------------------------------


class TestParseBadgeExpiry:
    def test_none(self):
        assert parse_badge_expiry(None) is BADGE_EXPIRY_NEVER

    def test_never_string(self):
        result = parse_badge_expiry("never")
        assert result.mode == "never"

    def test_never_case_insensitive(self):
        assert parse_badge_expiry("Never").mode == "never"

    def test_releases(self):
        result = parse_badge_expiry("3 releases")
        assert result.mode == "releases"
        assert result.value == 3

    def test_release_singular(self):
        result = parse_badge_expiry("1 release")
        assert result.mode == "releases"
        assert result.value == 1

    def test_minor_releases(self):
        result = parse_badge_expiry("2 minor releases")
        assert result.mode == "minor_releases"
        assert result.value == 2

    def test_days(self):
        result = parse_badge_expiry("180 days")
        assert result.mode == "days"
        assert result.value == 180

    def test_day_singular(self):
        result = parse_badge_expiry("1 day")
        assert result.mode == "days"
        assert result.value == 1

    def test_iso_date(self):
        result = parse_badge_expiry("2026-06-01")
        assert result.mode == "date"
        assert result.value == "2026-06-01"

    def test_version_tag(self):
        result = parse_badge_expiry("0.8")
        assert result.mode == "version"
        assert result.value == "0.8"

    def test_version_tag_with_v_prefix(self):
        result = parse_badge_expiry("v1.2")
        assert result.mode == "version"
        assert result.value == "v1.2"


# ---------------------------------------------------------------------------
# is_badge_expired
# ---------------------------------------------------------------------------


class TestIsBadgeExpired:
    @pytest.fixture
    def versions(self) -> list[VersionEntry]:
        return parse_versions_config(
            [
                {"tag": "dev", "label": "dev", "prerelease": True},
                {"tag": "0.7", "label": "0.7.0"},
                {"tag": "0.6", "label": "0.6.0"},
                {"tag": "0.5", "label": "0.5.0"},
                {"tag": "0.4", "label": "0.4.0"},
                {"tag": "0.3", "label": "0.3.0"},
            ]
        )

    def test_never_not_expired(self, versions):
        assert is_badge_expired("0.3", versions[1], versions, BADGE_EXPIRY_NEVER) is False

    # --- releases mode ---

    def test_releases_not_expired_same_version(self, versions):
        expiry = BadgeExpiry(mode="releases", value=3)
        target = versions[5]  # 0.3
        assert is_badge_expired("0.3", target, versions, expiry) is False

    def test_releases_not_expired_within_window(self, versions):
        expiry = BadgeExpiry(mode="releases", value=3)
        target = versions[3]  # 0.5 — 2 releases after 0.3
        assert is_badge_expired("0.3", target, versions, expiry) is False

    def test_releases_expired_at_boundary(self, versions):
        expiry = BadgeExpiry(mode="releases", value=3)
        target = versions[2]  # 0.6 — 3 releases after 0.3
        assert is_badge_expired("0.3", target, versions, expiry) is True

    def test_releases_expired_past_boundary(self, versions):
        expiry = BadgeExpiry(mode="releases", value=3)
        target = versions[1]  # 0.7 — 4 releases after 0.3
        assert is_badge_expired("0.3", target, versions, expiry) is True

    # --- minor_releases mode ---

    def test_minor_releases_skips_prerelease(self, versions):
        # dev is prerelease, so only 0.7-0.3 count
        expiry = BadgeExpiry(mode="minor_releases", value=3)
        target = versions[2]  # 0.6 — 3 non-pre releases after 0.3
        assert is_badge_expired("0.3", target, versions, expiry) is True

    def test_minor_releases_not_expired(self, versions):
        expiry = BadgeExpiry(mode="minor_releases", value=3)
        target = versions[3]  # 0.5 — 2 non-pre releases after 0.3
        assert is_badge_expired("0.3", target, versions, expiry) is False

    def test_minor_releases_prerelease_target_falls_back_to_latest(self, versions):
        # dev (prerelease) should behave like the latest non-prerelease (0.7)
        expiry = BadgeExpiry(mode="minor_releases", value=3)
        target_dev = versions[0]  # dev
        target_07 = versions[1]  # 0.7
        assert is_badge_expired("0.3", target_dev, versions, expiry) == is_badge_expired(
            "0.3", target_07, versions, expiry
        )

    # --- version mode ---

    def test_version_not_expired_before_threshold(self, versions):
        expiry = BadgeExpiry(mode="version", value="0.6")
        target = versions[3]  # 0.5
        assert is_badge_expired("0.3", target, versions, expiry) is False

    def test_version_expired_at_threshold(self, versions):
        expiry = BadgeExpiry(mode="version", value="0.6")
        target = versions[2]  # 0.6
        assert is_badge_expired("0.3", target, versions, expiry) is True

    def test_version_expired_after_threshold(self, versions):
        expiry = BadgeExpiry(mode="version", value="0.6")
        target = versions[1]  # 0.7
        assert is_badge_expired("0.3", target, versions, expiry) is True

    # --- date mode ---

    def test_date_not_expired_future(self, versions):
        expiry = BadgeExpiry(mode="date", value="2099-01-01")
        assert is_badge_expired("0.3", versions[1], versions, expiry) is False

    def test_date_expired_past(self, versions):
        expiry = BadgeExpiry(mode="date", value="2020-01-01")
        assert is_badge_expired("0.3", versions[1], versions, expiry) is True

    # --- days mode ---

    def test_days_no_released_date(self, versions):
        expiry = BadgeExpiry(mode="days", value=90)
        # No released date → fail open
        assert is_badge_expired("0.3", versions[1], versions, expiry) is False

    def test_days_expired(self):
        versions = parse_versions_config(
            [
                {"tag": "0.5", "label": "0.5.0"},
                {"tag": "0.3", "label": "0.3.0", "released": "2020-01-01"},
            ]
        )
        expiry = BadgeExpiry(mode="days", value=90)
        assert is_badge_expired("0.3", versions[0], versions, expiry) is True

    def test_days_not_expired(self):
        versions = parse_versions_config(
            [
                {"tag": "0.5", "label": "0.5.0"},
                {"tag": "0.3", "label": "0.3.0", "released": "2099-01-01"},
            ]
        )
        expiry = BadgeExpiry(mode="days", value=90)
        assert is_badge_expired("0.3", versions[0], versions, expiry) is False

    # --- unknown badge version ---

    def test_unknown_badge_version(self, versions):
        expiry = BadgeExpiry(mode="releases", value=1)
        assert is_badge_expired("9.9", versions[1], versions, expiry) is False

    # --- changed/deprecated not affected (tested via expand_version_badges) ---
