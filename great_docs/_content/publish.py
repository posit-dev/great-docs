"""Publication of authored pages and their referenced files in the build directory"""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from yaml12 import format_yaml

from .._source_refs import source_reference_spans
from .._yaml import YamlMapping, locate_front_matter, set_front_matter_option, split_front_matter
from . import code_includes
from .naming import fix_numeric_prefix_links

if TYPE_CHECKING:
    from collections.abc import Callable

    from .._layout import Layout
    from .pages import PageMap

_PAGE_SUFFIXES = {".qmd", ".md", ".rst", ".html", ".htm"}


def page(
    source: Path,
    destination: Path,
    *,
    layout: Layout,
    pages: PageMap,
    add_dates: Callable[[str, Path], str],
    strip_prefix: bool,
    breadcrumbs: Literal["default", "set"] | None,
    published: Path | None = None,
) -> YamlMapping:
    """
    Write an authored Markdown page to the build directory

    The page's code includes are expanded and its references are rewritten for its
    published path. Dates are added unless a later step moves the page to the homepage.

    Parameters
    ----------
    source
        The page's source file.
    destination
        The path where the page is written.
    layout
        The project's directories.
    pages
        The published path of each authored page.
    add_dates
        A callable that adds the source page's dates and authors to its text.
    strip_prefix
        Whether the page's directory publishes names without numeric ordering prefixes.
        When true, links to `.qmd` pages also drop those prefixes.
    breadcrumbs
        How to hide breadcrumbs while preserving an authored `bread-crumbs` value.
        `"set"` adds `bread-crumbs: false` and creates front matter if absent. `"default"`
        adds it only to existing front matter. `None` preserves the front matter.
    published
        The final published path if a later step moves the page from `destination`.
        References are rewritten for this path; the page is still written to
        `destination`. Dates are omitted when this path is the homepage.

    Returns
    -------
    :
        The page's front matter, without its dates.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    target = destination if published is None else published
    content = source.read_text(encoding="utf-8")
    content = code_includes.expand(content, source.parent, layout)
    content = rebase_references(content, source, target, layout=layout, pages=pages)
    if strip_prefix:
        content = fix_numeric_prefix_links(content)
    block = locate_front_matter(content)
    authored = block is not None and "bread-crumbs" in block.mapping
    if not authored and (breadcrumbs == "set" or (breadcrumbs == "default" and block is not None)):
        content = set_front_matter_option(content, "bread-crumbs", False)
    front_matter, _ = split_front_matter(content)
    # The page that becomes the homepage shows no dates
    if published != pages.homepage:
        content = add_dates(content, source)
    _ = destination.write_text(content, encoding="utf-8")
    return front_matter


def copy_asset(layout: Layout, source: Path, destination: Path) -> Path:
    """
    Copy a referenced file into the build directory

    Parameters
    ----------
    layout
        The project's directories.
    source
        The file to copy.
    destination
        The copy destination. An identical file at this path is kept.

    Returns
    -------
    :
        The resolved destination.

    Raises
    ------
    ValueError
        If `destination` lies outside the build directory or contains a different file.
    """
    destination = destination.resolve()
    if not destination.is_relative_to(layout.build_dir.resolve()):
        raise ValueError(f"Asset destination escapes the build directory: {destination}")
    if destination.exists():
        if not destination.is_file() or destination.read_bytes() != source.read_bytes():
            raise ValueError(f"Asset destination conflicts with an existing file: {destination}")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        _ = shutil.copy2(source, destination)
    return destination


def rebase_references(
    content: str,
    source: Path,
    destination: Path,
    *,
    layout: Layout,
    pages: PageMap,
) -> str:
    """
    Rewrite a page's local references relative to its published path

    A reference to another authored page points at that page's published path. A
    reference to any other local file points at a copy in the build directory: beside the
    page when the file lies in the documentation sources, otherwise under `_shared/`. A
    page's `bibliography` files are always copied under `_shared/`. URLs, anchors, absolute
    paths and references to missing files are left as written; queries and fragments are
    kept.

    Parameters
    ----------
    content
        The page's text.
    source
        The page's source file. Relative references are resolved from its directory.
    destination
        The page's published path. Rewritten references are relative to its directory.
    layout
        The project's directories.
    pages
        The published path of each authored page.

    Returns
    -------
    :
        The page's text with its references rewritten.

    Raises
    ------
    ValueError
        If a copy would leave the build directory or replace a different file.
    """
    build_dir = layout.build_dir.resolve()

    def rebase(reference: str) -> str:
        url = urlsplit(reference)
        if url.scheme or url.netloc or not url.path or reference.startswith("/"):
            return reference
        target = (source.parent / unquote(url.path)).resolve()
        if not target.is_file():
            return reference
        if target.suffix.lower() in _PAGE_SUFFIXES:
            page = pages.destination(target)
            if page is None:
                return reference
            return _relative_url(page, destination, url.query, url.fragment)
        copy = (destination.parent / unquote(url.path)).resolve()
        if not copy.is_relative_to(build_dir) or (
            layout.source_dir != layout.package_root
            and not target.is_relative_to(layout.source_dir)
        ):
            copy = _shared_destination(layout, target)
        copied = copy_asset(layout, target, copy)
        return _relative_url(copied, destination, url.query, url.fragment)

    spans = source_reference_spans(content, html=source.suffix.lower() in {".html", ".htm"})
    for start, end in reversed(spans):
        content = content[:start] + rebase(content[start:end]) + content[end:]
    return _rebase_bibliography(content, source, destination, layout)


def _rebase_bibliography(content: str, source: Path, destination: Path, layout: Layout) -> str:
    """
    Copy a page's bibliography files under `_shared/` and point its front matter at them

    Parameters
    ----------
    content
        The page's text.
    source
        The page's source file. Bibliography paths are resolved from its directory.
    destination
        The page's published path. Rewritten paths are relative to its directory.
    layout
        The project's directories.

    Returns
    -------
    :
        The page's text. Its front matter is rewritten only when a path changes, and only
        when `bibliography` is a string or a list of strings.
    """
    block = locate_front_matter(content)
    if block is None:
        return content
    bibliography = block.mapping.get("bibliography")
    if isinstance(bibliography, str):
        entries = [bibliography]
    elif isinstance(bibliography, list) and all(isinstance(item, str) for item in bibliography):
        entries = [str(item) for item in bibliography]
    else:
        return content

    rebased: list[str] = []
    changed = False
    for reference in entries:
        url = urlsplit(reference)
        if url.scheme or url.netloc or not url.path or reference.startswith("/"):
            rebased.append(reference)
            continue
        target = (source.parent / unquote(url.path)).resolve()
        if not target.is_file():
            rebased.append(reference)
            continue
        copied = copy_asset(layout, target, _shared_destination(layout, target))
        path = Path(os.path.relpath(copied, destination.parent)).as_posix()
        rebased.append(urlunsplit(("", "", quote(path, safe="/"), url.query, url.fragment)))
        changed = changed or path != reference

    if not changed:
        return content
    value = rebased if isinstance(bibliography, list) else rebased[0]
    front_matter = {**block.mapping.data, "bibliography": value}
    return f"---\n{format_yaml(front_matter)}\n---\n{content[block.end :]}"


def _shared_destination(layout: Layout, source: Path) -> Path:
    """
    Choose a destination under `_shared/` for a file shared by pages

    Parameters
    ----------
    layout
        The project's directories.
    source
        The resolved source path.

    Returns
    -------
    :
        The file's path relative to the package root, under `_shared/`. A file outside the
        package goes in a directory named by a hash of its path, so files with the same name
        do not collide.
    """
    if source.is_relative_to(layout.package_root):
        relative = source.relative_to(layout.package_root)
    else:
        relative = Path(hashlib.sha256(str(source).encode()).hexdigest()[:16]) / source.name
    return layout.build_dir / "_shared" / relative


def _relative_url(path: Path, page: Path, query: str, fragment: str) -> str:
    """
    Write a URL for a file relative to the page that refers to it

    Parameters
    ----------
    path
        The file.
    page
        The page that refers to it.
    query
        The query to keep.
    fragment
        The fragment to keep.

    Returns
    -------
    :
        The relative, percent-encoded URL.
    """
    relative = Path(os.path.relpath(path, page.parent)).as_posix()
    return urlunsplit(("", "", quote(relative, safe="/"), query, fragment))
