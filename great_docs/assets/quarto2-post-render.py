"""
Finish the pages a Quarto 2 render wrote (post-render, experimental)

Quarto 1 rewrites an `href`, `src` or `poster` that starts with `/` relative to each page,
in header includes and raw HTML alike. Quarto 2 leaves them as written, so they load only
when the site is served from the root of a domain, and never from a file. This script does
the rewriting. Script and style element contents, and comments, are left alone.
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


def main():
    output_dir = _output_dir()
    if not output_dir.is_dir():
        return
    for page in _rendered_pages(output_dir):
        html = page.read_text(encoding="utf-8")
        finished = rewrite(html, _offset(page, output_dir))
        if finished != html:
            page.write_text(finished, encoding="utf-8")


if __name__ == "__main__":
    main()
