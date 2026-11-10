"""
The user guide: authored pages that the build publishes under `user-guide/`

A list in the `user_guide` setting defines the page and section order and preserves file
names. Otherwise, discovery collects `.qmd` and `.md` pages from the guide directory,
orders them by path with the root `index.qmd` first, and groups them by `guide-section`
front matter or subdirectory. Published paths omit numeric ordering prefixes in this mode.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict, cast

from .._yaml import split_front_matter
from . import publish
from .naming import published_path, strip_numeric_prefix, title_from_name
from .sections import source_dirs as section_source_dirs

if TYPE_CHECKING:
    from collections.abc import Callable

    from .._project.layout import Layout
    from ..config import Config
    from .pages import PageMap

__all__ = [
    "SIDEBAR_ID",
    "GuidePage",
    "UserGuide",
    "copy_pages",
    "discover",
    "entry",
    "find_dir",
    "link_homepage",
    "published",
    "read_page",
    "sidebar",
]

SIDEBAR_ID = "user-guide"
"""The `id` of the guide's sidebar, which is also its directory in the build"""

_PAGE_SUFFIXES = {".qmd", ".md"}


class GuidePage(TypedDict):
    """A user guide page with its title and sidebar section"""

    path: Path
    """The page's source file"""

    section: str | None
    """The sidebar section that lists the page, or `None` for an ungrouped page"""

    title: str
    """The page's title, derived from the file name when the front matter has none"""

    custom_text: NotRequired[str]
    """The sidebar label that an explicit guide gives the page"""


class UserGuide(TypedDict):
    """A project's user guide pages in reading and sidebar order"""

    files: list[GuidePage]
    """The pages in reading order"""

    sections: dict[str, list[GuidePage]]
    """The pages of each sidebar section, with sections in order of first appearance"""

    has_index: bool
    """Whether the guide has an `index.qmd`"""

    source_dir: Path
    """The guide's source directory"""

    explicit: bool
    """Whether the `user_guide` setting lists the pages"""

    explicit_config: NotRequired[list[Any]]
    """The `user_guide` setting of an explicit guide"""


def find_dir(config: Config, layout: Layout, *, report: Callable[[str], None]) -> Path | None:
    """
    Find the user guide's source directory

    Use the directory named by `user_guide` when configured. Otherwise, check
    `user_guide/` then `user-guide/` under the source directory, skipping directories
    published by a `sections` entry.

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's directories.
    report
        Receives a warning when the configured directory is missing or takes precedence
        over an existing `user_guide/` directory.

    Returns
    -------
    :
        The directory, or `None` when the project has no user guide directory.
    """
    package_root = layout.source_dir
    configured_dir = config.user_guide_dir

    if configured_dir is not None:
        user_guide_dir = package_root / configured_dir

        conventional_dir = package_root / "user_guide"
        if conventional_dir.is_dir() and user_guide_dir.resolve() != conventional_dir.resolve():
            report(
                f"Both 'user_guide' config option ('{configured_dir}') and "
                f"'user_guide/' directory exist; using configured path"
            )

        if not user_guide_dir.is_dir():
            report(
                f"User guide directory '{configured_dir}' specified in great-docs.yml does not exist"
            )
            return None

        return user_guide_dir

    claimed = section_source_dirs(config, layout)
    for name in ("user_guide", "user-guide"):
        user_guide_dir = package_root / name
        if user_guide_dir.is_dir() and user_guide_dir.resolve() not in claimed:
            return user_guide_dir

    return None


def discover(config: Config, layout: Layout, *, report: Callable[[str], None]) -> UserGuide | None:
    """
    Discover the pages of the project's user guide

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's directories.
    report
        Receives directory warnings and a warning for each missing page listed in an
        explicit guide. Also receives a warning when automatic discovery finds an empty
        directory or no `.qmd` or `.md` files.

    Returns
    -------
    :
        The guide, or `None` when the project has no guide pages.
    """
    user_guide_dir = find_dir(config, layout, report=report)
    if user_guide_dir is None:
        return None

    user_guide_config = config.user_guide
    if isinstance(user_guide_config, list):
        return _discover_explicit(user_guide_dir, user_guide_config, report=report)

    dir_contents = list(user_guide_dir.iterdir())
    if not dir_contents:
        report(f"User guide directory '{user_guide_dir}' is empty")
        return None

    guide_files: list[Path] = []
    for item in dir_contents:
        if item.is_file() and item.suffix in _PAGE_SUFFIXES:
            guide_files.append(item)
        elif item.is_dir() and not layout.is_reserved_directory(item):
            for suffix in _PAGE_SUFFIXES:
                guide_files.extend(path for path in item.rglob(f"*{suffix}") if path.is_file())

    if not guide_files:
        report(f"User guide directory '{user_guide_dir}' contains no .qmd or .md files")
        return None

    # Root pages come before nested pages, and in each group `index.qmd` files come first
    guide_files.sort(
        key=lambda p: (
            p.parent != user_guide_dir,
            p.name != "index.qmd",
            p.relative_to(user_guide_dir),
        )
    )

    files: list[GuidePage] = []
    sections: dict[str, list[GuidePage]] = {}
    has_index = False
    for path in guide_files:
        page = read_page(path)
        if page is None:
            continue
        files.append(page)
        # A subdirectory's `index.qmd` titles its sidebar section; it is not the guide's index
        if path.name == "index.qmd" and path.parent == user_guide_dir:
            has_index = True
        if page["section"]:
            sections.setdefault(page["section"], []).append(page)

    if not files:
        return None

    return {
        "files": files,
        "sections": sections,
        "has_index": has_index,
        "source_dir": user_guide_dir,
        "explicit": False,
    }


def _discover_explicit(
    user_guide_dir: Path, explicit_config: list[Any], *, report: Callable[[str], None]
) -> UserGuide | None:
    """
    Collect the pages that the `user_guide` setting lists

    Parameters
    ----------
    user_guide_dir
        The guide's source directory. Listed page paths are relative to it.
    explicit_config
        The configured sections and their page lists, in reading order.
    report
        Receives a warning for each missing page, absolute path, or path with a `..`
        component.

    Returns
    -------
    :
        The guide, or `None` when no listed page can be read. Repeated file names appear
        once, in the first section that lists them.
    """
    files: list[GuidePage] = []
    sections: dict[str, list[GuidePage]] = {}
    has_index = False
    seen_files: set[str] = set()

    for section_entry in explicit_config:
        entry = cast("dict[str, Any]", section_entry)
        section_name = cast("str", entry.get("section", ""))
        section_contents = cast("list[Any]", entry.get("contents", []))
        if not section_name or not section_contents:
            continue

        section_files: list[GuidePage] = []
        for item in section_contents:
            filename, custom_text = _listed_page(item)
            if not filename or filename in seen_files:
                continue

            if not _is_inside_guide(filename):
                report(
                    f"User guide file '{filename}' referenced in config "
                    "must be a path inside the user guide directory"
                )
                continue

            file_path = user_guide_dir / filename
            if not file_path.exists():
                report(f"User guide file '{filename}' referenced in config does not exist")
                continue
            seen_files.add(filename)

            page = read_page(file_path)
            if page is None:
                continue

            page["section"] = section_name
            if custom_text:
                page["custom_text"] = custom_text
            files.append(page)
            section_files.append(page)

            if file_path.name == "index.qmd":
                has_index = True

        if section_files:
            sections[section_name] = section_files

    if not files:
        return None

    return {
        "files": files,
        "sections": sections,
        "has_index": has_index,
        "source_dir": user_guide_dir,
        "explicit": True,
        "explicit_config": explicit_config,
    }


def _is_inside_guide(filename: str) -> bool:
    """
    Check whether a listed page path is allowed in an explicit guide

    Parameters
    ----------
    filename
        A page path from the `user_guide` setting.

    Returns
    -------
    :
        `True` for a relative path with no `..` components; `False` otherwise.
        Symbolic links are not resolved.
    """
    path = Path(filename)
    return not (path.is_absolute() or ".." in path.parts)


def _listed_page(item: object) -> tuple[str, str | None]:
    """
    Read a listed page's file name and optional sidebar label

    Parameters
    ----------
    item
        A file name, or a mapping with the file name under `href` and an optional sidebar
        label under `text`.

    Returns
    -------
    :
        The file name and sidebar label. An unnamed file is `""`; an absent label is `None`.
    """
    if isinstance(item, str):
        return item, None
    if isinstance(item, dict):
        entry = cast("dict[str, Any]", item)
        return cast("str", entry.get("href", "")), cast("str | None", entry.get("text"))
    return "", None


def read_page(path: Path) -> GuidePage | None:
    """
    Read a user guide page's title and sidebar section

    Parameters
    ----------
    path
        The page's source file.

    Returns
    -------
    :
        The page, with the section from its `guide-section` front matter and a title from
        its `title` front matter or its file name. `None` when the file cannot be read or
        decoded.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    front_matter, _ = split_front_matter(content)
    # Titles omit numeric ordering prefixes even when published file names retain them
    title = front_matter.string("title") or title_from_name(strip_numeric_prefix(path.stem))
    # Quarto reserves `section`, so guide grouping uses `guide-section`
    section = front_matter.string("guide-section")
    return {"path": path, "section": section, "title": title}


def published(guide: UserGuide, page: GuidePage) -> Path:
    """
    Find a page's published path relative to `user-guide/`

    Parameters
    ----------
    guide
        The user guide.
    page
        One of the guide's pages.

    Returns
    -------
    :
        The relative path. Explicit guides retain listed file names; automatic guides
        omit numeric ordering prefixes from every path component.
    """
    rel_path = page["path"].relative_to(guide["source_dir"])
    return published_path(rel_path, strip_prefix=not guide.get("explicit", False))


def entry(guide: UserGuide) -> str:
    """
    Find the navbar target for the guide's first published page

    Parameters
    ----------
    guide
        The user guide.

    Returns
    -------
    :
        The path, relative to the build directory, of the guide's first page that the
        sidebar lists, such as `"user-guide/basics/setup.qmd"`. A subdirectory's
        `index.qmd` only titles its section, so a guide without a root `index.qmd` opens on
        the first section's first page. A sidebar that lists no pages falls back to the
        guide's first file.
    """
    hrefs = [f"{SIDEBAR_ID}/{published(guide, page)}" for page in guide["files"]]
    listed = set(_hrefs(sidebar(guide)["contents"]))
    return next((href for href in hrefs if href in listed), hrefs[0])


def _hrefs(contents: list[Any]) -> list[str]:
    """
    List the pages a sidebar links to

    Parameters
    ----------
    contents
        Sidebar entries: page paths, linked entries and sections.

    Returns
    -------
    :
        The pages' paths, in sidebar order.
    """
    hrefs: list[str] = []
    for item in contents:
        if isinstance(item, str):
            hrefs.append(item)
        elif href := item.get("href"):
            hrefs.append(href)
        else:
            hrefs.extend(_hrefs(item.get("contents", [])))
    return hrefs


def copy_pages(
    guide: UserGuide,
    destination: Path,
    *,
    layout: Layout,
    pages: PageMap,
    add_dates: Callable[[str, Path], str],
) -> list[str]:
    """
    Copy the guide's pages into the build directory

    Pages hide breadcrumbs unless their front matter sets `bread-crumbs`.

    Parameters
    ----------
    guide
        The user guide.
    destination
        The guide's directory in the build.
    layout
        The project's directories.
    pages
        The published path of each authored page.
    add_dates
        Adds a source page's dates and authors to its text.

    Returns
    -------
    :
        The copied pages' paths relative to the build directory, in reading order.
    """
    destination.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for page in guide["files"]:
        source = page["path"]
        dest_rel_path = published(guide, page)
        dst_path = destination / dest_rel_path
        # The first guide page moves to the homepage later when `homepage: user_guide`
        _ = publish.page(
            source,
            dst_path,
            layout=layout,
            pages=pages,
            add_dates=add_dates,
            strip_prefix=not guide.get("explicit", False),
            breadcrumbs=True,
            published=pages.destination(source.resolve()) or dst_path,
        )
        copied.append(f"{SIDEBAR_ID}/{dest_rel_path}")
    return copied


def sidebar(guide: UserGuide) -> dict[str, Any]:
    """
    Build the guide's sidebar

    Parameters
    ----------
    guide
        The user guide.

    Returns
    -------
    :
        The sidebar for Quarto's `website.sidebar`. Explicit guides use the configured
        sections and labels. Automatic guides group pages by `guide-section` when set,
        or by subdirectory otherwise. A subdirectory's `index.qmd` supplies its title.
    """
    contents = _explicit_contents(guide) if guide.get("explicit") else _auto_contents(guide)
    return {"id": SIDEBAR_ID, "title": "User Guide", "contents": contents}


def _explicit_contents(guide: UserGuide) -> list[Any]:
    """
    List an explicit guide's sidebar entries

    Parameters
    ----------
    guide
        An explicit user guide.

    Returns
    -------
    :
        One section per configured section with existing pages. Each entry is labelled with
        its configured text or the page's title, and keeps the listed file name.
    """
    source_dir = guide["source_dir"]
    title_lookup = {
        page["path"].relative_to(source_dir).as_posix(): page["title"]
        for page in guide.get("files", [])
        if page.get("title")
    }
    contents: list[Any] = []

    for section_entry in guide.get("explicit_config", []):
        entry = cast("dict[str, Any]", section_entry)
        section_name = cast("str", entry.get("section", ""))
        section_contents = cast("list[Any]", entry.get("contents", []))
        if not section_name or not section_contents:
            continue

        items: list[Any] = []
        for item in section_contents:
            filename, custom_text = _listed_page(item)
            if not filename or not _is_inside_guide(filename):
                continue
            if not (source_dir / filename).exists():
                continue

            href = f"{SIDEBAR_ID}/{filename}"
            text = custom_text or title_lookup.get(filename)
            items.append({"text": text, "href": href} if text else href)

        if items:
            contents.append({"section": section_name, "contents": items})

    return contents


def _auto_contents(guide: UserGuide) -> list[Any]:
    """
    List a discovered guide's sidebar entries

    Parameters
    ----------
    guide
        A user guide discovered from its directory.

    Returns
    -------
    :
        With `guide-section` pages: one section per name in order of first appearance,
        then the ungrouped pages. Otherwise, with subdirectories: the root `index.qmd`, then
        root pages and one section per subdirectory, ordered by name. Otherwise the pages in
        reading order.
    """
    source_dir = guide["source_dir"]
    files = guide["files"]
    sections = guide["sections"]

    def link(page: GuidePage) -> Any:
        rel_path = page["path"].relative_to(source_dir)
        href = f"{SIDEBAR_ID}/{published_path(rel_path, strip_prefix=True)}"
        if page.get("title"):
            return {"text": page["title"], "href": href}
        return href

    contents: list[Any] = []

    if sections:
        # Sections follow the reading order of their first pages
        order = dict.fromkeys(section for page in files if (section := page.get("section")))
        assigned: set[Path] = set()
        for section_name in order:
            section_pages = sections[section_name]
            assigned.update(page["path"] for page in section_pages)
            contents.append(
                {"section": section_name, "contents": [link(page) for page in section_pages]}
            )
        contents.extend(link(page) for page in files if page["path"] not in assigned)
        return contents

    subdirs: dict[str, list[GuidePage]] = {}
    root_files: list[GuidePage] = []
    for page in files:
        parent = page["path"].relative_to(source_dir).parent
        if parent == Path("."):
            root_files.append(page)
        else:
            subdirs.setdefault(str(parent), []).append(page)

    if not subdirs:
        return [link(page) for page in files]

    root_index = next((page for page in root_files if page["path"].name == "index.qmd"), None)
    if root_index is not None:
        contents.append(link(root_index))

    # Files and directory sections sort together, so numeric prefixes set the order
    nav_items: list[tuple[str, GuidePage | str, list[GuidePage]]] = [
        (page["path"].name, page, []) for page in root_files if page["path"].name != "index.qmd"
    ]
    nav_items.extend(
        (Path(subdir).parts[0], subdir, dir_pages) for subdir, dir_pages in subdirs.items()
    )
    nav_items.sort(key=lambda item: item[0])

    for _, item, dir_pages in nav_items:
        if not isinstance(item, str):
            contents.append(link(item))
            continue
        section_title = title_from_name(strip_numeric_prefix(item))
        section_contents: list[Any] = []
        for page in dir_pages:
            if page["path"].name == "index.qmd":
                section_title = page["title"]
            else:
                section_contents.append(link(page))
        contents.append({"section": section_title, "contents": section_contents})

    return contents


def link_homepage(guide_sidebar: dict[str, Any], href: str) -> None:
    """
    Point the promoted homepage's sidebar entry at `index.qmd`

    Parameters
    ----------
    guide_sidebar
        The guide's sidebar, changed in place.
    href
        The promoted page's former link, such as `"user-guide/introduction.qmd"`. Only the
        first matching entry changes. A bare link becomes an entry labelled "Home".

    Returns
    -------
    :
    """
    _ = _replace_href(cast("list[Any]", guide_sidebar.get("contents", [])), href, "index.qmd")


def _replace_href(items: list[Any], old_href: str, new_href: str) -> bool:
    """
    Replace the first link to `old_href` in a sidebar tree

    Parameters
    ----------
    items
        Sidebar entries, changed in place.
    old_href
        The link to replace.
    new_href
        The replacement link.

    Returns
    -------
    :
        Whether a link was replaced.
    """
    for index, item in enumerate(items):
        if isinstance(item, dict):
            entry = cast("dict[str, Any]", item)
            if entry.get("href") == old_href:
                entry["href"] = new_href
                return True
            nested = cast("list[Any]", entry.get("contents", []))
            if nested and _replace_href(nested, old_href, new_href):
                return True
        elif item == old_href:
            items[index] = {"text": "Home", "href": new_href}
            return True
    return False
