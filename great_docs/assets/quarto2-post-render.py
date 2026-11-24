"""
Finish the pages a Quarto 2 render wrote (post-render, experimental)

Quarto 1 rewrites an `href`, `src` or `poster` that starts with `/` relative to each page,
in header includes and raw HTML alike. Quarto 2 leaves them as written, so they load only
when the site is served from the root of a domain, and never from a file. This script does
the rewriting. Script and style element contents, and comments, are left alone.

Quarto 2 also leaves `.column-margin` content out of the page grid, so the homepage's
metadata sidebar sits in the body column. This script puts it in the right margin.
"""

import os
import re
from pathlib import Path, PurePosixPath

build_dir = Path.cwd()

_TOKEN = re.compile(
    r"(?P<script><script\b[^>]*>)(?:.*?)</script\s*>"
    r"|<!--.*?-->"
    r"|<style\b.*?</style\s*>"
    r"|(?P<tag><[a-zA-Z][^>]*>)",
    re.DOTALL | re.IGNORECASE,
)
_ATTRIBUTE = re.compile(r"""(\s(?:href|src|poster)=)(["'])/(?!/)""", re.IGNORECASE)
_CLASS = re.compile(r"""\sclass=(["'])(?P<classes>[^"']*)\1""", re.IGNORECASE)
_TAG_NAME = re.compile(r"<([a-zA-Z][a-zA-Z0-9-]*)")


def _output_dir():
    """Return the site's output directory"""
    output = os.environ.get("QUARTO_PROJECT_OUTPUT_DIR", "_site")
    return (build_dir / output).resolve()


def _rendered_pages(output_dir):
    """Return the HTML pages this render wrote"""
    listing = os.environ.get("QUARTO_USE_FILE_FOR_PROJECT_OUTPUT_FILES")
    if os.environ.get("QUARTO_PROJECT_RENDER_ALL"):
        text = ""
    elif listing:
        text = Path(listing).read_text(encoding="utf-8")
    else:
        text = os.environ.get("QUARTO_PROJECT_OUTPUT_FILES", "")
    pages = []
    for line in text.splitlines():
        if line.strip().endswith(".html"):
            path = (build_dir / line.strip()).resolve()
            if path.is_file() and path.is_relative_to(output_dir):
                pages.append(path)
    return pages or list(output_dir.rglob("*.html"))


def _offset(page, output_dir):
    """Return the prefix that leads from a page to the site root"""
    depth = len(PurePosixPath(page.relative_to(output_dir).as_posix()).parts) - 1
    return "../" * depth


def rewrite(html, offset):
    """Make each root-relative address in a page's markup start with `offset`"""

    def tag(markup):
        return _ATTRIBUTE.sub(lambda m: m.group(1) + m.group(2) + (offset or "./"), markup)

    def token(match):
        if match.group("script"):
            opening = match.group("script")
            return tag(opening) + match.group(0)[len(opening) :]
        if match.group("tag"):
            return tag(match.group("tag"))
        return match.group(0)

    return _TOKEN.sub(token, html)


def _classes(markup):
    """Return the classes in a tag's markup"""
    match = _CLASS.search(markup)
    return match.group("classes").split() if match else []


def _change_classes(markup, add=(), remove=()):
    """Return a tag's markup with classes added to and removed from its `class` attribute"""
    match = _CLASS.search(markup)
    if match is None:
        return markup
    classes = [name for name in match.group("classes").split() if name not in remove]
    classes += [name for name in add if name not in classes]
    return markup[: match.start("classes")] + " ".join(classes) + markup[match.end("classes") :]


def place_homepage_sidebar(html):
    """
    Put the homepage's metadata sidebar in the right margin, as Quarto 1 does

    Quarto 2 counts no `.column-margin` content as using the right margin, so it marks the
    page `fullcontent` and leaves `<main>` off the page grid. Great Docs writes the sidebar
    directly in `<main>`, so the classes Quarto 1 writes on these three elements place it.
    """
    tags = [match.group("tag") for match in _TOKEN.finditer(html) if match.group("tag")]
    if not any({"column-margin", "gd-homepage-sidebar"} <= set(_classes(tag)) for tag in tags):
        return html

    def token(match):
        markup = match.group("tag")
        if markup is None:
            return match.group(0)
        name = _TAG_NAME.match(markup).group(1).lower()
        classes = _classes(markup)
        if name == "main" and "content" in classes:
            return _change_classes(markup, add=("page-columns", "page-full"))
        if name == "body":
            return _change_classes(markup, remove=("fullcontent",))
        if {"column-margin", "gd-homepage-sidebar"} <= set(classes):
            return _change_classes(markup, add=("no-row-height", "column-container"))
        return markup

    return _TOKEN.sub(token, html)


def main():
    output_dir = _output_dir()
    if not output_dir.is_dir():
        return
    for page in _rendered_pages(output_dir):
        html = page.read_text(encoding="utf-8")
        finished = rewrite(place_homepage_sidebar(html), _offset(page, output_dir))
        if finished != html:
            page.write_text(finished, encoding="utf-8")


if __name__ == "__main__":
    main()
