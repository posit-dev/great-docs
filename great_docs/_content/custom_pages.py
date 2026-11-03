"""
Custom HTML pages published through the `custom_pages` setting

A `passthrough` page becomes a `.qmd` page with an HTML body and the site's navbar
and theme. A `raw` page remains a standalone HTML file. Quarto does not render raw pages,
so they receive the site's head tags directly. Other files in the source directory are
copied as project resources.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from yaml12 import format_yaml

from .._contribution import NavbarLink
from .._website import i18n, page_url, social_cards
from .._website.seo import description as seo_description
from .._yaml import YamlMapping, split_front_matter
from . import publish as page_publish
from .naming import title_from_name
from .pages import output_destination
from .sections import source_dirs as section_source_dirs

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from .._layout import Layout
    from .._website.seo.structured_data import StructuredData
    from ..config import Config
    from .pages import PageMap

__all__ = ["Published", "RawPageHead", "Source", "find_sources", "navbar_link", "publish"]

_LAYOUTS = {"passthrough", "raw"}


@dataclass(frozen=True)
class Source:
    """A custom page source directory and its destination in the build"""

    path: Path
    """The source directory"""

    output: str
    """The destination relative to the build directory, as configured"""

    destination: Path
    """The destination in the build"""


@dataclass(frozen=True)
class RawPageHead:
    """Site-wide metadata for the head tags of raw pages"""

    base_url: str | None
    """The canonical base URL, or `None` when the site has none"""

    card_image_url: str | None
    """The social card image, or `None` when social cards are disabled or have no image"""

    structured_data: StructuredData | None
    """The package's JSON-LD description, or `None` when it is disabled"""

    site_name: str
    """The site's name, or an empty string"""

    default_description: str | None
    """The site's default search description as plain text"""


@dataclass(frozen=True)
class Published:
    """The published custom page count and required `_quarto.yml` changes"""

    pages: int
    """The number of HTML pages published"""

    resources: list[str]
    """Files that Quarto must copy as they are, relative to the build directory"""

    render_excludes: list[str]
    """Raw pages that Quarto must not render, relative to the build directory"""

    navbar: list[tuple[NavbarLink, str | None]]
    """Navbar links that pages request, each with the label of the item it follows"""


def find_sources(config: Config, layout: Layout, *, report: Callable[[str], None]) -> list[Source]:
    """
    Find the configured custom page directories that exist

    Without a `custom_pages` setting, `custom/` is used unless a section publishes it.

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's directories.
    report
        A callback for missing-directory warnings. A missing default `custom/` is silent
        when the project has no configuration file.

    Returns
    -------
    :
        The directories, in configured order.

    Raises
    ------
    ValueError
        If an entry's `output` lies outside the build directory, even if its source
        directory is missing.
    """
    sources: list[Source] = []
    is_default = config["custom_pages"] is None
    claimed = section_source_dirs(config, layout)

    for entry in config.custom_pages:
        destination = output_destination(layout, entry["output"])
        source_dir = layout.source_dir / entry["dir"]
        if not source_dir.is_dir():
            if entry["dir"] != "custom" or config.exists():
                report(f"Custom pages directory '{entry['dir']}' not found, skipping")
            continue
        # A section takes precedence over the default `custom/`; explicit overlap fails validation.
        if is_default and source_dir.resolve() in claimed:
            continue
        sources.append(Source(source_dir, entry["output"], destination))

    return sources


def navbar_link(
    front_matter: YamlMapping, default_title: str, href: str
) -> tuple[NavbarLink, str | None] | None:
    """
    Read a custom page's requested navbar link

    `navbar` accepts `true`, a label, or a mapping with `text` and `after`.
    `navbar_after` names the item the link follows unless a mapping supplies `after`.

    Parameters
    ----------
    front_matter
        The page's front matter.
    default_title
        The label used when `navbar` gives none.
    href
        The link's target.

    Returns
    -------
    :
        The link and the label of the item it follows, or `None` when the page requests
        no link.
    """
    navbar = front_matter.get("navbar")
    navbar_after = front_matter.string("navbar_after")

    if navbar in (None, False):
        return None

    if navbar is True:
        return NavbarLink(text=default_title, href=href), navbar_after

    if isinstance(navbar, str):
        return NavbarLink(text=navbar, href=href), navbar_after

    if isinstance(navbar, dict):
        options = YamlMapping(navbar)
        text = options.get("text", default_title)
        after = options.get("after", navbar_after)
        if isinstance(text, str) and text:
            return NavbarLink(text=text, href=href), after if isinstance(after, str) else None

    return None  # pragma: no cover


def publish(
    sources: Sequence[Source],
    *,
    config: Config,
    layout: Layout,
    pages: PageMap,
    head: RawPageHead,
    add_dates: Callable[[str, Path], str],
    report: Callable[[str], None],
) -> Published:
    """
    Publish custom pages and copy their supporting files into the build

    `.html` and `.htm` files are pages. Their `layout` front matter selects `passthrough`
    (the default) or `raw`. Links in each page are rebased to its published location.

    Parameters
    ----------
    sources
        The custom page directories.
    config
        The project's configuration.
    layout
        The project's directories.
    pages
        The published paths of authored pages.
    head
        The site-wide values for the head tags of raw pages.
    add_dates
        Adds a source page's dates and authors to the text of a passthrough page.
    report
        Receives a warning for each unsupported `layout`, which is published as
        `passthrough`.

    Returns
    -------
    :
        The published page count and the required resources, render exclusions and
        navbar links.
    """
    resources: list[str] = []
    render_excludes: list[str] = []
    navbar: list[tuple[NavbarLink, str | None]] = []
    processed = 0

    for source in sources:
        source.destination.mkdir(parents=True, exist_ok=True)

        for src_path in sorted(source.path.rglob("*")):
            if not src_path.is_file():
                continue

            rel_path = src_path.relative_to(source.path)
            dest_path = source.destination / rel_path
            output_path = (Path(source.output) / rel_path).as_posix()
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            if src_path.suffix.lower() not in (".html", ".htm"):
                _ = shutil.copy2(src_path, dest_path)
                resources.append(output_path)
                continue

            content = src_path.read_text(encoding="utf-8")
            content = page_publish.rebase_references(
                content, src_path, dest_path, layout=layout, pages=pages
            )
            front_matter, body = split_front_matter(content)
            body = body.lstrip("\n")
            page_layout = (front_matter.string("layout") or "passthrough").lower()
            page_title = front_matter.string("title") or title_from_name(src_path.stem)

            if page_layout not in _LAYOUTS:
                report(  # pragma: no cover
                    f"Unsupported custom page layout '{page_layout}' in {output_path}; "
                    "defaulting to passthrough"
                )
                page_layout = "passthrough"  # pragma: no cover

            if page_layout == "raw":
                _ = dest_path.write_text(
                    _add_head_tags(body, output_path, config=config, head=head), encoding="utf-8"
                )
                resources.append(output_path)
                render_excludes.append(output_path)
                href = output_path
            else:
                qmd_front_matter = dict(front_matter.data)
                _ = qmd_front_matter.pop("layout", None)
                _ = qmd_front_matter.setdefault("title", page_title)
                _ = qmd_front_matter.setdefault("bread-crumbs", False)
                qmd_body = body if body.endswith("\n") else f"{body}\n"
                qmd_content = f"---\n{format_yaml(qmd_front_matter)}\n---\n\n{qmd_body}"
                _ = dest_path.with_suffix(".qmd").write_text(
                    add_dates(qmd_content, src_path), encoding="utf-8"
                )
                href = Path(output_path).with_suffix(".qmd").as_posix()

            link = navbar_link(front_matter, page_title, href)
            if link is not None:
                navbar.append(link)

            processed += 1

    return Published(processed, resources, render_excludes, navbar)


def _add_head_tags(page: str, output_path: str, *, config: Config, head: RawPageHead) -> str:
    """
    Add the site's canonical link, translations, description and social card tags to a raw page

    Parameters
    ----------
    page
        The page's HTML.
    output_path
        The page's path relative to the build directory, in POSIX form.
    config
        The project's configuration.
    head
        The site-wide values for the tags.

    Returns
    -------
    :
        The page with the tags in its `<head>`.
    """
    page = page_url.add_to_raw_page(page, config, head.base_url, output_path)
    page = i18n.add_to_raw_page(page, config)
    if config.seo_enabled:
        page = seo_description.add_to_raw_page(page, head.default_description)
    page = social_cards.add_to_raw_page(
        page,
        config,
        site_name=head.site_name,
        default=head.default_description,
        url=page_url.address(head.base_url, output_path) if head.base_url else None,
        image_url=head.card_image_url,
    )
    if head.structured_data:
        page = head.structured_data.add_to_raw_page(page, output_path)
    return page
