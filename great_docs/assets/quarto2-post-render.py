"""
Finish the pages a Quarto 2 render wrote (post-render, experimental)

- Quarto 1 rewrites an `href`, `src` or `poster` that starts with `/` relative to each page,
  in header includes and raw HTML alike. Quarto 2 leaves them as written, so they load only
  when the site is served from the root of a domain, and never from a file. This script
  does the rewriting. Script and style element contents, and comments, are left alone.
- Quarto 2 sets no text direction on the root element, and writes a page's `body-classes`
  in place of the classes it computes for the layout. The gd-quarto2 filter records the
  page's direction and classes in `<meta>` tags, which this script moves onto `<html>` and
  `<body>`.
"""

import html as entities
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
_MARKER = re.compile(r'<meta name="gd-(?P<name>body-classes|dir)" content="(?P<value>[^"]*)">\n?')
_ROOT = re.compile(r"<html\b[^>]*>", re.IGNORECASE)
_BODY = re.compile(r"<body\b[^>]*>", re.IGNORECASE)
_DIR = re.compile(r"""\sdir=(["']).*?\1""", re.IGNORECASE)
_CLASS = re.compile(r"""(\sclass=)(["'])(.*?)\2""", re.IGNORECASE)


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


def apply_markers(html):
    """Move the gd-quarto2 filter's direction and classes onto `<html>` and `<body>`"""
    markers = {}

    def take(match):
        markers[match.group("name")] = entities.unescape(match.group("value"))
        return ""

    html = _MARKER.sub(take, html)
    direction = markers.get("dir")
    if direction:

        def set_dir(match):
            opening = _DIR.sub("", match.group(0))
            return f'{opening[:-1].rstrip()} dir="{entities.escape(direction)}">'

        html = _ROOT.sub(set_dir, html, count=1)
    classes = markers.get("body-classes", "").split()
    if classes:

        def add_classes(match):
            opening = match.group(0)
            existing = _CLASS.search(opening)
            if existing is None:
                joined = entities.escape(" ".join(classes))
                return f'{opening[:-1].rstrip()} class="{joined}">'
            names = existing.group(3).split()
            names += [name for name in classes if name not in names]
            replacement = f'{existing.group(1)}"{entities.escape(" ".join(names))}"'
            return opening[: existing.start()] + replacement + opening[existing.end() :]

        html = _BODY.sub(add_classes, html, count=1)
    return html


def main():
    output_dir = _output_dir()
    if not output_dir.is_dir():
        return
    for page in _rendered_pages(output_dir):
        html = page.read_text(encoding="utf-8")
        finished = apply_markers(rewrite(html, _offset(page, output_dir)))
        if finished != html:
            page.write_text(finished, encoding="utf-8")


if __name__ == "__main__":
    main()
