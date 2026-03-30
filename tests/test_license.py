# pyright: reportPrivateUsage=false
"""Tests for the _license module (SPDX data model and HTML generation)."""

import pytest

from great_docs._license import (
    LICENSES,
    LicenseInfo,
    build_license_features_html,
    get_license_info,
)


# ── get_license_info ────────────────────────────────────────────────────


class TestGetLicenseInfo:
    def test_exact_match(self):
        info = get_license_info("MIT")
        assert info is not None
        assert info.spdx_id == "MIT"
        assert info.full_name == "MIT License"

    def test_case_insensitive(self):
        info = get_license_info("mit")
        assert info is not None
        assert info.spdx_id == "MIT"

    def test_apache(self):
        info = get_license_info("Apache-2.0")
        assert info is not None
        assert info.spdx_id == "Apache-2.0"
        assert info.full_name == "Apache License 2.0"

    def test_gpl3_alias(self):
        info = get_license_info("GPL-3.0")
        assert info is not None
        assert info.spdx_id == "GPL-3.0-only"

    def test_gpl3_or_later_alias(self):
        info = get_license_info("GPL-3.0-or-later")
        assert info is not None
        assert info.spdx_id == "GPL-3.0-only"

    def test_bsd_3_clause(self):
        info = get_license_info("BSD-3-Clause")
        assert info is not None
        assert info.spdx_id == "BSD-3-Clause"

    def test_unknown_returns_none(self):
        assert get_license_info("UNKNOWN-LICENSE-XYZ") is None

    def test_empty_string_returns_none(self):
        assert get_license_info("") is None

    def test_all_registered_licenses_have_required_fields(self):
        seen_ids = set()
        for key, info in LICENSES.items():
            # Each alias resolves to a valid LicenseInfo
            assert isinstance(info, LicenseInfo)
            assert info.spdx_id
            assert info.full_name
            seen_ids.add(info.spdx_id)

        # Verify we have a reasonable number of distinct licenses
        assert len(seen_ids) >= 46


# ── LicenseInfo features ───────────────────────────────────────────────


class TestLicenseInfoFeatures:
    def test_mit_permissions(self):
        info = get_license_info("MIT")
        assert "Commercial use" in info.permissions
        assert "Modification" in info.permissions
        assert "Distribution" in info.permissions
        assert "Private use" in info.permissions

    def test_mit_conditions(self):
        info = get_license_info("MIT")
        assert "License and copyright notice" in info.conditions

    def test_mit_limitations(self):
        info = get_license_info("MIT")
        assert "Liability" in info.limitations
        assert "Warranty" in info.limitations

    def test_apache_has_patent_use(self):
        info = get_license_info("Apache-2.0")
        assert "Patent use" in info.permissions
        assert "State changes" in info.conditions

    def test_apache_has_trademark_limitation(self):
        info = get_license_info("Apache-2.0")
        assert "Trademark use" in info.limitations

    def test_gpl3_has_copyleft_conditions(self):
        info = get_license_info("GPL-3.0-only")
        assert "Disclose source" in info.conditions
        assert "Same license" in info.conditions

    def test_unlicense_no_conditions(self):
        info = get_license_info("Unlicense")
        assert info.conditions == []

    def test_cc0_no_conditions(self):
        info = get_license_info("CC0-1.0")
        assert info.conditions == []

    def test_mit0_no_conditions(self):
        info = get_license_info("MIT-0")
        assert info.conditions == []

    def test_agpl_has_network_condition(self):
        info = get_license_info("AGPL-3.0-only")
        assert "Network use is distribution" in info.conditions

    def test_mpl_has_file_level_copyleft(self):
        info = get_license_info("MPL-2.0")
        assert "Same license (file)" in info.conditions

    def test_bsl1_uses_source_only_notice(self):
        info = get_license_info("BSL-1.0")
        assert "License and copyright notice for source" in info.conditions

    def test_cc0_has_patent_limitation(self):
        info = get_license_info("CC0-1.0")
        assert "Patent use" in info.limitations

    def test_bsd3_clear_has_patent_limitation(self):
        info = get_license_info("BSD-3-Clause-Clear")
        assert "Patent use" in info.limitations
        assert "Patent use" not in info.permissions

    def test_epl2_lookup(self):
        info = get_license_info("EPL-2.0")
        assert info is not None
        assert info.full_name == "Eclipse Public License 2.0"

    def test_gfdl_alias(self):
        info = get_license_info("GFDL-1.3")
        assert info is not None
        assert info.spdx_id == "GFDL-1.3-only"

    def test_wtfpl_no_conditions_or_limitations(self):
        info = get_license_info("WTFPL")
        assert info.conditions == []
        assert info.limitations == []

    def test_vim_no_limitations(self):
        info = get_license_info("Vim")
        assert info.limitations == []
        assert len(info.conditions) > 0

    def test_zlib_uses_source_only_notice(self):
        info = get_license_info("Zlib")
        assert "License and copyright notice for source" in info.conditions
        assert "State changes" in info.conditions


# ── build_license_features_html ─────────────────────────────────────────


class TestBuildLicenseFeaturesHtml:
    def test_contains_toggle_structure(self):
        info = get_license_info("MIT")
        html = build_license_features_html(info)
        assert "gd-license-features" in html
        assert "gd-license-features-toggle" in html
        assert "gd-license-features-body" in html
        assert "<script>" in html

    def test_contains_full_name_in_toggle(self):
        info = get_license_info("MIT")
        html = build_license_features_html(info)
        assert "MIT License" in html

    def test_contains_permission_badges(self):
        info = get_license_info("MIT")
        html = build_license_features_html(info)
        assert "license-badge-permission" in html
        assert "Commercial use" in html

    def test_contains_condition_badges(self):
        info = get_license_info("MIT")
        html = build_license_features_html(info)
        assert "license-badge-condition" in html
        assert "License and copyright notice" in html

    def test_contains_limitation_badges(self):
        info = get_license_info("MIT")
        html = build_license_features_html(info)
        assert "license-badge-limitation" in html
        assert "Liability" in html

    def test_no_conditions_section_when_empty(self):
        info = get_license_info("Unlicense")
        html = build_license_features_html(info)
        assert "license-badge-condition" not in html
        # But still has permissions and limitations
        assert "license-badge-permission" in html
        assert "license-badge-limitation" in html

    def test_custom_features_label(self):
        info = get_license_info("MIT")
        html = build_license_features_html(info, features_label="Lizenzmerkmale")
        assert "Lizenzmerkmale" in html
        assert "MIT License" in html

    def test_all_licenses_produce_valid_html(self):
        seen = set()
        for key, info in LICENSES.items():
            if info.spdx_id in seen:
                continue
            seen.add(info.spdx_id)
            html = build_license_features_html(info)
            assert html.startswith('<div class="gd-license-features">')
            assert html.endswith("</div>")
