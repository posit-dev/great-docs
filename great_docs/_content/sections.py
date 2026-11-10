"""
Sections: directories of authored pages that the `sections` setting publishes

A default section publishes its pages with a sidebar and, optionally, a generated index of
cards. A blog section publishes its posts under a listing page that Quarto fills.
"""

from __future__ import annotations

import html
import json
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict, cast

from yaml12 import format_yaml

from .._contribution import NavbarLink
from .._website.navigation import navbar
from .._yaml import locate_front_matter, set_front_matter_option
from . import publish as page_publish
from .naming import published_path, strip_numeric_prefix, title_from_name
from .pages import section_destination

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from .._project.layout import Layout
    from ..config import Config
    from .pages import PageMap

__all__ = [
    "Page",
    "Published",
    "Section",
    "add_no_sidebar_class",
    "blog_index",
    "card_index",
    "copy_pages",
    "copy_posts",
    "publish",
    "read",
    "sidebar",
    "source_dirs",
]

_NO_SIDEBAR_CLASS = "gd-section-no-sidebar"
_CONTENT_SUFFIXES = {".qmd", ".md"}


class Page(TypedDict):
    """A page published in a section, as its index and sidebar list it"""

    filename: str
    """The page's path relative to the section's directory in the build"""

    title: str
    """The page's title, or one made from its file name"""

    description: str
    """The page's description, or an empty string"""

    image: NotRequired[str]
    """The page's card image, or an empty string; blog posts have none"""


@dataclass(frozen=True)
class Section:
    """A `sections` entry whose directory holds pages to publish"""

    title: str
    """The section's title, used for its navbar link, sidebar and index"""

    dir: str
    """The source directory as configured"""

    source: Path
    """The source directory"""

    blog: bool
    """Whether the section is a blog, whose posts keep their names and front matter"""

    files: tuple[Path, ...]
    """The `.qmd` and `.md` pages, in sorted order"""

    destination: Path
    """The section's directory in the build"""

    slug: str
    """The destination relative to the build directory, in POSIX form"""

    index: bool
    """Whether to generate an index of cards when the section has no `index.qmd`"""

    index_columns: int
    """The number of columns of image cards in a generated index"""

    index_groups: bool
    """Whether a generated index groups cards the way the sidebar groups pages"""

    navbar_after: str | None
    """The label of the navbar item the section's link follows"""

    dir_titles: dict[str, str]
    """Sidebar titles for subdirectories, keyed by name without the numeric prefix"""

    sidebar_groups: list[dict[str, Any]] | None
    """Sidebar groups, each a `section` title and the file names of its `contents`"""


@dataclass(frozen=True)
class Published:
    """A section's published pages and the navigation it adds to the site"""

    pages: list[Page]
    """The pages copied into the build"""

    sidebar: dict[str, Any] | None
    """
    The sidebar, or `None` for a blog or a section with at most one page

    The page count includes the section's index.
    """

    navbar: NavbarLink
    """The link to the section's index or first page"""

    navbar_after: str | None
    """The label of the navbar item the link follows"""


def source_dirs(config: Config, layout: Layout) -> set[Path]:
    """
    Collect the source directories that `sections` entries publish

    Each directory published by a section belongs to that section. The user guide and custom
    pages do not also publish it.

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's layout, which locates section directories.

    Returns
    -------
    :
        The resolved directory of every section entry with a `dir`.
    """
    sections = config.sections
    if not isinstance(sections, list):  # pyright: ignore[reportUnnecessaryIsInstance]
        return set()
    return {
        (layout.source_dir / section["dir"]).resolve()
        for section in sections
        if isinstance(section, dict) and isinstance(section.get("dir"), str)  # pyright: ignore[reportUnnecessaryIsInstance]
    }


def read(config: Config, layout: Layout, *, report: Callable[[str], None]) -> list[Section]:
    """
    Read the `sections` entries that have pages to publish

    Pages are the `.qmd` and `.md` files at any depth of the section's directory, except
    `README.md` and files under this project's generated directories.

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's directories.
    report
        Receives a line for each entry that is skipped and why.

    Returns
    -------
    :
        The sections, in configured order.
    """
    entries = cast("object", config.sections)
    if not entries:
        return []
    if not isinstance(entries, list):
        report(f"'sections' must be a list, got {type(entries).__name__}")
        return []

    sections: list[Section] = []
    for entry in cast("list[object]", entries):
        if not isinstance(entry, dict):
            report(f"Section entry must be a dict, skipping: {entry}")
            continue
        options = cast("dict[str, Any]", entry)
        title = options.get("title")
        directory = options.get("dir")
        if not title or not directory:
            report(f"Section missing 'title' or 'dir', skipping: {options}")
            continue

        source = layout.source_dir / directory
        if not source.exists() or not source.is_dir():
            report(f"Section directory '{directory}' not found, skipping")
            continue

        # Only ancestors within the section directory are consulted, since a hidden
        # directory above the project says nothing about the content inside.
        files = sorted(
            file
            for file in source.rglob("*")
            if file.suffix in _CONTENT_SUFFIXES
            and file.name != "README.md"
            and not any(
                layout.is_reserved_directory(parent)
                for parent in file.parents
                if parent != source and parent.is_relative_to(source)
            )
        )
        if not files:
            report(f"Section '{title}' directory '{directory}' has no .qmd/.md files")
            continue

        # Tag and status scanning find pages at the same destination
        destination = section_destination(layout, options)
        assert destination is not None
        sections.append(
            Section(
                title=title,
                dir=directory,
                source=source,
                blog=options.get("type", "default") == "blog",
                files=tuple(files),
                destination=destination,
                slug=destination.relative_to(layout.build_dir).as_posix(),
                index=bool(options.get("index", False)),
                index_columns=options.get("index_columns", 2),
                index_groups=bool(options.get("index_groups", True)),
                navbar_after=options.get("navbar_after"),
                dir_titles=options.get("dir_titles") or {},
                sidebar_groups=options.get("sidebar_groups"),
            )
        )
    return sections


def publish(
    section: Section,
    *,
    config: Config,
    layout: Layout,
    pages: PageMap,
    add_dates: Callable[[str, Path], str],
) -> Published:
    """
    Copy a section's pages into the build and write or patch its index

    A blog's index is the author's root `index.qmd`, given the blog index's layout, or a
    generated listing. A default section's index is the author's `index.qmd`, a generated
    index of cards when `index` is set, or else its first page.

    A default section has a sidebar when it has more than one page, including its index.
    With at most one page, its pages receive the `gd-section-no-sidebar` body class.

    The navbar label is the section's title. A section titled exactly `Recipes` uses
    the translation of that label in the site's language.

    Parameters
    ----------
    section
        The section.
    config
        The Great Docs configuration.
    layout
        The project's directories.
    pages
        The published path of each authored page.
    add_dates
        Adds a source page's dates and authors to its text.

    Returns
    -------
    :
        The copied pages, the sidebar and the navbar link.
    """
    destination = section.destination
    index = destination / "index.qmd"
    index_href = f"{section.slug}/index.qmd"
    # Only a root-level `index.qmd` is the section's index; a blog post may be a
    # subdirectory's `index.qmd`.
    has_user_index = (section.source / "index.qmd").exists()
    section_sidebar = None

    if section.blog:
        copied = copy_posts(
            section.files,
            section.source,
            destination,
            layout=layout,
            pages=pages,
            add_dates=add_dates,
        )
        if has_user_index:
            content = index.read_text(encoding="utf-8")
            content = set_front_matter_option(content, "toc", False)
            content = set_front_matter_option(content, "body-classes", "gd-blog-index")
            _ = index.write_text(content, encoding="utf-8")
        else:
            _ = index.write_text(blog_index(section.title), encoding="utf-8")
    else:
        copied = copy_pages(
            section.files,
            section.source,
            destination,
            layout=layout,
            pages=pages,
            add_dates=add_dates,
        )
        content_pages = [page for page in copied if page["filename"] != "index.qmd"]
        if not has_user_index and section.index:
            index_source = card_index(
                section.title,
                copied,
                columns=section.index_columns,
                dir_titles=section.dir_titles,
                sidebar_groups=section.sidebar_groups,
                index_groups=section.index_groups,
            )
            _ = index.write_text(index_source, encoding="utf-8")
        elif not has_user_index and content_pages:
            index_href = f"{section.slug}/{content_pages[0]['filename']}"

        has_index = has_user_index or section.index
        section_sidebar = sidebar(
            section.title,
            section.slug,
            copied,
            has_index=has_index,
            dir_titles=section.dir_titles,
            sidebar_groups=section.sidebar_groups,
        )
        if section_sidebar is None:
            add_no_sidebar_class(copied, destination)

    return Published(
        pages=copied,
        sidebar=section_sidebar,
        navbar=NavbarLink(text=_navbar_label(section.title, config), href=index_href),
        navbar_after=section.navbar_after,
    )


def _navbar_label(title: str, config: Config) -> str:
    """
    Label a section's navbar link

    Parameters
    ----------
    title
        The section's title.
    config
        The Great Docs configuration.

    Returns
    -------
    :
        The title, translated into the site's language only when it is exactly `Recipes`.
    """
    if title == navbar.RECIPES.english:
        return navbar.RECIPES.label(config)
    return title


def copy_pages(
    files: Iterable[Path],
    source_dir: Path,
    dest_dir: Path,
    *,
    layout: Layout,
    pages: PageMap,
    add_dates: Callable[[str, Path], str],
) -> list[Page]:
    """
    Copy a default section's pages into the build

    Numeric prefixes are dropped from every part of a page's path, and pages hide their
    breadcrumbs unless they set `bread-crumbs`.

    Parameters
    ----------
    files
        The source pages.
    source_dir
        The section's source directory.
    dest_dir
        The section's directory in the build.
    layout
        The project's directories.
    pages
        The published path of each authored page.
    add_dates
        Adds a source page's dates and authors to its text.

    Returns
    -------
    :
        The copied pages, in the order of `files`.
    """
    copied: list[Page] = []
    for source in files:
        # Copied paths and rewritten links must drop the same numeric prefixes
        published = published_path(source.relative_to(source_dir), strip_prefix=True)
        front_matter = page_publish.page(
            source,
            dest_dir / published,
            layout=layout,
            pages=pages,
            add_dates=add_dates,
            strip_prefix=True,
            breadcrumbs=True,
        )
        copied.append(
            {
                "filename": str(published),
                "title": front_matter.string("title") or title_from_name(published.stem),
                "description": front_matter.string("description") or "",
                "image": front_matter.string("image") or "",
            }
        )
    return copied


def copy_posts(
    files: Iterable[Path],
    source_dir: Path,
    dest_dir: Path,
    *,
    layout: Layout,
    pages: PageMap,
    add_dates: Callable[[str, Path], str],
) -> list[Page]:
    """
    Copy a blog's posts and the files beside them into the build

    Posts keep their paths and front matter, which Quarto's listing reads. Every other
    file in a directory that holds a post is copied too, as is each of its subdirectories
    that holds no page, so a post's relative references to images and data resolve.

    Parameters
    ----------
    files
        The source posts.
    source_dir
        The blog's source directory.
    dest_dir
        The blog's directory in the build.
    layout
        The project's directories.
    pages
        The published path of each authored page.
    add_dates
        Adds a source page's dates and authors to its text.

    Returns
    -------
    :
        The copied posts, in the order of `files`.
    """
    copied: list[Page] = []
    post_dirs: set[Path] = set()
    for source in files:
        relative = source.relative_to(source_dir)
        post_dirs.add(source.parent)
        front_matter = page_publish.page(
            source,
            dest_dir / relative,
            layout=layout,
            pages=pages,
            add_dates=add_dates,
            strip_prefix=False,
            breadcrumbs=False,
        )
        copied.append(
            {
                "filename": str(relative),
                "title": front_matter.string("title") or title_from_name(relative.stem),
                "description": front_matter.string("description") or "",
            }
        )

    for post_dir in post_dirs:
        for item in post_dir.iterdir():
            if item.is_file() and item.suffix.lower() not in _CONTENT_SUFFIXES:
                target = dest_dir / item.relative_to(source_dir)
                target.parent.mkdir(parents=True, exist_ok=True)
                _ = shutil.copy2(item, target)
        for item in post_dir.iterdir():
            if item.is_dir() and not any(
                file.suffix in _CONTENT_SUFFIXES for file in item.rglob("*")
            ):
                target = dest_dir / item.relative_to(source_dir)
                if target.exists():
                    shutil.rmtree(target)
                _ = shutil.copytree(item, target)
    return copied


def blog_index(title: str) -> str:
    """
    Generate a blog listing page with posts ordered newest first

    Parameters
    ----------
    title
        The blog's title.

    Returns
    -------
    :
        The page source.
    """
    lines = [
        "---",
        f"title: {_yaml_string(title)}",
        "listing:",
        "  type: default",
        '  sort: "date desc"',
        "  contents:",
        '    - "**.qmd"',
        "bread-crumbs: false",
        "toc: false",
        "body-classes: gd-blog-index",
        "---",
        "",
    ]
    return "\n".join(lines)


@dataclass(frozen=True)
class _PageGroup:
    """Pages the sidebar lists together"""

    title: Any
    """The sidebar section title, unused when `titled` is false"""

    pages: tuple[Page, ...]
    """The pages, in the order the sidebar lists them"""

    titled: bool
    """Whether the sidebar gives these pages a section heading"""


def _page_groups(
    pages: Sequence[Page],
    *,
    dir_titles: dict[str, str] | None = None,
    sidebar_groups: list[dict[str, Any]] | None = None,
) -> list[_PageGroup]:
    """
    Group pages the way the sidebar lists them

    `index.qmd` is the section index, not a listed page. With `sidebar_groups`, each
    configured group that names a page becomes a titled group, and pages it does not name
    follow in one untitled group. Otherwise top-level pages form one untitled group and
    each first-level subdirectory a titled group, in the order its first page appears.
    A duplicate filename keeps the last page at the first position, matching the sidebar.

    Parameters
    ----------
    pages
        The section's pages.
    dir_titles
        Group titles keyed by subdirectory name without its numeric prefix.
    sidebar_groups
        Groups, each a `section` title and the published file names of its `contents`.

    Returns
    -------
    :
        The groups. An untitled group has `titled` false.
    """
    by_filename = {page["filename"]: page for page in pages if page["filename"] != "index.qmd"}
    if sidebar_groups:
        grouped: set[str] = set()
        groups: list[_PageGroup] = []
        for group in sidebar_groups:
            members: list[Page] = []
            for filename in group.get("contents", []):
                page = by_filename.get(filename)
                if page:
                    members.append(page)
                    grouped.add(filename)
            if members:
                groups.append(
                    _PageGroup(title=group.get("section", ""), pages=tuple(members), titled=True)
                )
        rest = tuple(page for filename, page in by_filename.items() if filename not in grouped)
        if rest:
            groups.append(_PageGroup(title=None, pages=rest, titled=False))
        return groups

    top_level: list[Page] = []
    subdirectories: dict[str, list[Page]] = {}
    for page in by_filename.values():
        parts = PurePosixPath(page["filename"]).parts
        if len(parts) > 1:
            subdirectories.setdefault(parts[0], []).append(page)
        else:
            top_level.append(page)

    directory_groups: list[_PageGroup] = []
    if top_level:
        directory_groups.append(_PageGroup(title=None, pages=tuple(top_level), titled=False))
    titles = dir_titles or {}
    # Pages arrive in source order with numeric prefixes intact in that order, so
    # first appearance follows the author's ordering where a sort by the stripped
    # names would not.
    for subdirectory, group_pages in subdirectories.items():
        name = strip_numeric_prefix(subdirectory)
        directory_groups.append(
            _PageGroup(
                title=titles.get(name, title_from_name(name)),
                pages=tuple(group_pages),
                titled=True,
            )
        )
    return directory_groups


def _markdown_heading(title: object) -> str:
    """
    Return a level-2 heading whose text is `title`

    A newline would end the heading or start another block. `<` would start raw HTML.
    A hash would close the heading, and a backslash would escape the character after it,
    including the newline that ends the heading.

    Parameters
    ----------
    title
        The heading text. `None` is an empty heading.

    Returns
    -------
    :
        The heading.
    """
    text = "" if title is None else str(title)
    text = " ".join(text.splitlines())
    text = html.escape(text, quote=False)
    text = text.replace("\\", "\\\\").replace("#", "\\#")
    return f"## {text}"


def _column_opener(columns: int) -> str:
    """
    Return the opening tag of a card grid with `columns` columns

    Parameters
    ----------
    columns
        The requested column count, clamped to 1 or 2.

    Returns
    -------
    :
        The `<div>` tag.
    """
    columns = max(1, min(columns, 2))
    if columns == 1:
        col_cls = "section-cards-1col"
        grid_style = "display: grid; grid-template-columns: 1fr; gap: 1rem; margin-top: 0.5rem;"
    else:
        col_cls = "section-cards-2col"
        grid_style = (
            "display: grid; "
            "grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); "
            "gap: 1rem; "
            "margin-top: 0.5rem;"
        )
    return f'<div class="section-cards {col_cls}" style="{grid_style}">'


def _card_grid(entries: Sequence[Page], opener: str, *, image: bool | None) -> str:
    """
    Return one HTML block of cards

    The block has no blank lines, so Quarto's Markdown parser does not split it into
    paragraphs or duplicate anchors. `image` true draws every card's image, false draws
    none, and `None` draws an image only when the page has one.

    Parameters
    ----------
    entries
        The pages. Empty input is not used.
    opener
        The grid's opening `<div>` tag.
    image
        Whether to draw card images.

    Returns
    -------
    :
        The grid, closed by `</div>` on the last line.
    """
    card_style = (
        "display: block; "
        "padding: 1.25rem 1.5rem; "
        "border: 1px solid #dee2e6; "
        "border-radius: 0.5rem; "
        "color: inherit; "
        "text-decoration: none;"
    )
    title_style = "font-size: 1.1rem; font-weight: 600; margin-bottom: 0.35rem; color: #0d6efd;"
    desc_style = "font-size: 0.9rem; color: #6c757d; line-height: 1.45;"
    parts = [opener]
    for entry in entries:
        parts.append(
            f'<a href="{html.escape(entry["filename"])}" class="section-card" style="{card_style}">'
        )
        show_image = image if image is not None else bool(entry.get("image"))
        if show_image:
            parts.append(
                f'<img src="{html.escape(entry.get("image", ""))}" class="section-card-img" '
                'style="width: 100%; border-radius: 0.375rem; '
                'margin-bottom: 0.75rem;" />'
            )
        parts.extend(_card_text(entry, title_style, desc_style))
        parts.append("</a>")
    parts[-1] = parts[-1] + "</div>"
    return "\n".join(parts)


def _flat_cards(entries: Sequence[Page], columns: int) -> str:
    """
    Return the flat index body: image cards, then plain cards

    Parameters
    ----------
    entries
        The pages, excluding `index.qmd`.
    columns
        The number of columns of image cards, clamped to 1 or 2.

    Returns
    -------
    :
        The card HTML. A horizontal rule separates the two kinds when both are present.
    """
    image_entries = [entry for entry in entries if entry.get("image")]
    plain_entries = [entry for entry in entries if not entry.get("image")]
    parts: list[str] = []
    if image_entries:
        parts.append(_card_grid(image_entries, _column_opener(columns), image=True))
    if image_entries and plain_entries:
        parts.append("<hr>")
    if plain_entries:
        parts.append(
            _card_grid(
                plain_entries,
                (
                    '<div class="section-cards section-cards-list" '
                    'style="display: grid; grid-template-columns: 1fr; '
                    'gap: 1rem; margin-top: 0.5rem;">'
                ),
                image=False,
            )
        )
    return "\n".join(parts)


def card_index(
    title: str,
    pages: Sequence[Page],
    columns: int = 2,
    *,
    dir_titles: dict[str, str] | None = None,
    sidebar_groups: list[dict[str, Any]] | None = None,
    index_groups: bool = True,
) -> str:
    """
    Generate a section index with a card for each page

    When the sidebar groups the pages and `index_groups` is set, the index uses those
    groups, titles, and order. Each group is one card grid. A titled group follows a
    Markdown heading, so the page table of contents can list it. A page without an
    image stays in its group. An untitled group — top-level pages before subdirectory
    groups, or pages `sidebar_groups` does not name — is a grid with no heading.

    Otherwise pages with an `image` get image cards in a grid and the others follow as
    a list of plain cards. A horizontal rule separates the two kinds when both are
    present. A section with no sidebar groups keeps this layout.

    Parameters
    ----------
    title
        The section's title.
    pages
        The section's pages; a page named `index.qmd` gets no card.
    columns
        The number of columns of a card grid, clamped to 1 or 2. The flat layout uses
        it for image cards only.
    dir_titles
        Group titles keyed by subdirectory name without its numeric prefix.
    sidebar_groups
        Groups, each a `section` title and the published file names of its `contents`.
    index_groups
        When false, keep the flat layout even if the sidebar has groups.

    Returns
    -------
    :
        The page source.
    """
    lines = [
        "---",
        f"title: {_yaml_string(title)}",
        "bread-crumbs: false",
        "---",
        "",
    ]
    groups = (
        _page_groups(pages, dir_titles=dir_titles, sidebar_groups=sidebar_groups)
        if index_groups
        else []
    )
    if any(group.titled for group in groups):
        blocks: list[str] = []
        for group in groups:
            if group.titled:
                blocks.append(_markdown_heading(group.title))
            blocks.append(_card_grid(group.pages, _column_opener(columns), image=None))
        lines.append("\n\n".join(blocks))
    else:
        entries = [page for page in pages if page["filename"] != "index.qmd"]
        if not entries:
            lines.append("*No pages found.*")
        else:
            lines.append(_flat_cards(entries, columns))

    lines.append("")
    return "\n".join(lines)


def _yaml_string(text: str) -> str:
    """
    Return text as a double-quoted YAML scalar

    Parameters
    ----------
    text
        The text.

    Returns
    -------
    :
        A JSON string, which YAML reads back as `text`.
    """
    return json.dumps(str(text), ensure_ascii=False)


def _card_text(entry: Page, title_style: str, desc_style: str) -> list[str]:
    """
    Write the title and description lines of a page's card

    Parameters
    ----------
    entry
        The page.
    title_style
        The inline style of the title.
    desc_style
        The inline style of the description.

    Returns
    -------
    :
        The title line, then the description line when the page has a description.
    """
    title = html.escape(entry["title"], quote=False)
    lines = [f'<div class="section-card-title" style="{title_style}">{title}</div>']
    description = entry.get("description", "")
    if description:
        description = html.escape(description, quote=False)
        lines.append(f'<div class="section-card-desc" style="{desc_style}">{description}</div>')
    return lines


def sidebar(
    title: str,
    slug: str,
    pages: Sequence[Page],
    *,
    has_index: bool,
    dir_titles: dict[str, str] | None = None,
    sidebar_groups: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """
    Make a section's sidebar

    The sidebar starts with the section's index when it has one. With `sidebar_groups`,
    the grouped pages follow under their group titles and the other pages after them.
    Otherwise top-level pages follow in order, then each subdirectory as a group titled by
    `dir_titles` or by its name, in the order its first page appears. The generated card
    index uses this same grouping.

    Parameters
    ----------
    title
        The section's title.
    slug
        The section's directory relative to the build directory.
    pages
        The section's pages.
    has_index
        Whether the section has an index page.
    dir_titles
        Group titles keyed by subdirectory name without its numeric prefix.
    sidebar_groups
        Groups, each a `section` title and the published file names of its `contents`.

    Returns
    -------
    :
        The sidebar, with `slug` as its `id`, or `None` if the section has at most one
        page, including its index.
    """
    by_filename = {page["filename"]: page for page in pages if page["filename"] != "index.qmd"}
    # Count pages, including the index: one top-level subdirectory can contain
    # several pages that need sidebar navigation.
    if (1 if has_index else 0) + len(by_filename) <= 1:
        return None

    contents: list[dict[str, Any]] = []
    if has_index:
        contents.append({"text": title, "href": f"{slug}/index.qmd"})

    def link(page: Page) -> dict[str, Any]:
        return {"text": page["title"], "href": f"{slug}/{page['filename']}"}

    for group in _page_groups(pages, dir_titles=dir_titles, sidebar_groups=sidebar_groups):
        links = [link(page) for page in group.pages]
        if group.titled:
            contents.append({"section": group.title, "contents": links})
        else:
            contents.extend(links)

    return {"id": slug, "title": title, "contents": contents}


def add_no_sidebar_class(pages: Iterable[Page], dest_dir: Path) -> None:
    """
    Add the `gd-section-no-sidebar` body class to pages

    The class lets a page's content take the width a sidebar would. It joins any
    `body-classes` the page sets. Pages that are missing or have no
    front matter are left unchanged.

    Parameters
    ----------
    pages
        The pages.
    dest_dir
        The section's directory in the build.

    Returns
    -------
    :
    """
    for page in pages:
        path = dest_dir / page["filename"]
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        block = locate_front_matter(content)
        if block is None:
            continue
        classes = " ".join(block.mapping.strings("body-classes")).split()
        if _NO_SIDEBAR_CLASS not in classes:
            classes.append(_NO_SIDEBAR_CLASS)
            updated = {**block.mapping.data, "body-classes": " ".join(classes)}
            _ = path.write_text(
                f"---\n{format_yaml(updated)}\n---\n{content[block.end :]}", encoding="utf-8"
            )
