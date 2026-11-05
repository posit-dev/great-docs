"""
Homepage writing from an index page, README or the first user guide page

Both homepage modes use the same wrapper for `index.qmd`: front matter, the hero as a raw
HTML block, the body and the metadata sidebar. Each mode keeps its own sidebar placement.
"""

from __future__ import annotations

import json
import re
from enum import Enum
from typing import TYPE_CHECKING, Any

from yaml12 import format_yaml

from ..._content import publish
from ..._manifest import Manifest
from ..._yaml import YamlValue, locate_front_matter, set_front_matter_option
from ..project_pages import community
from ..seo import description as seo_description
from . import hero, landing, margin, readme, source

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from ..._content.pages import PageMap
    from ..._layout import Layout
    from ...config import Config

__all__ = ["Placement", "write", "write_blended", "write_readme"]


class Placement(Enum):
    """
    The position of the metadata sidebar on the homepage
    """

    MARGIN_COLUMN = "margin-column"
    """
    Quarto's margin column, written before the body, for the README homepage

    The page also gets a style rule that removes most of the top margin of its first heading,
    which would otherwise sit below the hero with a gap.
    """

    AFTER_BODY = "after-body"
    """
    A sidebar written after the body and positioned in the margin by the theme, for a user
    guide page

    A margin column would change Quarto's grid on a user guide page. On a narrow screen the
    sidebar falls back into the page flow, and writing it after the body keeps the content
    above it.
    """


_FIRST_HEADING_STYLE = """<style>
section.level1:first-of-type > h1:first-child,
section.level2:first-of-type > h2:first-child,
.column-body-outset-right > section.level1:first-of-type > h1,
#quarto-document-content > section:first-of-type > h1 {
  margin-top: 4px !important;
}
</style>

"""


def write(
    build_dir: Path,
    *,
    front_matter: str,
    hero: str,
    body: str,
    sidebar: str,
    placement: Placement,
) -> Path:
    """
    Write the homepage to `index.qmd`

    Parameters
    ----------
    build_dir
        The Quarto project directory to write `index.qmd` into.
    front_matter
        The page's front matter with its `---` fences, or `""` for none.
    hero
        The hero HTML, or `""` for a page without a hero.
    body
        The page's Markdown.
    sidebar
        The metadata sidebar's Markdown, or `""` for a page without one.
    placement
        Where the sidebar goes.

    Returns
    -------
    :
        The path to the written `index.qmd`.
    """
    hero_block = f"```{{=html}}\n{hero}```\n\n" if hero else ""
    content = front_matter + "\n"
    if placement is Placement.MARGIN_COLUMN:
        content += _FIRST_HEADING_STYLE + hero_block
        if sidebar:
            content += f"::: {{.column-margin .gd-homepage-sidebar}}\n{sidebar}\n:::\n\n"
        content += body + "\n"
    else:
        content += hero_block + body
        if sidebar:
            content += f"\n\n::: {{.gd-meta-sidebar .gd-homepage-sidebar}}\n{sidebar}\n:::\n"

    index_qmd = build_dir / "index.qmd"
    _ = index_qmd.write_text(content, encoding="utf-8")
    return index_qmd


def write_readme(
    config: Config,
    layout: Layout,
    build_dir: Path,
    *,
    metadata: Manifest,
    package_name: str | None,
    pages: PageMap,
    page_authors: list[dict[str, Any]],
    has_api_reference: bool,
    has_user_guide: Callable[[], bool],
    has_llms_txt: bool,
    report: Callable[[str], None],
) -> Path:
    """
    Write the homepage from the project's index page or README

    Use the first available source, or generate a landing page from package metadata if no
    source exists. Preserve the source's front matter and lower its headings by one level.
    Honour an explicit `toc` setting; otherwise, disable the table of contents. Add
    `gd-homepage` to the source's `body-classes`.

    Parameters
    ----------
    config
        The Great Docs configuration.
    layout
        The project's directories.
    build_dir
        The Quarto project directory to write the homepage and community pages into.
    metadata
        The package metadata.
    package_name
        The package name, or `None` if it is unknown.
    pages
        The published paths of the authored pages.
    page_authors
        The configured authors, with local portrait paths replaced by site URLs.
    has_api_reference
        Whether the site has an API reference, which a landing page links to.
    has_user_guide
        A callback that reports whether the site has a user guide. User guide discovery
        reports directory problems, so the callback is called only for a landing page,
        which links to the guide when present.
    has_llms_txt
        Whether the build writes `llms.txt` and `llms-full.txt`, which the sidebar links to.
    report
        A callback that receives progress messages and warnings.

    Returns
    -------
    :
        The path to the written `index.qmd`.
    """
    index_qmd = build_dir / "index.qmd"
    sources = source.find(layout)
    if len(sources) > 1:
        others = ", ".join(path.name for path in sources[1:])
        report(
            f"⚠️  Multiple index source files detected. Using {sources[0].name} (ignoring {others})"
        )

    # An empty title keeps "Home" off a generated landing page.
    title = ""
    page_description: dict[str, YamlValue] = {}
    options: dict[str, YamlValue] = {}
    if not sources:
        report("No index source file found (index.qmd, index.md, README.md, or README.rst)")
        report("Generating landing page from package metadata...")
        body = landing.markdown(
            package_name,
            metadata.get("description", ""),
            has_api_reference=has_api_reference,
            has_user_guide=has_user_guide(),
        )
    else:
        source_file = sources[0]
        report(f"Rebuilding index.qmd from {source_file.name}...")
        authored = source.read(source_file, report=report)
        title = authored.title
        page_description = dict(authored.description)
        options = dict(authored.options)
        body = publish.rebase_references(
            authored.body, source_file, index_qmd, layout=layout, pages=pages
        )

    # Extract the hero before changing heading levels so README badges can move into it.
    hero_html, without_badges = _hero(
        config,
        layout,
        build_dir,
        body,
        metadata=metadata,
        package_name=package_name,
        pages=pages,
    )
    if without_badges is not None:
        body = without_badges

    # Test that the hero rendered, not `hero.enabled`: a logo-hero file or a README hero
    # block also turns the hero on.
    if hero_html:
        hero_name = config.hero_name
        if hero_name is None:
            hero_name = metadata.get("name") or package_name
        if isinstance(hero_name, str) and hero_name:
            body = readme.strip_duplicate_title(body, hero_name)

    # Read the README's opening paragraph before the page wrapper adds markup above it.
    if config.seo_enabled and not page_description:
        opening = seo_description.first_paragraph(body, citations=bool(config.bibliography)).text
        if opening:
            page_description = {"description-meta": seo_description.as_metadata(opening)}

    if sources:
        # The README's headings sit one level below the homepage's
        body = readme.bump_heading_levels(body)

    sidebar = _sidebar(
        config,
        layout,
        build_dir,
        metadata=metadata,
        package_name=package_name,
        page_authors=page_authors,
        has_llms_txt=has_llms_txt,
    )

    # An explicit `toc` setting overrides the homepage's default of no table of contents.
    page_keys: dict[str, YamlValue] = {"title": title, **page_description, **options}
    _ = page_keys.setdefault("toc", False)

    # Homepage styles require `gd-homepage` alongside any classes the source sets.
    authored_classes = page_keys.pop("body-classes", None)
    items = authored_classes if isinstance(authored_classes, list) else [authored_classes]
    classes = " ".join(item for item in items if isinstance(item, str)).split()
    if "gd-homepage" not in classes:
        classes.append("gd-homepage")

    # Preserve quotes and colons in front matter and write an empty title as `title: ""`.
    # JSON quoting also produces a valid YAML scalar for the body classes.
    front_matter = (
        f"---\n{format_yaml(page_keys).rstrip()}\n"
        f"body-classes: {json.dumps(' '.join(classes))}\n---\n"
    )
    index_qmd = write(
        build_dir,
        front_matter=front_matter,
        hero=hero_html,
        body=body,
        sidebar=sidebar,
        placement=Placement.MARGIN_COLUMN,
    )
    report(f"Created {index_qmd}")
    return index_qmd


def write_blended(
    config: Config,
    layout: Layout,
    build_dir: Path,
    content: str,
    *,
    metadata: Manifest,
    package_name: str | None,
    pages: PageMap,
    page_authors: list[dict[str, Any]],
    has_llms_txt: bool,
) -> Path:
    """
    Write the homepage from the first user guide page

    Preserve the page's front matter, disable its table of contents and remove its first `#`
    heading.

    Parameters
    ----------
    config
        The Great Docs configuration.
    layout
        The project's directories.
    build_dir
        The Quarto project directory to write the homepage and community pages into.
    content
        The user guide page as copied into the build directory.
    metadata
        The package metadata.
    package_name
        The package name, or `None` if it is unknown.
    pages
        The published paths of the authored pages.
    page_authors
        The configured authors, with local portrait paths replaced by site URLs.
    has_llms_txt
        Whether the build writes `llms.txt` and `llms-full.txt`, which the sidebar links to.

    Returns
    -------
    :
        The path to the written `index.qmd`.
    """
    # Preserve the front matter title so Quarto's title block matches other user guide pages.
    content = set_front_matter_option(content, "toc", False)

    sidebar = _sidebar(
        config,
        layout,
        build_dir,
        metadata=metadata,
        package_name=package_name,
        page_authors=page_authors,
        has_llms_txt=has_llms_txt,
    )
    hero_html, _ = _hero(
        config,
        layout,
        build_dir,
        None,
        metadata=metadata,
        package_name=package_name,
        pages=pages,
    )

    # Keep user guide heading levels: Quarto takes the first body `#` heading as the title,
    # and `shift-heading-level-by: -1` turns the remaining `##` into `<h1>`, as on other
    # user guide pages.
    front_matter = ""
    body = content
    block = locate_front_matter(content)
    if block is not None:
        front_matter = content[: block.end]
        body = content[block.end :].lstrip("\n")

    # The front matter title provides the title block. Remove the first body `#` heading:
    # `shift-heading-level-by: -1` would turn it into a duplicate paragraph.
    body = re.sub(r"^#\s+[^\n]*\n?", "", body, count=1, flags=re.MULTILINE)

    return write(
        build_dir,
        front_matter=front_matter,
        hero=hero_html,
        body=body,
        sidebar=sidebar,
        placement=Placement.AFTER_BODY,
    )


def _hero(
    config: Config,
    layout: Layout,
    build_dir: Path,
    readme_text: str | None,
    *,
    metadata: Manifest,
    package_name: str | None,
    pages: PageMap,
) -> tuple[str, str | None]:
    """
    Render the homepage hero

    Parameters
    ----------
    config
        The Great Docs configuration.
    layout
        The project's directories.
    build_dir
        The Quarto project directory, which receives a copy of a local logo.
    readme_text
        The homepage Markdown, or `None` for a page that is not a README.
    metadata
        The package metadata.
    package_name
        The package name, or `None` if it is unknown.
    pages
        The published paths of the authored pages.

    Returns
    -------
    :
        The hero HTML and the README with its badges removed. The HTML is `""` when no hero
        is rendered; the README is `None` when the hero leaves it unchanged.
    """
    found = hero.find(config, layout.source_dir, readme_text)
    if found is None:
        return "", None
    html = hero.render(
        found,
        config,
        layout,
        build_dir,
        metadata=metadata,
        package_name=package_name,
        pages=pages,
    )
    return html, found.body if html else None


def _sidebar(
    config: Config,
    layout: Layout,
    build_dir: Path,
    *,
    metadata: Manifest,
    package_name: str | None,
    page_authors: list[dict[str, Any]],
    has_llms_txt: bool,
) -> str:
    """
    Write the community pages and render the homepage's metadata sidebar

    Parameters
    ----------
    config
        The Great Docs configuration.
    layout
        The project's directories.
    build_dir
        The Quarto project directory to write the community pages into.
    metadata
        The package metadata.
    package_name
        The package name, or `None` if it is unknown.
    page_authors
        The configured authors, with local portrait paths replaced by site URLs.
    has_llms_txt
        Whether the build writes `llms.txt` and `llms-full.txt`.

    Returns
    -------
    :
        The sidebar's Markdown, or `""` when it has no sections.
    """
    package_root = layout.package_root
    return margin.render(
        config,
        build_dir,
        package_root=package_root,
        metadata=metadata,
        package_name=package_name,
        community_pages=community.write_pages(config, package_root, build_dir, page_authors),
        has_llms_txt=has_llms_txt,
    )
