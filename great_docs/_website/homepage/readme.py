"""
Clean-up of README Markdown for the homepage

The hero shows a README's badges, logo and tagline, so they are taken out of the body. The
body's headings sit one level below the homepage's.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "Badge",
    "HeroElements",
    "bump_heading_levels",
    "extract_hero_elements",
    "strip_duplicate_title",
]

_BADGE_HOSTS = (
    "img.shields.io",
    "badge.fury.io",
    "github.com/",  # GitHub Actions badge URLs contain /badge.svg
    "codecov.io",
    "readthedocs.org",
    "repostatus.org",
    "pepy.tech",
    "pyopensci.org",
    "zenodo.org/badge",
    "www.contributor-covenant.org",
    "deepwiki.com",
    "static.pepy.tech",
)

# [![alt](img_url)](link_url)
_MD_BADGE = re.compile(r"\[!\[([^\]]*)\]\(([^)]+)\)\]\(([^)]+)\)")
_CENTRED_DIV = re.compile(r'^<div\s+align=["\']center["\']', re.IGNORECASE)
_DIV_OPEN = re.compile(r"<div[\s>]", re.IGNORECASE)
_DIV_CLOSE = re.compile(r"</div\s*>", re.IGNORECASE)
_LINKED_IMG = re.compile(
    r'<a\s[^>]*href="([^"]+)"[^>]*>\s*<img\s[^>]*src="([^"]+)"[^>]*/?>\s*</a>',
    re.IGNORECASE,
)
_BARE_IMG = re.compile(r'<img\s[^>]*src="([^"]+)"[^>]*/?>', re.IGNORECASE)
_ITALIC = re.compile(r"^[*_](.+)[*_]$")
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
_HEADING = re.compile(r"^(#{1,6})(\s+)")


@dataclass(frozen=True, kw_only=True)
class Badge:
    """A status badge image, optionally linked"""

    alt: str
    """The image's alternative text"""

    img: str
    """The image URL"""

    url: str
    """The link target, or `""` for an unlinked badge"""


@dataclass(frozen=True, kw_only=True)
class HeroElements:
    """The hero content found in a README, and the README without it"""

    badges: list[Badge]
    """The badges from a known badge host, in README order"""

    body: str
    """The README without the badge block, or unchanged when it has no badges"""

    logo_url: str | None = None
    """The image of a centred `<div>` that holds badges"""

    tagline: str | None = None
    """The italic line of a centred `<div>` that holds badges"""


def _is_badge(img: str) -> bool:
    """
    Check whether an image comes from a known badge host

    Parameters
    ----------
    img
        The image URL.

    Returns
    -------
    :
        Whether the URL names a badge host.
    """
    return any(host in img for host in _BADGE_HOSTS)


def extract_hero_elements(markdown: str) -> HeroElements:
    """
    Extract a README's badges, logo and tagline and remove the badge block

    Two layouts are recognised. In the first, a centred `<div>` holds the badges, perhaps with
    a logo image and an italic tagline; the whole `<div>`, up to its matching `</div>`, is
    removed, and a `<div>` that never closes is left in place. In the second, lines of
    badges follow the first heading; those lines are removed and the heading is kept.

    Parameters
    ----------
    markdown
        README Markdown without front matter.

    Returns
    -------
    :
        The badges, the README without them, and the logo and tagline of a centred `<div>`.
    """
    lines = markdown.split("\n")

    for i, line in enumerate(lines):
        if not _CENTRED_DIV.match(line.strip()):
            continue
        div_badges: list[Badge] = []
        logo_url: str | None = None
        tagline: str | None = None
        div_end: int | None = None
        depth = 1
        for j in range(i + 1, len(lines)):
            sline = lines[j].strip()
            for alt, img, url in _MD_BADGE.findall(sline):
                if _is_badge(img):
                    div_badges.append(Badge(alt=alt, img=img, url=url))

            # A badge line holds images too, but none of them is the logo
            if logo_url is None and not _MD_BADGE.search(sline):
                if linked := _LINKED_IMG.search(sline):
                    logo_url = linked.group(2)
                elif bare := _BARE_IMG.search(sline):
                    logo_url = bare.group(1)

            if tagline is None and (italic := _ITALIC.match(sline)):
                tagline = italic.group(1)

            # Nested `<div>`s close before the centred one does
            depth += len(_DIV_OPEN.findall(sline)) - len(_DIV_CLOSE.findall(sline))
            if depth <= 0:
                div_end = j
                break

        if div_badges and div_end is not None:
            body = "\n".join(lines[:i] + lines[div_end + 1 :])
            body = re.sub(r"\n{3,}", "\n\n", body)
            return HeroElements(badges=div_badges, body=body, logo_url=logo_url, tagline=tagline)

    badges: list[Badge] = []
    badge_end = 0
    started = False
    for i, line in enumerate(lines):
        stripped = line.strip()

        if not started and not stripped:
            continue

        if not started and stripped.startswith("# "):
            started = True
            continue

        if not started and stripped:
            started = True

        if started and not stripped:
            # A blank line inside the badge block is followed by more badges
            if any(_MD_BADGE.search(lines[j]) for j in range(i + 1, min(i + 3, len(lines)))):
                badge_end = i + 1
                continue
            break

        found = _MD_BADGE.findall(stripped)
        if found:
            badges.extend(
                Badge(alt=alt, img=img, url=url) for alt, img, url in found if _is_badge(img)
            )
            badge_end = i + 1
        elif started:
            break

    if not badges or badge_end == 0:
        return HeroElements(badges=badges, body=markdown)

    headings = [line for line in lines[:badge_end] if line.strip().startswith("# ")]
    remaining = lines[badge_end:]
    if headings:
        body = headings[0] + "\n\n" + "\n".join(remaining).lstrip("\n")
    else:
        body = "\n".join(remaining).lstrip("\n")
    return HeroElements(badges=badges, body=body)


def bump_heading_levels(markdown: str) -> str:
    """
    Move Markdown ATX headings one level down outside fenced code blocks

    Lines in fenced code are unchanged, so a Quarto cell option such as `#| code-fold: true`
    keeps its meaning.

    Parameters
    ----------
    markdown
        The Markdown to change.

    Returns
    -------
    :
        The Markdown with one more `#` on each ATX heading.
    """
    lines = markdown.split("\n")
    fence_char = ""
    for i, line in enumerate(lines):
        if fence := _FENCE.match(line):
            marker = fence.group(1)[0]
            if not fence_char:
                fence_char = marker
            elif marker == fence_char:
                fence_char = ""
            continue
        if not fence_char and _HEADING.match(line):
            lines[i] = "#" + line
    return "\n".join(lines)


def strip_duplicate_title(markdown: str, name: str) -> str:
    """
    Remove the first level-one heading when it repeats a name

    The hero shows the package name, so a README that opens with the same title would show
    it twice.

    Parameters
    ----------
    markdown
        The README Markdown.
    name
        The name the hero shows. Case and surrounding spaces are ignored in the comparison.

    Returns
    -------
    :
        The Markdown without that heading, or unchanged when the first level-one heading
        differs.
    """
    first_h1 = re.match(r"^#\s+(.+)$", markdown.strip(), re.MULTILINE)
    if first_h1 and first_h1.group(1).strip().lower() == name.strip().lower():
        return markdown.replace(first_h1.group(0), "", 1).lstrip("\n")
    return markdown
