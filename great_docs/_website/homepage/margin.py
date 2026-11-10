"""
The homepage sidebar of project metadata

The sidebar has up to five sections: Links, AI / Agents, Developers, Community and Meta. A
section without entries is left out.
"""

from __future__ import annotations

import html
from typing import TYPE_CHECKING, Any, cast

from ..._project.manifest import Manifest
from ..._translations import translate
from ..spdx import get_license_info

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from ..._project.layout import Layout
    from ...config import Config
    from ..project_pages.community import CommunityPage

__all__ = ["render"]

# Lucide arrow-up-right, marking a link that leaves the site
_EXTERNAL_ARROW = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" '
    'fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round" '
    'style="vertical-align: -0.05em; margin-left: 0em; margin-top: 0.1em;" '
    'viewBox="0 0 24 24">'
    '<path d="M7 7h10v10"/><path d="M7 17 17 7"/></svg>'
)

_SPARKLE_PATHS = (
    '<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.582a.5.5 0 0 1 0 .963L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/>'
    '<path d="M20 3v4"/><path d="M22 5h-4"/>'
)

_ROR_ICON = (
    '<svg class="ror-sidebar-icon" viewBox="0 0 164 118" '
    'xmlns="http://www.w3.org/2000/svg" '
    'style="width: 1em; height: 0.75em; vertical-align: -0.05em; fill: currentColor;">'
    '<g transform="translate(-0.945,-0.815)">'
    '<path d="M68.65,4.16L56.52,22.74L44.38,4.16L68.65,4.16Z" style="fill:rgb(83,186,161);"/>'
    '<path d="M119.41,4.16L107.28,22.74L95.14,4.16L119.41,4.16Z" style="fill:rgb(83,186,161);"/>'
    '<path d="M44.38,115.47L56.52,96.88L68.65,115.47L44.38,115.47Z" style="fill:rgb(83,186,161);"/>'
    '<path d="M95.14,115.47L107.28,96.88L119.41,115.47L95.14,115.47Z" style="fill:rgb(83,186,161);"/>'
    '<path d="M145.53,63.71C149.83,62.91 153.1,61 155.33,57.99C157.57,54.98 158.68,51.32 158.68,47.03C158.68,43.47 158.06,40.51 156.83,38.13C155.6,35.75 153.93,33.86 151.84,32.45C149.75,31.05 147.31,30.04 144.53,29.44C141.75,28.84 138.81,28.54 135.72,28.54L112.16,28.54L112.16,47.37C111.97,46.82 111.77,46.28 111.55,45.74C109.92,41.79 107.64,38.42 104.71,35.64C101.78,32.86 98.32,30.72 94.3,29.23C90.29,27.74 85.9,26.99 81.14,26.99C76.38,26.99 72,27.74 67.98,29.23C63.97,30.72 60.5,32.86 57.57,35.64C54.95,38.13 52.85,41.1 51.27,44.54C51.04,42.07 50.46,39.93 49.53,38.13C48.3,35.75 46.63,33.86 44.54,32.45C42.45,31.05 40.01,30.04 37.23,29.44C34.45,28.84 31.51,28.54 28.42,28.54L4.87,28.54L4.87,89.42L18.28,89.42L18.28,65.08L24.9,65.08L37.63,89.42L53.71,89.42L38.24,63.71C42.54,62.91 45.81,61 48.04,57.99C48.14,57.85 48.23,57.7 48.33,57.56C48.31,58.03 48.3,58.5 48.3,58.98C48.3,63.85 49.12,68.27 50.75,72.22C52.38,76.17 54.66,79.54 57.59,82.32C60.51,85.1 63.98,87.24 68,88.73C72.01,90.22 76.4,90.97 81.16,90.97C85.92,90.97 90.3,90.22 94.32,88.73C98.33,87.24 101.8,85.1 104.73,82.32C107.65,79.54 109.93,76.17 111.57,72.22C111.79,71.69 111.99,71.14 112.18,70.59L112.18,89.42L125.59,89.42L125.59,65.08L132.21,65.08L144.94,89.42L161.02,89.42L145.53,63.71ZM36.39,50.81C35.67,51.73 34.77,52.4 33.68,52.83C32.59,53.26 31.37,53.52 30.03,53.6C28.68,53.69 27.41,53.73 26.2,53.73L18.29,53.73L18.29,39.89L27.06,39.89C28.26,39.89 29.5,39.98 30.76,40.15C32.02,40.32 33.14,40.65 34.11,41.14C35.08,41.63 35.89,42.33 36.52,43.25C37.15,44.17 37.47,45.4 37.47,46.95C37.47,48.6 37.11,49.89 36.39,50.81ZM98.74,66.85C97.85,69.23 96.58,71.29 94.91,73.04C93.25,74.79 91.26,76.15 88.93,77.13C86.61,78.11 84.01,78.59 81.15,78.59C78.28,78.59 75.69,78.1 73.37,77.13C71.05,76.16 69.06,74.79 67.39,73.04C65.73,71.29 64.45,69.23 63.56,66.85C62.67,64.47 62.23,61.85 62.23,58.98C62.23,56.17 62.67,53.56 63.56,51.15C64.45,48.74 65.72,46.67 67.39,44.92C69.05,43.17 71.04,41.81 73.37,40.83C75.69,39.86 78.28,39.37 81.15,39.37C84.02,39.37 86.61,39.86 88.93,40.83C91.25,41.8 93.24,43.17 94.91,44.92C96.57,46.67 97.85,48.75 98.74,51.15C99.63,53.56 100.07,56.17 100.07,58.98C100.07,61.85 99.63,64.47 98.74,66.85ZM143.68,50.81C142.96,51.73 142.06,52.4 140.97,52.83C139.88,53.26 138.66,53.52 137.32,53.6C135.97,53.69 134.7,53.73 133.49,53.73L125.58,53.73L125.58,39.89L134.35,39.89C135.55,39.89 136.79,39.98 138.05,40.15C139.31,40.32 140.43,40.65 141.4,41.14C142.37,41.63 143.18,42.33 143.81,43.25C144.44,44.17 144.76,45.4 144.76,46.95C144.76,48.6 144.4,49.89 143.68,50.81Z" style="fill:currentColor;"/>'
    "</g></svg>"
)


def render(
    config: Config,
    layout: Layout,
    *,
    metadata: Manifest,
    package_name: str | None,
    community_pages: Sequence[CommunityPage],
    has_llms_txt: bool,
) -> str:
    """
    Render the homepage sidebar as Markdown

    The sidebar links to the licence, citation and package-info pages when they are in the
    build directory, so it is rendered after them.

    Parameters
    ----------
    config
        The Great Docs configuration.
    layout
        The package root to search for a curated skill and the build directory to
        check for pages the sidebar can link to.
    metadata
        The package metadata: URLs, authors, licence, Python requirement and extras.
    package_name
        The package name, for the PyPI link, the curated skill and the citation link.
    community_pages
        The community pages written for the site.
    has_llms_txt
        Whether the build writes `llms.txt` and `llms-full.txt`, which the sidebar links to.

    Returns
    -------
    :
        The sidebar's Markdown, or `""` if no section has entries.
    """
    lang = config.lang
    build_dir = layout.build_dir
    sections = [
        *_links(config, metadata, package_name, lang),
        *_ai_agents(config, layout.package_root, package_name, lang, has_llms_txt=has_llms_txt),
        *_developers(config, metadata, lang),
        *_community(build_dir, metadata, package_name, community_pages, lang),
        *_meta(config, build_dir, metadata, lang),
    ]
    return "\n".join(sections)


def _links(config: Config, metadata: Manifest, package_name: str | None, lang: str) -> list[str]:
    """
    Render the Links section: PyPI and the project URLs

    Parameters
    ----------
    config
        The Great Docs configuration.
    metadata
        The package metadata.
    package_name
        The package name, for the default PyPI link.
    lang
        The site language.

    Returns
    -------
    :
        The heading and one line per link, or no lines if there are no links.
    """
    items: list[str] = []
    pypi = config.pypi
    if pypi is not False:
        if isinstance(pypi, str):
            pypi_url = pypi
        else:
            pypi_url = f"https://pypi.org/project/{package_name}/" if package_name else None
        if pypi_url:
            label = translate("view_on_pypi", lang)
            items.append(f'<a href="{html.escape(pypi_url)}">{label}{_EXTERNAL_ARROW}</a><br>')

    labels = {
        "homepage": None,
        "repository": translate("browse_source_code", lang),
        "bug_tracker": translate("report_a_bug", lang),
        "documentation": None,
    }
    urls: Mapping[str, str] = metadata.get("urls") or {}
    for name, url in urls.items():
        label = labels.get(name.lower().replace(" ", "_"), name.replace("_", " ").title())
        if label:
            items.append(
                f'<a href="{html.escape(url)}">'
                f"{html.escape(label, quote=False)}{_EXTERNAL_ARROW}</a><br>"
            )

    if not items:
        return []
    return [f"#### {translate('links', lang)}\n", *items]


def _ai_agents(
    config: Config,
    package_root: Path,
    package_name: str | None,
    lang: str,
    *,
    has_llms_txt: bool,
) -> list[str]:
    """
    Render the AI / Agents section with the Skills page and `llms.txt` files

    The Skills link's sparkle is emphasised for a curated skill: one set in the configuration
    or a `skills/<package>/SKILL.md` file in the project.

    Parameters
    ----------
    config
        The Great Docs configuration.
    package_root
        The project directory.
    package_name
        The package name.
    lang
        The site language.
    has_llms_txt
        Whether the build writes `llms.txt` and `llms-full.txt`.

    Returns
    -------
    :
        The heading and one line per link, or no lines if there are no links.
    """
    items: list[str] = []
    if config.skill_enabled:
        curated = bool(config.skill_file or config.skill_skills)
        if not curated:
            name = package_name or ""
            curated = any(
                candidate and (package_root / "skills" / candidate / "SKILL.md").exists()
                for candidate in (name.replace("_", "-"), name)
            )
        sparkle_class = "gd-sparkle-curated" if curated else "gd-sparkle"
        sparkle = (
            f'<svg class="{sparkle_class}" xmlns="http://www.w3.org/2000/svg" '
            'width="0.85em" height="0.85em" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            'stroke-linejoin="round" style="vertical-align: -0.1em; margin-left: 0.25em;">'
            f"{_SPARKLE_PATHS}</svg>"
        )
        items.append(f'<a href="skills.html">Skills{sparkle}</a><br>')
    if has_llms_txt:
        items.append("[llms.txt](llms.txt)<br>")
        items.append("[llms-full.txt](llms-full.txt)<br>")

    if not items:
        return []
    return [f"\n#### {translate('ai_agents', lang)}\n", *items]


def _developers(config: Config, metadata: Manifest, lang: str) -> list[str]:
    """
    Render the Developers section: a card per author, then the funder

    The authors are the configured ones, else those the package declares. An author without
    a GitHub account links to the owner of a GitHub repository URL.

    Parameters
    ----------
    config
        The Great Docs configuration, with the authors and the funder.
    metadata
        The package metadata, with `authors` and `urls`.
    lang
        The site language.

    Returns
    -------
    :
        The heading and one `<div>` per card, or no lines if there are no cards.
    """
    authors: list[Any] = config.authors or metadata.get("authors", [])
    funding: dict[str, Any] | None = config.funding
    if not isinstance(funding, dict) or not funding.get("name"):
        funding = None
    if not (authors or funding):
        return []

    repository_owner = None
    if urls := metadata.get("urls"):
        repo_url: str = urls.get("repository", "") or urls.get("Repository", "")
        _, found, path = repo_url.rstrip("/").partition("github.com/")
        if found:
            repository_owner = path.split("/")[0] or None

    cards = [
        _author_card(cast("dict[str, Any]", author), repository_owner)
        for author in authors
        if isinstance(author, dict)
    ]
    if funding is not None:
        cards.append(_funder_card(funding))

    return [
        f"\n#### {translate('developers', lang)}\n",
        *(
            f"<div>{card}</div>" if index == 0 else f'<div style="padding-top: 10px;">{card}</div>'
            for index, card in enumerate(cards)
        ),
    ]


def _author_card(author: dict[str, Any], repository_owner: str | None) -> str:
    """
    Render an author's name, role, affiliation and links

    Parameters
    ----------
    author
        The author's `name`, and optionally `role`, `affiliation`, `email`, `github`,
        `homepage` or `url`, and `orcid`.
    repository_owner
        The GitHub account to link when the author has none.

    Returns
    -------
    :
        The card's HTML.
    """
    parts = [_card_name(author.get("name", ""))]
    if role := author.get("role", ""):
        parts.append(_card_detail(role))
    if affiliation := author.get("affiliation", ""):
        parts.append(
            '<span><p><small style="margin-top: -0.15em; display: block;">'
            f"{html.escape(affiliation, quote=False)}</small></p></span>"
        )

    icons: list[str] = []
    if email := author.get("email", ""):
        icons.append(
            f'<a href="mailto:{html.escape(email)}" title="Email">'
            '<i class="bi bi-envelope-fill"></i></a>'
        )
    if github := author.get("github", "") or repository_owner:
        icons.append(
            f'<a href="https://github.com/{html.escape(github)}" title="GitHub">'
            '<i class="bi bi-github"></i></a>'
        )
    if homepage := author.get("homepage", "") or author.get("url", ""):
        icons.append(
            f'<a href="{html.escape(homepage)}" title="Website"><i class="bi bi-globe"></i></a>'
        )
    if orcid := author.get("orcid", ""):
        orcid_url = orcid if orcid.startswith("http") else f"https://orcid.org/{orcid}"
        icons.append(
            f'<a href="{html.escape(orcid_url)}" title="ORCID">'
            '<i class="fa-brands fa-orcid"></i></a>'
        )
    if icons:
        parts.append(_icon_row(icons))
    return "".join(parts)


def _funder_card(funding: dict[str, Any]) -> str:
    """
    Render the funder's name, roles and links

    Parameters
    ----------
    funding
        The funder's `name`, and optionally `roles`, `homepage` and `ror`.

    Returns
    -------
    :
        The card's HTML.
    """
    parts = [_card_name(funding.get("name", ""))]
    if roles := funding.get("roles", []):
        parts.append(_card_detail(", ".join(roles)))

    icons: list[str] = []
    if homepage := funding.get("homepage", ""):
        icons.append(
            f'<a href="{html.escape(homepage)}" title="Website"><i class="bi bi-globe"></i></a>'
        )
    if ror_url := funding.get("ror", ""):
        icons.append(
            f'<a href="{html.escape(ror_url)}" title="Research Organization Registry">'
            f"{_ROR_ICON}</a>"
        )
    if icons:
        parts.append(_icon_row(icons))
    return "".join(parts)


def _card_name(name: str) -> str:
    """
    Render the name line of a card

    Parameters
    ----------
    name
        The person or organisation.

    Returns
    -------
    :
        The name in bold.
    """
    name = html.escape(name, quote=False)
    return f'<span><p><strong style="padding-bottom: 4px;">{name}</strong></p></span>'


def _card_detail(text: str) -> str:
    """
    Render a line of small text under a card's name

    Parameters
    ----------
    text
        The role or roles.

    Returns
    -------
    :
        The text in a block-level `<span>`.
    """
    text = html.escape(text, quote=False)
    return f'<span style="margin-top: -0.15em; display: block;"><p><small>{text}</small></p></span>'


def _icon_row(icons: list[str]) -> str:
    """
    Render a card's row of icon links

    Parameters
    ----------
    icons
        The `<a>` elements.

    Returns
    -------
    :
        The links in one block-level `<span>`.
    """
    return '<span style="margin-top: -0.15em; display: block;">' + " ".join(icons) + "</span>"


def _community(
    build_dir: Path,
    metadata: Manifest,
    package_name: str | None,
    community_pages: Sequence[CommunityPage],
    lang: str,
) -> list[str]:
    """
    Render the Community section: community pages, the licence and the citation

    Parameters
    ----------
    build_dir
        The Quarto project directory, which may hold `license.qmd` and `citation.qmd`.
    metadata
        The package metadata, with the licence identifier.
    package_name
        The package name, for the citation link.
    community_pages
        The community pages written for the site.
    lang
        The site language.

    Returns
    -------
    :
        The heading and one line per link, or no lines if there are no links.
    """
    items = [
        f"[{translate(page.label_key, lang)}]({page.filename})<br>" for page in community_pages
    ]

    if (build_dir / "license.qmd").exists():
        full_licence = translate("full_license", lang)
        licence_id: str = metadata.get("license", "")
        info = get_license_info(licence_id) if licence_id else None
        if info is not None:
            items.append(
                f'<a href="license.qmd">{full_licence}</a> '
                f'<span title="{html.escape(info.full_name)}" '
                f'class="gd-spdx-badge">{info.spdx_id}</span><br>'
            )
        else:
            items.append(f"[{full_licence}](license.qmd)<br>")

    if (build_dir / "citation.qmd").exists():
        citing = translate("citing", lang)
        items.append(f"[{citing} {package_name or 'this package'}](citation.qmd)<br>")

    if not items:
        return []
    return [f"\n#### {translate('community', lang)}\n", *items]


def _meta(config: Config, build_dir: Path, metadata: Manifest, lang: str) -> list[str]:
    """
    Render the Meta section: Python requirement, extras, tags and package information

    Parameters
    ----------
    config
        The Great Docs configuration.
    build_dir
        The Quarto project directory, which may hold `package-info.qmd`.
    metadata
        The package metadata, with the Python requirement and optional dependencies.
    lang
        The site language.

    Returns
    -------
    :
        The heading and the entries on one line, or no lines if there are no entries.
    """
    items: list[str] = []
    if config.is_python_project and metadata.get("requires_python"):
        requires = translate("requires_python", lang)
        items.append(f"**{requires}:** Python `{metadata['requires_python']}`")

    if config.is_python_project and (extras := list(metadata.get("optional_dependencies") or {})):
        provides = translate("provides_extra", lang)
        items.append(f"**{provides}:** " + ", ".join(f"`{extra}`" for extra in extras))

    if config.tags_enabled and config.tags_index_page:
        items.append(f"[{translate('site_tags', lang)}](tags/index.html)")

    if (build_dir / "package-info.qmd").exists():
        items.append(f"[{translate('package_info', lang)}](package-info.html)")

    if not items:
        return []
    return [f"\n#### {translate('meta', lang)}\n", "<br>\n".join(items)]
