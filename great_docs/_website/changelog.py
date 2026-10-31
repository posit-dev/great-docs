"""
A changelog page generated from a repository's GitHub Releases
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from .._contribution import Contribution, NavbarLink
from .._translations import get_translation
from . import page_dates

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

    from .._github import GithubRepo
    from .._remote import Remote
    from ..config import Config

__all__ = ["FILENAME", "linkify_references", "write_page"]

FILENAME = "changelog.qmd"

# A closing fence must use the same character as the opening fence and be at least as long.
# An unclosed fenced block continues to the end of the notes. Inline code spans use equal
# backtick runs and stay within one paragraph.
_CODE = re.compile(
    r"^[ ]{0,3}(?P<backticks>`{3,})[^`\n]*$.*?(?:^[ ]{0,3}(?P=backticks)`*[ \t]*$|\Z)"
    r"|^[ ]{0,3}(?P<tildes>~{3,}).*?$.*?(?:^[ ]{0,3}(?P=tildes)~*[ \t]*$|\Z)"
    r"|(?<!`)(?P<ticks>`+)(?!`)(?:(?!\n[ \t]*\n).)+?(?<!`)(?P=ticks)(?!`)",
    re.MULTILINE | re.DOTALL,
)


def write_page(
    config: Config,
    build_dir: Path,
    repo: GithubRepo,
    remote: Remote,
    *,
    max_releases: int | None = None,
    report: Callable[[str], None],
) -> Contribution | None:
    """
    Write the changelog page from the repository's published releases

    The page lists releases newest first, with one section per release. Each section shows
    its date, a pre-release mark and a link to the release on GitHub. GitHub references in
    the notes become links, and note headings move down one level to nest under the release
    heading.

    Parameters
    ----------
    config
        The Great Docs configuration.
    build_dir
        The Quarto project directory to write the page into.
    repo
        The repository whose releases the page lists.
    remote
        The source of the releases.
    max_releases
        The maximum number of releases to list. If `None`, use `changelog.max_releases`
        from the configuration.
    report
        A callback that receives the line announcing the written page.

    Returns
    -------
    :
        A contribution containing the page's navbar link, or `None` if the repository has
        no releases. No page is written in that case.
    """
    if max_releases is None:
        max_releases = config.changelog_max_releases
    releases = remote.github_releases(repo, max_releases)
    if not releases:
        return None

    toc_title = get_translation("releases", config.lang)

    # Pin the heading shift so release headings always render at level 1. This keeps the TOC
    # limited to release headings: without it, `toc-depth: 1` could include release-note
    # subsections or list nothing.
    lines: list[str] = [
        "---",
        'title: "Changelog"',
        f"{page_dates.AUTO_GENERATED}: true",
        "body-classes: gd-changelog-page",
        "toc: true",
        "toc-depth: 1",
        f'toc-title: "{toc_title}"',
        "shift-heading-level-by: -1",
        "---",
        "",
        "This changelog is generated automatically from ",
        f"[GitHub Releases]({repo.url}/releases).",
        "",
    ]
    for release in releases:
        lines.extend(_release_lines(release, repo))

    page = build_dir / FILENAME
    _ = page.write_text("\n".join(lines), encoding="utf-8")
    report(f"Created {page}")
    return Contribution(navbar=(NavbarLink(text="Changelog", href=FILENAME),))


def _release_lines(release: Mapping[str, Any], repo: GithubRepo) -> list[str]:
    """
    Format the changelog section for one release

    Parameters
    ----------
    release
        The release, with the keys that `Remote.github_releases` returns.
    repo
        The repository the release belongs to.

    Returns
    -------
    :
        The section's lines: the heading, the date and link line, and the release notes.
    """
    name = release["name"] or release["tag_name"]
    published = release["published_at"][:10] if release["published_at"] else ""

    details: list[str] = []
    if published:
        details.append(f"*{published}*")
    if release["prerelease"]:
        details.append("*(pre-release)*")
    details.append(f"[GitHub]({release['html_url']})")

    lines = [f"## {name}  {{.changelog-version}}", "", " · ".join(details), ""]

    body = (release.get("body") or "").strip()
    if body:
        body = linkify_references(body, repo)
        # Nest the notes' headings under the release's `##` heading
        body = re.sub(r"^(#{2,6})\s", lambda m: m.group(1) + "# ", body, flags=re.MULTILINE)
        lines.extend([body, ""])
    return lines


def linkify_references(text: str, repo: GithubRepo) -> str:
    """
    Turn GitHub shorthand references in release notes into Markdown links

    Leave inline code spans and fenced code blocks as written. In the surrounding text,
    link bare `#123`, `gh issue #123` and `gh pr #123` to issues in the repository,
    `@username` to the user's profile, and bare compare URLs to themselves. Remove the
    backslash escapes that GitHub adds before `@`, `#`, quotes and backslashes in that text.

    Parameters
    ----------
    text
        The Markdown text of a release's notes.
    repo
        The repository the issue numbers refer to.

    Returns
    -------
    :
        The text with references outside code written as Markdown links.
    """
    pieces: list[str] = []
    start = 0
    for code in _CODE.finditer(text):
        pieces.extend([_linkify_prose(text[start : code.start()], repo), code.group()])
        start = code.end()
    pieces.append(_linkify_prose(text[start:], repo))
    return "".join(pieces)


def _linkify_prose(text: str, repo: GithubRepo) -> str:
    """
    Turn GitHub shorthand references in text outside code into Markdown links

    Parameters
    ----------
    text
        Markdown text without code spans or fenced code blocks.
    repo
        The repository the issue numbers refer to.

    Returns
    -------
    :
        The text with each reference written as a Markdown link.
    """
    base = repo.url

    # Remove escapes first. They hide `@` and `#` from the patterns below and break
    # Markdown rendering.
    text = re.sub(r"\\([\\@#'\"])", r"\1", text)

    # "gh issue #NNN" / "gh pr #NNN" (case-insensitive)
    text = re.sub(r"(?i)\bgh\s+(?:issue|pr)\s+#(\d+)", rf"[#\1]({base}/issues/\1)", text)

    # Bare "#NNN", except as the text of a link made above or inside a URL
    text = re.sub(r"(?<!\[)(?<!/)#(\d+)\b", rf"[#\1]({base}/issues/\1)", text)

    # "@username": 1-39 alphanumerics or inner hyphens; not preceded by a word character or
    # a dot, which excludes email addresses
    text = re.sub(
        r"(?<![\w.])@([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?)",
        r"[@\1](https://github.com/\1)",
        text,
    )

    # Not every Markdown renderer links bare compare URLs ("Full Changelog: https://...").
    # Wrap them as links unless they are already linked.
    compare_url = re.escape(base) + r"/compare/[^\s)]+"
    return re.sub(rf"(?<!\[)(?<!\(){compare_url}", lambda m: f"[{m.group(0)}]({m.group(0)})", text)
