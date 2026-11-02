"""
Source selection and reading for authored homepages

The homepage uses the first existing file in this order: `index.qmd`, `index.md`, `README.md`
and `README.rst` in the documentation source directory, followed by `README.md` and
`README.rst` in the package root.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..._subprocess import TEXT_MODE_KWARGS
from ..._yaml import YamlValue, split_front_matter
from ..seo import description

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from ..._layout import Layout

__all__ = ["INDEX_NAMES", "NAMES", "README_NAMES", "Source", "find", "read", "rst_to_markdown"]

INDEX_NAMES = ("index.qmd", "index.md")
"""The names of a homepage page written for the site"""

README_NAMES = ("README.md", "README.rst")
"""The names of a project README that the homepage can be made from"""

NAMES = (*INDEX_NAMES, *README_NAMES)
"""The names of every homepage source, in the order the homepage prefers them"""


@dataclass(frozen=True, kw_only=True)
class Source:
    """The parts of an authored homepage source that the homepage keeps"""

    title: str
    """The source's front matter title, or `""` if it has none"""

    description: dict[str, YamlValue]
    """The source's search description keys, as they appear in its front matter"""

    body: str
    """The Markdown after the front matter, without leading blank lines"""


def find(layout: Layout) -> list[Path]:
    """
    Find a project's homepage source files in order of preference

    Parameters
    ----------
    layout
        The project's directories.

    Returns
    -------
    :
        The existing source files in order of preference. The homepage uses the first, and
        the others are ignored.
    """
    candidates = [layout.source_dir / name for name in NAMES]
    if layout.source_dir != layout.package_root:
        candidates.extend(layout.package_root / name for name in README_NAMES)
    return [candidate for candidate in candidates if candidate.exists()]


def read(path: Path, *, report: Callable[[str], None]) -> Source:
    """
    Read a homepage source file

    A reStructuredText file is converted to Markdown first. Only the title and search
    description keys are kept from the front matter.

    Parameters
    ----------
    path
        The source file.
    report
        A callback that receives conversion warnings.

    Returns
    -------
    :
        The source's title, description keys and body.
    """
    if path.suffix.lower() == ".rst":
        content = rst_to_markdown(path, report=report)
    else:
        content = path.read_text(encoding="utf-8")
    front_matter, body = split_front_matter(content)
    return Source(
        title=front_matter.string("title") or "",
        description={
            key: front_matter.get(key) for key in description.PAGE_KEYS if key in front_matter
        },
        body=body.lstrip("\n"),
    )


def rst_to_markdown(path: Path, *, report: Callable[[str], None]) -> str:
    """
    Convert a reStructuredText file to Markdown with pandoc

    Quarto's bundled pandoc is preferred to a standalone one.

    Parameters
    ----------
    path
        The `.rst` file.
    report
        A callback that receives warnings when pandoc is missing or fails.

    Returns
    -------
    :
        The Markdown, or the file's raw text if pandoc is missing or fails.
    """
    if shutil.which("quarto"):
        pandoc = ["quarto", "pandoc"]
    elif shutil.which("pandoc"):
        pandoc = ["pandoc"]
    else:
        report("   ⚠️  pandoc not found; using raw RST content for landing page")
        return path.read_text(encoding="utf-8")

    try:
        result = subprocess.run(
            [*pandoc, str(path), "-f", "rst", "-t", "markdown", "--wrap=none"],
            capture_output=True,
            **TEXT_MODE_KWARGS,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout
        report(f"   ⚠️  pandoc conversion failed: {result.stderr.strip()}")
        report("   Falling back to raw RST content")
        return path.read_text(encoding="utf-8")
    except (OSError, subprocess.TimeoutExpired, UnicodeDecodeError) as error:
        report(f"   ⚠️  pandoc conversion error: {error}")
        report("   Falling back to raw RST content")
        return path.read_text(encoding="utf-8")
