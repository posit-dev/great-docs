from __future__ import annotations

import pytest

from great_docs._versioning import (
    _resolve_version_str,
    _parse_version_tuple,
    _find_entry,
    BADGE_EXPIRY_NEVER,
    BadgeExpiry,
    VersionEntry,
    build_version_map,
    evaluate_version_expr,
    extract_page_versions,
    get_latest_version,
    is_badge_expired,
    is_page_upcoming,
    is_page_upcoming_for_version,
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

    def test_version_field_resolves_dev_tag(self):
        """The version field maps a non-numeric tag to a semantic version."""
        vers = parse_versions_config(
            [
                {"tag": "dev", "label": "0.8 (dev)", "version": "0.8", "prerelease": True},
                {"tag": "0.7", "label": "0.7.0", "latest": True},
                {"tag": "0.6", "label": "0.6.0"},
            ]
        )
        # >=0.8 should match dev (via version field) but not 0.7 or 0.6
        assert evaluate_version_expr(">=0.8", "dev", vers) is True
        assert evaluate_version_expr(">=0.8", "0.7", vers) is False
        assert evaluate_version_expr(">=0.8", "0.6", vers) is False

    def test_version_field_exact_match(self):
        vers = parse_versions_config(
            [
                {"tag": "dev", "version": "0.8", "prerelease": True},
                {"tag": "0.7", "latest": True},
            ]
        )
        assert evaluate_version_expr("0.8", "dev", vers) is True
        assert evaluate_version_expr("0.8", "0.7", vers) is False

    def test_version_field_in_range(self):
        vers = parse_versions_config(
            [
                {"tag": "dev", "version": "0.8", "prerelease": True},
                {"tag": "0.7", "latest": True},
                {"tag": "0.6"},
            ]
        )
        # dev is 0.8 → >0.6,<0.8 should not match dev (0.8 is not <0.8)
        assert evaluate_version_expr(">0.6,<0.8", "dev", vers) is False
        assert evaluate_version_expr(">0.6,<0.8", "0.7", vers) is True

    def test_ref_version_not_in_list_gte(self):
        """>=0.5 should match 0.9 even when 0.5 is not in the versions list."""
        vers = parse_versions_config(
            [
                {"tag": "dev", "version": "0.10", "prerelease": True},
                {"tag": "0.9", "latest": True},
            ]
        )
        assert evaluate_version_expr(">=0.5", "0.9", vers) is True
        assert evaluate_version_expr(">=0.5", "dev", vers) is True

    def test_ref_version_not_in_list_lte(self):
        """<=0.5 should NOT match 0.9 when 0.5 is absent."""
        vers = parse_versions_config(
            [
                {"tag": "dev", "version": "0.10", "prerelease": True},
                {"tag": "0.9", "latest": True},
            ]
        )
        assert evaluate_version_expr("<=0.5", "0.9", vers) is False
        assert evaluate_version_expr("<=0.5", "dev", vers) is False

    def test_ref_version_not_in_list_gt(self):
        vers = parse_versions_config(
            [
                {"tag": "dev", "version": "0.10", "prerelease": True},
                {"tag": "0.9", "latest": True},
            ]
        )
        assert evaluate_version_expr(">0.5", "0.9", vers) is True
        assert evaluate_version_expr(">0.9", "0.9", vers) is False

    def test_ref_version_not_in_list_lt(self):
        vers = parse_versions_config(
            [
                {"tag": "dev", "version": "0.10", "prerelease": True},
                {"tag": "0.9", "latest": True},
            ]
        )
        assert evaluate_version_expr("<0.5", "0.9", vers) is False
        assert evaluate_version_expr("<1.0", "0.9", vers) is True

    def test_ref_version_not_in_list_exact(self):
        """Exact match for absent version should fail."""
        vers = parse_versions_config(
            [
                {"tag": "dev", "version": "0.10", "prerelease": True},
                {"tag": "0.9", "latest": True},
            ]
        )
        assert evaluate_version_expr("=0.5", "0.9", vers) is False
        assert evaluate_version_expr("=0.9", "0.9", vers) is True

    def test_ref_version_not_in_list_range(self):
        """Range with one absent endpoint should still work."""
        vers = parse_versions_config(
            [
                {"tag": "dev", "version": "0.10", "prerelease": True},
                {"tag": "0.9", "latest": True},
            ]
        )
        # >=0.5,<=0.9 should match 0.9
        assert evaluate_version_expr(">=0.5,<=0.9", "0.9", vers) is True
        # >=0.5,<0.9 should NOT match 0.9
        assert evaluate_version_expr(">=0.5,<0.9", "0.9", vers) is False

    def test_three_part_version_in_expr(self):
        """>=0.11.0 should work the same as >=0.11 when target is 0.11."""
        vers = parse_versions_config(
            [
                {"tag": "dev", "version": "0.12", "prerelease": True},
                {"tag": "0.11", "latest": True},
                {"tag": "0.10"},
            ]
        )
        assert evaluate_version_expr(">=0.11.0", "0.11", vers) is True
        assert evaluate_version_expr(">=0.11.0", "dev", vers) is True
        assert evaluate_version_expr(">=0.11.0", "0.10", vers) is False
        # Equality with different segment counts
        assert evaluate_version_expr("=0.11.0", "0.11", vers) is True
        assert evaluate_version_expr(">=0.10.0", "0.11", vers) is True


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
        content = "## Feature A [version-badge new 0.2]\n\nFeature A content.\n\n## Feature B\n"
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
        content = "## Feature [version-badge changed 0.3]\n\nContent here.\n\n## Next\n"
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
# is_page_upcoming
# ---------------------------------------------------------------------------


class TestIsPageUpcoming:
    @pytest.fixture
    def versions(self) -> list[VersionEntry]:
        return parse_versions_config(
            [
                {"tag": "dev", "label": "0.8.0", "prerelease": True},
                {"tag": "0.7", "label": "0.7.0", "latest": True},
                {"tag": "0.6", "label": "0.6.0"},
            ]
        )

    def test_scoped_to_prerelease_only(self, versions):
        content = '---\nversions: ["dev"]\n---\nBody\n'
        assert is_page_upcoming(content, versions) is True

    def test_scoped_to_stable_not_upcoming(self, versions):
        content = '---\nversions: ["0.7"]\n---\nBody\n'
        assert is_page_upcoming(content, versions) is False

    def test_scoped_to_mixed_not_upcoming(self, versions):
        content = '---\nversions: ["dev", "0.7"]\n---\nBody\n'
        assert is_page_upcoming(content, versions) is False

    def test_no_versions_key_not_upcoming(self, versions):
        content = '---\ntitle: "Hello"\n---\nBody\n'
        assert is_page_upcoming(content, versions) is False

    def test_expression_matching_only_prerelease(self, versions):
        """An expression that resolves to only prerelease entries."""
        # dev is index 0, so >0.7 only matches dev
        content = '---\nversions: ">0.7"\n---\nBody\n'
        assert is_page_upcoming(content, versions) is True

    def test_expression_matching_stable_too(self, versions):
        content = '---\nversions: ">=0.7"\n---\nBody\n'
        assert is_page_upcoming(content, versions) is False

    def test_no_matched_versions_returns_false(self):
        """When page versions don't match any entry, returns False."""
        versions = _versions("0.9", "0.8")

        # Page targets "0.5" which doesn't exist
        content = "---\nversions:\n  - 0.5\n---\n# Content\n"

        assert is_page_upcoming(content, versions) is False

    def test_all_prerelease_returns_true(self):
        """Page matching only prerelease versions is upcoming."""
        versions = [
            VersionEntry(tag="dev", label="dev", prerelease=True, _index=0),
            VersionEntry(tag="0.9", label="0.9", _index=1),
        ]
        content = "---\nversions:\n  - dev\n---\n# Content\n"

        assert is_page_upcoming(content, versions) is True

    def test_mixed_versions_not_upcoming(self):
        """Page matching both release and prerelease is not upcoming."""
        versions = [
            VersionEntry(tag="dev", label="dev", prerelease=True, _index=0),
            VersionEntry(tag="0.9", label="0.9", _index=1),
        ]
        content = "---\nversions:\n  - dev\n  - 0.9\n---\n# Content\n"

        assert is_page_upcoming(content, versions) is False


class TestIsPageUpcomingForVersion:
    @pytest.fixture
    def versions(self) -> list[VersionEntry]:
        return parse_versions_config(
            [
                {"tag": "dev", "label": "0.8.0", "version": "0.8", "prerelease": True},
                {"tag": "0.7", "label": "0.7.0", "latest": True},
                {"tag": "0.6", "label": "0.6.0"},
            ]
        )

    def test_older_build_is_upcoming(self, versions):
        # Building 0.7, upcoming: "0.8" → 0.7 is older → True
        assert is_page_upcoming_for_version("0.8", "0.7", versions) is True

    def test_older_build_0_6_is_upcoming(self, versions):
        assert is_page_upcoming_for_version("0.8", "0.6", versions) is True

    def test_same_version_not_upcoming(self, versions):
        # Building dev (version 0.8), upcoming: "0.8" → same → False
        assert is_page_upcoming_for_version("0.8", "dev", versions) is False

    def test_newer_build_not_upcoming(self, versions):
        # If we ever build something newer than 0.8, it wouldn't be upcoming
        vers = parse_versions_config(
            [
                {"tag": "0.9", "label": "0.9.0"},
                {"tag": "0.8", "label": "0.8.0"},
                {"tag": "0.7", "label": "0.7.0"},
            ]
        )
        assert is_page_upcoming_for_version("0.8", "0.9", vers) is False

    def test_unknown_upcoming_version(self, versions):
        # Unknown version tag → fail-open (not upcoming)
        assert is_page_upcoming_for_version("9.9", "0.7", versions) is False

    def test_upcoming_with_dev_tag_directly(self, versions):
        # upcoming: "dev" targeting 0.7 → 0.7 is older than dev → True
        assert is_page_upcoming_for_version("dev", "0.7", versions) is True


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

    def test_minor_releases_badge_not_found(self):
        """minor_releases mode returns False when badge version not resolved."""
        versions = _versions("0.9", "0.8")
        target = versions[0]
        expiry = BadgeExpiry(mode="minor_releases", value=1)

        # Badge version "unknown" won't resolve
        assert is_badge_expired("unknown", target, versions, expiry) is False

    def test_date_mode_invalid_date(self):
        """date mode with invalid date returns False."""
        versions = _versions("0.9")
        target = versions[0]
        expiry = BadgeExpiry(mode="date", value="not-a-date")

        assert is_badge_expired("0.9", target, versions, expiry) is False

    def test_date_mode_future_date(self):
        """date mode with future date returns False."""
        versions = _versions("0.9")
        target = versions[0]
        expiry = BadgeExpiry(mode="date", value="2099-01-01")

        assert is_badge_expired("0.9", target, versions, expiry) is False

    def test_date_mode_past_date(self):
        """date mode with past date returns True."""
        versions = _versions("0.9")
        target = versions[0]
        expiry = BadgeExpiry(mode="date", value="2020-01-01")

        assert is_badge_expired("0.9", target, versions, expiry) is True

    def test_days_mode_invalid_release_date(self):
        """days mode with unparseable released date returns False."""
        versions = [VersionEntry(tag="0.9", label="0.9", released="not-a-date", _index=0)]
        target = versions[0]
        expiry = BadgeExpiry(mode="days", value=1)

        assert is_badge_expired("0.9", target, versions, expiry) is False

    def test_days_mode_recently_released(self):
        """days mode returns False when badge released recently."""
        versions = [VersionEntry(tag="0.9", label="0.9", released="2099-01-01", _index=0)]
        target = versions[0]
        expiry = BadgeExpiry(mode="days", value=30)

        assert is_badge_expired("0.9", target, versions, expiry) is False

    def test_days_mode_old_release(self):
        """days mode returns True when badge released long ago."""
        versions = [VersionEntry(tag="0.9", label="0.9", released="2020-01-01", _index=0)]
        target = versions[0]
        expiry = BadgeExpiry(mode="days", value=30)

        assert is_badge_expired("0.9", target, versions, expiry) is True

    def test_version_mode_threshold_not_found(self):
        """version mode returns False when threshold version not resolved."""
        versions = _versions("0.9", "0.8")
        target = versions[0]
        expiry = BadgeExpiry(mode="version", value="nonexistent")

        assert is_badge_expired("0.9", target, versions, expiry) is False

    def test_unknown_mode_returns_false(self):
        """Unknown expiry mode falls through to return False."""
        versions = _versions("0.9")
        target = versions[0]
        expiry = BadgeExpiry(mode="unknown_mode", value=1)

        assert is_badge_expired("0.9", target, versions, expiry) is False


# _find_entry fallback paths


def _versions(*tags, **kwargs):
    """Build a list of VersionEntry objects from tag strings."""
    entries = []
    for i, tag in enumerate(tags):
        if isinstance(tag, dict):
            entries.append(VersionEntry(_index=i, **tag))
        else:
            entries.append(VersionEntry(tag=tag, label=tag, _index=i, **kwargs))
    return entries


# _parse_version_tuple returns None on non-numeric


class TestParseVersionTuple:
    def test_valid_version(self):
        assert _parse_version_tuple("1.2.3") == (1, 2, 3)

    def test_version_with_v_prefix(self):
        assert _parse_version_tuple("v0.5") == (0, 5)

    def test_non_numeric_returns_none(self):
        """Non-numeric version string returns None."""
        assert _parse_version_tuple("dev") is None

    def test_partial_non_numeric_returns_none(self):
        assert _parse_version_tuple("1.2.beta") is None


# _resolve_version_str — alt prefix fallback


class TestResolveVersionStr:
    def test_exact_match(self):
        versions = _versions("0.9", "0.8")

        assert _resolve_version_str("0.9", versions) == "0.9"

    def test_v_prefix_fallback(self):
        """Tag with 'v' prefix tries without it."""
        versions = _versions("0.9", "0.8")

        # Looking for "v0.9" which has alt "0.9"
        assert _resolve_version_str("v0.9", versions) == "0.9"

    def test_no_match_returns_tag(self):
        """When no version matches, returns the original tag."""
        versions = _versions("0.9", "0.8")

        assert _resolve_version_str("unknown", versions) == "unknown"

    def test_version_field_match(self):
        """Match via the version field of a VersionEntry."""
        versions = [
            VersionEntry(tag="dev", label="dev", version="0.10", _index=0),
            VersionEntry(tag="0.9", label="0.9", _index=1),
        ]

        assert _resolve_version_str("0.10", versions) == "0.10"


# evaluate_version_expr edge cases


class TestEvaluateVersionExprEdgeCases:
    def test_or_mode_no_regex_match_skipped(self):
        """In OR mode, empty part doesn't match regex and is skipped."""
        versions = _versions("0.9", "0.8", "0.7")

        # Leading comma → empty part first, then "0.9" matches
        result = evaluate_version_expr(",0.9", "0.9", versions)

        assert result is True

    def test_and_mode_no_regex_match_returns_false(self):
        """In AND mode, empty part doesn't match regex → returns False."""
        versions = _versions("0.9", "0.8", "0.7")

        # ">=0.8," has trailing comma → empty part in AND mode → return False
        result = evaluate_version_expr(">=0.8,", "0.9", versions)

        assert result is False

    def test_and_mode_equality_mismatch(self):
        """AND mode equality check returns False when idx differs."""
        versions = _versions("0.9", "0.8", "0.7")

        # Bare "0.8" in AND context (mixed with operator): target=0.9, ref=0.8 → mismatch
        result = evaluate_version_expr("=0.8", "0.9", versions)

        assert result is False

    def test_semver_fallback_unparseable_returns_false(self):
        """When ref version is not in list and tag can't be parsed, returns False."""
        versions = _versions("dev", "0.9")
        versions[0].version = None

        # ">=alpha" — "alpha" not in versions, can't parse as tuple
        result = evaluate_version_expr(">=alpha", "dev", versions)

        assert result is False

    def test_semver_fallback_gt_operator(self):
        """Semver fallback with '>' operator."""
        # Only 0.9 configured; 0.5 not in the list, so semver fallback kicks in
        versions = _versions("0.9")

        # target=0.9, ref=0.5, op=">": 0.9 > 0.5 is True → constraint satisfied
        result = evaluate_version_expr(">0.5", "0.9", versions)

        assert result is True

    def test_semver_fallback_gt_fails(self):
        """Semver fallback '>' returns False when target <= ref."""
        versions = _versions("0.5")
        result = evaluate_version_expr(">0.9", "0.5", versions)

        assert result is False


# is_badge_expired branches


class TestFindEntry:
    def test_exact_match(self):
        versions = _versions("0.9", "0.8")

        assert _find_entry("0.9", versions) == versions[0]

    def test_v_prefix_fallback(self):
        """Finds entry by stripping/adding 'v' prefix."""
        versions = _versions("v1.0", "v0.9")
        result = _find_entry("1.0", versions)

        assert result == versions[0]

    def test_version_field_fallback(self):
        """Finds entry via the version field."""
        versions = [
            VersionEntry(tag="dev", label="dev", version="0.10", _index=0),
            VersionEntry(tag="0.9", label="0.9", _index=1),
        ]
        result = _find_entry("0.10", versions)

        assert result == versions[0]

    def test_not_found_returns_none(self):
        versions = _versions("0.9")

        assert _find_entry("nonexistent", versions) is None


# extract_page_versions — stops at next YAML key


class TestExtractPageVersions:
    def test_stops_at_next_yaml_key(self):
        """Stops reading list items when next top-level key encountered."""
        content = "---\nversions:\n  - 0.9\n  - 0.8\ntitle: Hello\n---\n# Content\n"
        result = extract_page_versions(content)

        assert result == ["0.9", "0.8"]

    def test_no_versions_key_returns_none(self):
        content = "---\ntitle: Hello\n---\n# Content\n"
        result = extract_page_versions(content)

        assert result is None


# is_page_upcoming — no matched versions returns False
