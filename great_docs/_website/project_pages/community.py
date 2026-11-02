"""
Pages copied from a project's contributing guide, code of conduct, roadmap and security policy
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .. import page_dates

if TYPE_CHECKING:
    from pathlib import Path

    from ...config import Config

__all__ = ["PAGES", "SECURITY", "CommunityPage", "write_pages"]


@dataclass(frozen=True, kw_only=True)
class CommunityPage:
    """A site page copied from a Markdown file in the project"""

    source: str
    """The source file name, such as `CONTRIBUTING.md`"""

    in_github_dir: bool
    """Whether the source file may sit in `.github/` when the project root has none"""

    filename: str
    """The page's file name in the Quarto project"""

    title: str
    """The page title"""

    label_key: str
    """The translation key of the page's link text on the homepage"""


SECURITY = CommunityPage(
    source="SECURITY.md",
    in_github_dir=True,
    filename="security.qmd",
    title="Security Policy",
    label_key="security_policy",
)
"""The security policy page, written only when `show_security` is enabled"""

PAGES = (
    CommunityPage(
        source="CONTRIBUTING.md",
        in_github_dir=True,
        filename="contributing.qmd",
        title="Contributing",
        label_key="contributing_guide",
    ),
    CommunityPage(
        source="CODE_OF_CONDUCT.md",
        in_github_dir=True,
        filename="code-of-conduct.qmd",
        title="Code of Conduct",
        label_key="code_of_conduct",
    ),
    CommunityPage(
        source="ROADMAP.md",
        in_github_dir=False,
        filename="roadmap.qmd",
        title="Roadmap",
        label_key="project_roadmap",
    ),
    SECURITY,
)
"""The community pages, in the order the homepage links them"""


def write_pages(
    config: Config, package_root: Path, build_dir: Path, authors: list[dict[str, Any]]
) -> list[CommunityPage]:
    """
    Write community pages from the project's Markdown files

    Each page uses its own title and the source text with an initial `# ` heading removed.
    The security policy page is written only when `show_security` is enabled.

    Parameters
    ----------
    config
        The Great Docs configuration.
    package_root
        The project directory holding the source files.
    build_dir
        The Quarto project directory to write the pages into.
    authors
        The configured authors, with local portrait paths replaced by site URLs.

    Returns
    -------
    :
        The pages written, in the order of `PAGES`.
    """
    written: list[CommunityPage] = []
    for page in PAGES:
        if page is SECURITY and not config.show_security:
            continue
        source = package_root / page.source
        if not source.exists() and page.in_github_dir:
            source = package_root / ".github" / page.source
        if not source.exists():
            continue

        text = source.read_text(encoding="utf-8")
        lines = text.split("\n")
        if lines and lines[0].startswith("# "):
            text = "\n".join(lines[1:]).lstrip()

        content = f"""---
title: "{page.title}"
---

{text}
"""
        _ = (build_dir / page.filename).write_text(
            page_dates.add_to_page(content, source, config, authors), encoding="utf-8"
        )
        written.append(page)
    return written
