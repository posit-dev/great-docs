"""
SPDX license data for Great Docs.

Provides structured metadata for common open-source licenses including
SPDX identifiers, full names, and feature breakdowns (permissions,
conditions, limitations). Used by the license page generator and the
homepage sidebar metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LicenseInfo:
    """Structured metadata for a single SPDX license."""

    spdx_id: str
    full_name: str
    permissions: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


# ── Feature labels ──────────────────────────────────────────────────────
# Canonical strings used in permissions / conditions / limitations lists.
# Kept here for consistency and to ease future i18n.

PERM_COMMERCIAL = "Commercial use"
PERM_MODIFICATION = "Modification"
PERM_DISTRIBUTION = "Distribution"
PERM_PATENT = "Patent use"
PERM_PRIVATE = "Private use"

COND_LICENSE_NOTICE = "License and copyright notice"
COND_STATE_CHANGES = "State changes"
COND_DISCLOSE_SOURCE = "Disclose source"
COND_SAME_LICENSE = "Same license"
COND_LICENSE_NOTICE_SOURCE = "License and copyright notice for source"
COND_SAME_LICENSE_FILE = "Same license (file)"
COND_SAME_LICENSE_LIBRARY = "Same license (library)"
COND_NETWORK_USE = "Network use is distribution"

LIM_LIABILITY = "Liability"
LIM_WARRANTY = "Warranty"
LIM_TRADEMARK = "Trademark use"
LIM_PATENT = "Patent use"

# ── License database ───────────────────────────────────────────────────

LICENSES: dict[str, LicenseInfo] = {}


def _register(info: LicenseInfo, *aliases: str) -> None:
    """Register a LicenseInfo under its spdx_id and optional aliases."""
    LICENSES[info.spdx_id] = info
    for alias in aliases:
        LICENSES[alias] = info


# -- MIT ------------------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="MIT",
        full_name="MIT License",
        permissions=[PERM_COMMERCIAL, PERM_MODIFICATION, PERM_DISTRIBUTION, PERM_PRIVATE],
        conditions=[COND_LICENSE_NOTICE],
        limitations=[LIM_LIABILITY, LIM_WARRANTY],
    ),
)

# -- MIT-0 ----------------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="MIT-0",
        full_name="MIT No Attribution",
        permissions=[PERM_COMMERCIAL, PERM_MODIFICATION, PERM_DISTRIBUTION, PERM_PRIVATE],
        conditions=[],
        limitations=[LIM_LIABILITY, LIM_WARRANTY],
    ),
)

# -- Apache-2.0 -----------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="Apache-2.0",
        full_name="Apache License 2.0",
        permissions=[
            PERM_COMMERCIAL,
            PERM_MODIFICATION,
            PERM_DISTRIBUTION,
            PERM_PATENT,
            PERM_PRIVATE,
        ],
        conditions=[COND_LICENSE_NOTICE, COND_STATE_CHANGES],
        limitations=[LIM_LIABILITY, LIM_WARRANTY, LIM_TRADEMARK],
    ),
)

# -- GPL-3.0 --------------------------------------------------------------
_gpl3 = LicenseInfo(
    spdx_id="GPL-3.0-only",
    full_name="GNU General Public License v3.0",
    permissions=[
        PERM_COMMERCIAL,
        PERM_MODIFICATION,
        PERM_DISTRIBUTION,
        PERM_PATENT,
        PERM_PRIVATE,
    ],
    conditions=[
        COND_LICENSE_NOTICE,
        COND_STATE_CHANGES,
        COND_DISCLOSE_SOURCE,
        COND_SAME_LICENSE,
    ],
    limitations=[LIM_LIABILITY, LIM_WARRANTY],
)
_register(_gpl3, "GPL-3.0", "GPL-3.0-or-later")

# -- GPL-2.0 --------------------------------------------------------------
_gpl2 = LicenseInfo(
    spdx_id="GPL-2.0-only",
    full_name="GNU General Public License v2.0",
    permissions=[PERM_COMMERCIAL, PERM_MODIFICATION, PERM_DISTRIBUTION, PERM_PRIVATE],
    conditions=[
        COND_LICENSE_NOTICE,
        COND_STATE_CHANGES,
        COND_DISCLOSE_SOURCE,
        COND_SAME_LICENSE,
    ],
    limitations=[LIM_LIABILITY, LIM_WARRANTY],
)
_register(_gpl2, "GPL-2.0", "GPL-2.0-or-later")

# -- LGPL-3.0 -------------------------------------------------------------
_lgpl3 = LicenseInfo(
    spdx_id="LGPL-3.0-only",
    full_name="GNU Lesser General Public License v3.0",
    permissions=[
        PERM_COMMERCIAL,
        PERM_MODIFICATION,
        PERM_DISTRIBUTION,
        PERM_PATENT,
        PERM_PRIVATE,
    ],
    conditions=[
        COND_LICENSE_NOTICE,
        COND_STATE_CHANGES,
        COND_DISCLOSE_SOURCE,
        COND_SAME_LICENSE_LIBRARY,
    ],
    limitations=[LIM_LIABILITY, LIM_WARRANTY],
)
_register(_lgpl3, "LGPL-3.0", "LGPL-3.0-or-later")

# -- LGPL-2.1 -------------------------------------------------------------
_lgpl21 = LicenseInfo(
    spdx_id="LGPL-2.1-only",
    full_name="GNU Lesser General Public License v2.1",
    permissions=[PERM_COMMERCIAL, PERM_MODIFICATION, PERM_DISTRIBUTION, PERM_PRIVATE],
    conditions=[
        COND_LICENSE_NOTICE,
        COND_STATE_CHANGES,
        COND_DISCLOSE_SOURCE,
        COND_SAME_LICENSE_LIBRARY,
    ],
    limitations=[LIM_LIABILITY, LIM_WARRANTY],
)
_register(_lgpl21, "LGPL-2.1", "LGPL-2.1-or-later")

# -- AGPL-3.0 -------------------------------------------------------------
_agpl3 = LicenseInfo(
    spdx_id="AGPL-3.0-only",
    full_name="GNU Affero General Public License v3.0",
    permissions=[
        PERM_COMMERCIAL,
        PERM_MODIFICATION,
        PERM_DISTRIBUTION,
        PERM_PATENT,
        PERM_PRIVATE,
    ],
    conditions=[
        COND_LICENSE_NOTICE,
        COND_STATE_CHANGES,
        COND_DISCLOSE_SOURCE,
        COND_SAME_LICENSE,
        COND_NETWORK_USE,
    ],
    limitations=[LIM_LIABILITY, LIM_WARRANTY],
)
_register(_agpl3, "AGPL-3.0", "AGPL-3.0-or-later")

# -- BSD-2-Clause ---------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="BSD-2-Clause",
        full_name='BSD 2-Clause "Simplified" License',
        permissions=[PERM_COMMERCIAL, PERM_MODIFICATION, PERM_DISTRIBUTION, PERM_PRIVATE],
        conditions=[COND_LICENSE_NOTICE],
        limitations=[LIM_LIABILITY, LIM_WARRANTY],
    ),
)

# -- BSD-3-Clause ---------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="BSD-3-Clause",
        full_name='BSD 3-Clause "New" or "Revised" License',
        permissions=[PERM_COMMERCIAL, PERM_MODIFICATION, PERM_DISTRIBUTION, PERM_PRIVATE],
        conditions=[COND_LICENSE_NOTICE],
        limitations=[LIM_LIABILITY, LIM_WARRANTY],
    ),
)

# -- ISC ------------------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="ISC",
        full_name="ISC License",
        permissions=[PERM_COMMERCIAL, PERM_MODIFICATION, PERM_DISTRIBUTION, PERM_PRIVATE],
        conditions=[COND_LICENSE_NOTICE],
        limitations=[LIM_LIABILITY, LIM_WARRANTY],
    ),
)

# -- MPL-2.0 --------------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="MPL-2.0",
        full_name="Mozilla Public License 2.0",
        permissions=[
            PERM_COMMERCIAL,
            PERM_MODIFICATION,
            PERM_DISTRIBUTION,
            PERM_PATENT,
            PERM_PRIVATE,
        ],
        conditions=[COND_LICENSE_NOTICE, COND_DISCLOSE_SOURCE, COND_SAME_LICENSE_FILE],
        limitations=[LIM_LIABILITY, LIM_WARRANTY, LIM_TRADEMARK],
    ),
)

# -- Unlicense ------------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="Unlicense",
        full_name="The Unlicense",
        permissions=[PERM_COMMERCIAL, PERM_MODIFICATION, PERM_DISTRIBUTION, PERM_PRIVATE],
        conditions=[],
        limitations=[LIM_LIABILITY, LIM_WARRANTY],
    ),
)

# -- 0BSD -----------------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="0BSD",
        full_name="BSD Zero Clause License",
        permissions=[PERM_COMMERCIAL, PERM_MODIFICATION, PERM_DISTRIBUTION, PERM_PRIVATE],
        conditions=[],
        limitations=[LIM_LIABILITY, LIM_WARRANTY],
    ),
)

# -- CC0-1.0 --------------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="CC0-1.0",
        full_name="Creative Commons Zero v1.0 Universal",
        permissions=[PERM_COMMERCIAL, PERM_MODIFICATION, PERM_DISTRIBUTION, PERM_PRIVATE],
        conditions=[],
        limitations=[LIM_LIABILITY, LIM_WARRANTY, LIM_TRADEMARK, LIM_PATENT],
    ),
)

# -- BSL-1.0 --------------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="BSL-1.0",
        full_name="Boost Software License 1.0",
        permissions=[PERM_COMMERCIAL, PERM_MODIFICATION, PERM_DISTRIBUTION, PERM_PRIVATE],
        conditions=[COND_LICENSE_NOTICE_SOURCE],
        limitations=[LIM_LIABILITY, LIM_WARRANTY],
    ),
)

# -- Artistic-2.0 ---------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="Artistic-2.0",
        full_name="Artistic License 2.0",
        permissions=[
            PERM_COMMERCIAL,
            PERM_MODIFICATION,
            PERM_DISTRIBUTION,
            PERM_PATENT,
            PERM_PRIVATE,
        ],
        conditions=[COND_LICENSE_NOTICE, COND_STATE_CHANGES],
        limitations=[LIM_LIABILITY, LIM_WARRANTY, LIM_TRADEMARK],
    ),
)


# -- AFL-3.0 --------------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="AFL-3.0",
        full_name="Academic Free License v3.0",
        permissions=[
            PERM_COMMERCIAL,
            PERM_MODIFICATION,
            PERM_DISTRIBUTION,
            PERM_PATENT,
            PERM_PRIVATE,
        ],
        conditions=[COND_LICENSE_NOTICE, COND_STATE_CHANGES],
        limitations=[LIM_LIABILITY, LIM_WARRANTY, LIM_TRADEMARK],
    ),
)

# -- BSD-2-Clause-Patent --------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="BSD-2-Clause-Patent",
        full_name="BSD-2-Clause Plus Patent License",
        permissions=[
            PERM_COMMERCIAL,
            PERM_MODIFICATION,
            PERM_DISTRIBUTION,
            PERM_PATENT,
            PERM_PRIVATE,
        ],
        conditions=[COND_LICENSE_NOTICE],
        limitations=[LIM_LIABILITY, LIM_WARRANTY],
    ),
)

# -- BSD-3-Clause-Clear ---------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="BSD-3-Clause-Clear",
        full_name="BSD 3-Clause Clear License",
        permissions=[PERM_COMMERCIAL, PERM_MODIFICATION, PERM_DISTRIBUTION, PERM_PRIVATE],
        conditions=[COND_LICENSE_NOTICE],
        limitations=[LIM_LIABILITY, LIM_WARRANTY, LIM_PATENT],
    ),
)

# -- BSD-4-Clause ---------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="BSD-4-Clause",
        full_name='BSD 4-Clause "Original" or "Old" License',
        permissions=[PERM_COMMERCIAL, PERM_MODIFICATION, PERM_DISTRIBUTION, PERM_PRIVATE],
        conditions=[COND_LICENSE_NOTICE],
        limitations=[LIM_LIABILITY, LIM_WARRANTY],
    ),
)

# -- CC-BY-4.0 ------------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="CC-BY-4.0",
        full_name="Creative Commons Attribution 4.0 International",
        permissions=[PERM_COMMERCIAL, PERM_MODIFICATION, PERM_DISTRIBUTION, PERM_PRIVATE],
        conditions=[COND_LICENSE_NOTICE, COND_STATE_CHANGES],
        limitations=[LIM_LIABILITY, LIM_WARRANTY, LIM_TRADEMARK, LIM_PATENT],
    ),
)

# -- CC-BY-SA-4.0 ---------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="CC-BY-SA-4.0",
        full_name="Creative Commons Attribution Share Alike 4.0 International",
        permissions=[PERM_COMMERCIAL, PERM_MODIFICATION, PERM_DISTRIBUTION, PERM_PRIVATE],
        conditions=[COND_LICENSE_NOTICE, COND_SAME_LICENSE, COND_STATE_CHANGES],
        limitations=[LIM_LIABILITY, LIM_WARRANTY, LIM_TRADEMARK, LIM_PATENT],
    ),
)

# -- CECILL-2.1 -----------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="CECILL-2.1",
        full_name="CeCILL Free Software License Agreement v2.1",
        permissions=[
            PERM_COMMERCIAL,
            PERM_MODIFICATION,
            PERM_DISTRIBUTION,
            PERM_PATENT,
            PERM_PRIVATE,
        ],
        conditions=[
            COND_DISCLOSE_SOURCE,
            COND_LICENSE_NOTICE,
            COND_NETWORK_USE,
            COND_SAME_LICENSE,
        ],
        limitations=[LIM_LIABILITY, LIM_WARRANTY],
    ),
)

# -- CERN-OHL-P-2.0 ------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="CERN-OHL-P-2.0",
        full_name="CERN Open Hardware Licence Version 2 - Permissive",
        permissions=[
            PERM_COMMERCIAL,
            PERM_MODIFICATION,
            PERM_DISTRIBUTION,
            PERM_PATENT,
            PERM_PRIVATE,
        ],
        conditions=[COND_LICENSE_NOTICE, COND_STATE_CHANGES],
        limitations=[LIM_LIABILITY, LIM_WARRANTY],
    ),
)

# -- CERN-OHL-S-2.0 ------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="CERN-OHL-S-2.0",
        full_name="CERN Open Hardware Licence Version 2 - Strongly Reciprocal",
        permissions=[
            PERM_COMMERCIAL,
            PERM_MODIFICATION,
            PERM_DISTRIBUTION,
            PERM_PATENT,
            PERM_PRIVATE,
        ],
        conditions=[
            COND_DISCLOSE_SOURCE,
            COND_LICENSE_NOTICE,
            COND_SAME_LICENSE,
            COND_STATE_CHANGES,
        ],
        limitations=[LIM_LIABILITY, LIM_WARRANTY],
    ),
)

# -- CERN-OHL-W-2.0 ------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="CERN-OHL-W-2.0",
        full_name="CERN Open Hardware Licence Version 2 - Weakly Reciprocal",
        permissions=[
            PERM_COMMERCIAL,
            PERM_MODIFICATION,
            PERM_DISTRIBUTION,
            PERM_PATENT,
            PERM_PRIVATE,
        ],
        conditions=[
            COND_DISCLOSE_SOURCE,
            COND_LICENSE_NOTICE,
            COND_SAME_LICENSE_LIBRARY,
            COND_STATE_CHANGES,
        ],
        limitations=[LIM_LIABILITY, LIM_WARRANTY],
    ),
)

# -- ECL-2.0 --------------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="ECL-2.0",
        full_name="Educational Community License v2.0",
        permissions=[
            PERM_COMMERCIAL,
            PERM_MODIFICATION,
            PERM_DISTRIBUTION,
            PERM_PATENT,
            PERM_PRIVATE,
        ],
        conditions=[COND_LICENSE_NOTICE, COND_STATE_CHANGES],
        limitations=[LIM_LIABILITY, LIM_WARRANTY, LIM_TRADEMARK],
    ),
)

# -- EPL-1.0 --------------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="EPL-1.0",
        full_name="Eclipse Public License 1.0",
        permissions=[
            PERM_COMMERCIAL,
            PERM_MODIFICATION,
            PERM_DISTRIBUTION,
            PERM_PATENT,
            PERM_PRIVATE,
        ],
        conditions=[COND_DISCLOSE_SOURCE, COND_LICENSE_NOTICE, COND_SAME_LICENSE],
        limitations=[LIM_LIABILITY, LIM_WARRANTY],
    ),
)

# -- EPL-2.0 --------------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="EPL-2.0",
        full_name="Eclipse Public License 2.0",
        permissions=[
            PERM_COMMERCIAL,
            PERM_MODIFICATION,
            PERM_DISTRIBUTION,
            PERM_PATENT,
            PERM_PRIVATE,
        ],
        conditions=[COND_DISCLOSE_SOURCE, COND_LICENSE_NOTICE, COND_SAME_LICENSE],
        limitations=[LIM_LIABILITY, LIM_WARRANTY],
    ),
)

# -- EUPL-1.1 -------------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="EUPL-1.1",
        full_name="European Union Public License 1.1",
        permissions=[
            PERM_COMMERCIAL,
            PERM_MODIFICATION,
            PERM_DISTRIBUTION,
            PERM_PATENT,
            PERM_PRIVATE,
        ],
        conditions=[
            COND_DISCLOSE_SOURCE,
            COND_LICENSE_NOTICE,
            COND_NETWORK_USE,
            COND_SAME_LICENSE,
            COND_STATE_CHANGES,
        ],
        limitations=[LIM_LIABILITY, LIM_WARRANTY, LIM_TRADEMARK],
    ),
)

# -- EUPL-1.2 -------------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="EUPL-1.2",
        full_name="European Union Public License 1.2",
        permissions=[
            PERM_COMMERCIAL,
            PERM_MODIFICATION,
            PERM_DISTRIBUTION,
            PERM_PATENT,
            PERM_PRIVATE,
        ],
        conditions=[
            COND_DISCLOSE_SOURCE,
            COND_LICENSE_NOTICE,
            COND_NETWORK_USE,
            COND_SAME_LICENSE,
            COND_STATE_CHANGES,
        ],
        limitations=[LIM_LIABILITY, LIM_WARRANTY, LIM_TRADEMARK],
    ),
)

# -- GFDL-1.3 -------------------------------------------------------------
_gfdl13 = LicenseInfo(
    spdx_id="GFDL-1.3-only",
    full_name="GNU Free Documentation License v1.3",
    permissions=[PERM_COMMERCIAL, PERM_MODIFICATION, PERM_DISTRIBUTION, PERM_PRIVATE],
    conditions=[
        COND_DISCLOSE_SOURCE,
        COND_LICENSE_NOTICE,
        COND_SAME_LICENSE,
        COND_STATE_CHANGES,
    ],
    limitations=[LIM_LIABILITY, LIM_WARRANTY],
)
_register(_gfdl13, "GFDL-1.3", "GFDL-1.3-or-later")

# -- LPPL-1.3c ------------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="LPPL-1.3c",
        full_name="LaTeX Project Public License v1.3c",
        permissions=[PERM_COMMERCIAL, PERM_MODIFICATION, PERM_DISTRIBUTION, PERM_PRIVATE],
        conditions=[COND_DISCLOSE_SOURCE, COND_LICENSE_NOTICE, COND_STATE_CHANGES],
        limitations=[LIM_LIABILITY, LIM_WARRANTY],
    ),
)

# -- MS-PL ----------------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="MS-PL",
        full_name="Microsoft Public License",
        permissions=[
            PERM_COMMERCIAL,
            PERM_MODIFICATION,
            PERM_DISTRIBUTION,
            PERM_PATENT,
            PERM_PRIVATE,
        ],
        conditions=[COND_LICENSE_NOTICE],
        limitations=[LIM_WARRANTY, LIM_TRADEMARK],
    ),
)

# -- MS-RL ----------------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="MS-RL",
        full_name="Microsoft Reciprocal License",
        permissions=[
            PERM_COMMERCIAL,
            PERM_MODIFICATION,
            PERM_DISTRIBUTION,
            PERM_PATENT,
            PERM_PRIVATE,
        ],
        conditions=[COND_DISCLOSE_SOURCE, COND_LICENSE_NOTICE, COND_SAME_LICENSE_FILE],
        limitations=[LIM_WARRANTY, LIM_TRADEMARK],
    ),
)

# -- MulanPSL-2.0 ---------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="MulanPSL-2.0",
        full_name="Mulan Permissive Software License, Version 2",
        permissions=[
            PERM_COMMERCIAL,
            PERM_MODIFICATION,
            PERM_DISTRIBUTION,
            PERM_PATENT,
            PERM_PRIVATE,
        ],
        conditions=[COND_LICENSE_NOTICE],
        limitations=[LIM_LIABILITY, LIM_WARRANTY, LIM_TRADEMARK],
    ),
)

# -- NCSA -----------------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="NCSA",
        full_name="University of Illinois/NCSA Open Source License",
        permissions=[PERM_COMMERCIAL, PERM_MODIFICATION, PERM_DISTRIBUTION, PERM_PRIVATE],
        conditions=[COND_LICENSE_NOTICE],
        limitations=[LIM_LIABILITY, LIM_WARRANTY],
    ),
)

# -- ODbL-1.0 -------------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="ODbL-1.0",
        full_name="Open Data Commons Open Database License v1.0",
        permissions=[PERM_COMMERCIAL, PERM_MODIFICATION, PERM_DISTRIBUTION, PERM_PRIVATE],
        conditions=[COND_DISCLOSE_SOURCE, COND_LICENSE_NOTICE, COND_SAME_LICENSE],
        limitations=[LIM_LIABILITY, LIM_WARRANTY, LIM_TRADEMARK, LIM_PATENT],
    ),
)

# -- OFL-1.1 --------------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="OFL-1.1",
        full_name="SIL Open Font License 1.1",
        permissions=[PERM_COMMERCIAL, PERM_MODIFICATION, PERM_DISTRIBUTION, PERM_PRIVATE],
        conditions=[COND_LICENSE_NOTICE, COND_SAME_LICENSE],
        limitations=[LIM_LIABILITY, LIM_WARRANTY],
    ),
)

# -- OSL-3.0 --------------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="OSL-3.0",
        full_name="Open Software License 3.0",
        permissions=[
            PERM_COMMERCIAL,
            PERM_MODIFICATION,
            PERM_DISTRIBUTION,
            PERM_PATENT,
            PERM_PRIVATE,
        ],
        conditions=[
            COND_DISCLOSE_SOURCE,
            COND_LICENSE_NOTICE,
            COND_NETWORK_USE,
            COND_SAME_LICENSE,
            COND_STATE_CHANGES,
        ],
        limitations=[LIM_LIABILITY, LIM_WARRANTY, LIM_TRADEMARK],
    ),
)

# -- PostgreSQL -----------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="PostgreSQL",
        full_name="PostgreSQL License",
        permissions=[PERM_COMMERCIAL, PERM_MODIFICATION, PERM_DISTRIBUTION, PERM_PRIVATE],
        conditions=[COND_LICENSE_NOTICE],
        limitations=[LIM_LIABILITY, LIM_WARRANTY],
    ),
)

# -- UPL-1.0 --------------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="UPL-1.0",
        full_name="Universal Permissive License v1.0",
        permissions=[
            PERM_COMMERCIAL,
            PERM_MODIFICATION,
            PERM_DISTRIBUTION,
            PERM_PATENT,
            PERM_PRIVATE,
        ],
        conditions=[COND_LICENSE_NOTICE],
        limitations=[LIM_LIABILITY, LIM_WARRANTY],
    ),
)

# -- Vim ------------------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="Vim",
        full_name="Vim License",
        permissions=[PERM_COMMERCIAL, PERM_MODIFICATION, PERM_DISTRIBUTION, PERM_PRIVATE],
        conditions=[
            COND_DISCLOSE_SOURCE,
            COND_LICENSE_NOTICE,
            COND_SAME_LICENSE,
            COND_STATE_CHANGES,
        ],
        limitations=[],
    ),
)

# -- WTFPL ----------------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="WTFPL",
        full_name="Do What The F*ck You Want To Public License",
        permissions=[PERM_COMMERCIAL, PERM_MODIFICATION, PERM_DISTRIBUTION, PERM_PRIVATE],
        conditions=[],
        limitations=[],
    ),
)

# -- Zlib -----------------------------------------------------------------
_register(
    LicenseInfo(
        spdx_id="Zlib",
        full_name="zlib License",
        permissions=[PERM_COMMERCIAL, PERM_MODIFICATION, PERM_DISTRIBUTION, PERM_PRIVATE],
        conditions=[COND_LICENSE_NOTICE_SOURCE, COND_STATE_CHANGES],
        limitations=[LIM_LIABILITY, LIM_WARRANTY],
    ),
)


# ── Public helpers ──────────────────────────────────────────────────────


def get_license_info(identifier: str) -> LicenseInfo | None:
    """
    Look up license metadata by SPDX identifier.

    The lookup is case-insensitive: ``"mit"`` and ``"MIT"`` both match.

    Parameters
    ----------
    identifier
        An SPDX short identifier (e.g. ``"MIT"``, ``"Apache-2.0"``).

    Returns
    -------
    LicenseInfo | None
        The matching :class:`LicenseInfo`, or ``None`` for unrecognized identifiers.
    """
    # Try exact match first, then case-insensitive
    if identifier in LICENSES:
        return LICENSES[identifier]
    for key, info in LICENSES.items():
        if key.lower() == identifier.lower():
            return info
    return None


def build_license_features_html(
    info: LicenseInfo,
    features_label: str = "License features",
    permissions_label: str = "Permissions",
    conditions_label: str = "Conditions",
    limitations_label: str = "Limitations",
) -> str:
    """
    Generate the HTML for a collapsible license-features section.

    Uses the same button + animated-grid pattern as the Skills page install
    dropdown for visual consistency.  Produces color-coded badge lists for
    permissions (green), conditions (blue), and limitations (red).

    Parameters
    ----------
    info
        A :class:`LicenseInfo` with the feature lists.
    features_label
        Translated label for the "License features" summary text.
    permissions_label
        Translated heading for the permissions section.
    conditions_label
        Translated heading for the conditions section.
    limitations_label
        Translated heading for the limitations section.

    Returns
    -------
    str
        An HTML fragment ready for inclusion inside a ``.license-container``.
    """
    parts: list[str] = []

    # Outer wrapper
    parts.append('<div class="gd-license-features">')

    # Toggle button (same structure as .gd-skills-install-toggle)
    parts.append(
        '<button class="gd-license-features-toggle" '
        'aria-expanded="false" aria-controls="gd-license-features-body">'
    )
    parts.append('<span class="gd-license-features-icon">&#9654;</span>')
    parts.append(f"    {features_label} — {info.full_name}")
    parts.append("</button>")

    # Collapsible body (same grid pattern as .gd-skills-install-body)
    parts.append('<div class="gd-license-features-body" id="gd-license-features-body">')
    parts.append('<div class="gd-license-features-inner">')
    parts.append('<div class="gd-license-features-pad">')

    if info.permissions:
        parts.append('<div class="license-feature-group">')
        parts.append(f"<h4>{permissions_label}</h4>")
        parts.append('<div class="license-badges">')
        for p in info.permissions:
            parts.append(f'<span class="license-badge license-badge-permission">{p}</span>')
        parts.append("</div></div>")

    if info.conditions:
        parts.append('<div class="license-feature-group">')
        parts.append(f"<h4>{conditions_label}</h4>")
        parts.append('<div class="license-badges">')
        for c in info.conditions:
            parts.append(f'<span class="license-badge license-badge-condition">{c}</span>')
        parts.append("</div></div>")

    if info.limitations:
        parts.append('<div class="license-feature-group">')
        parts.append(f"<h4>{limitations_label}</h4>")
        parts.append('<div class="license-badges">')
        for lim in info.limitations:
            parts.append(f'<span class="license-badge license-badge-limitation">{lim}</span>')
        parts.append("</div></div>")

    parts.append("</div></div></div>")  # pad, inner, body

    # Inline toggle script (same pattern as skills page)
    parts.append("<script>")
    parts.append("(function() {")
    parts.append("  var btn = document.querySelector('.gd-license-features-toggle');")
    parts.append("  var body = document.getElementById('gd-license-features-body');")
    parts.append("  if (!btn || !body) return;")
    parts.append("  btn.addEventListener('click', function() {")
    parts.append("    var open = body.classList.toggle('gd-license-features-open');")
    parts.append("    btn.setAttribute('aria-expanded', open);")
    parts.append("  });")
    parts.append("})();")
    parts.append("</script>")

    parts.append("</div>")  # close .gd-license-features
    return "\n".join(parts)
