"""
Harper proofreading for documentation pages and Python docstrings

Shared checks apply the same dictionary, rule filters and prose extraction to files from
the command line and Python API.
"""

from __future__ import annotations

import contextlib
import tempfile
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

from . import _harper

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from ._harper import HarperFileResult, HarperLint
    from ._layout import Layout

__all__ = ["CheckedFile", "Options", "check", "find_pages"]


@dataclass(frozen=True)
class Options:
    """Harper settings for one proofreading run"""

    dialect: str = "us"
    """English dialect: `"us"`, `"uk"`, `"au"`, `"in"` or `"ca"`"""

    words: Sequence[str] = ()
    """Additional accepted words, alongside any enabled built-in dictionary"""

    only_rules: Sequence[str] = ()
    """Harper rules to run exclusively, or all rules not ignored when empty"""

    ignore_rules: Sequence[str] = ()
    """Harper rules to skip in addition to any enabled default exclusions"""

    builtin_dictionary: bool = True
    """Whether to accept the built-in technical terms"""

    default_ignores: bool = True
    """Whether to skip the rules that misfire on technical documentation"""


@dataclass(frozen=True)
class CheckedFile:
    """The proofreading outcome for one file"""

    file: str
    """The file's path, relative to the project root for `.qmd` pages"""

    issues: Sequence[HarperLint] = ()
    """Issues reported by Harper, with line numbers in the original file"""

    error: str | None = None
    """Reason the file could not be checked, or `None` after a successful check"""


def find_pages(layout: Layout, guide_dir: Path | None = None) -> list[Path]:
    """
    Find the documentation pages to proofread

    The user guide and recipes are searched recursively for `.qmd` and `.md` files.
    `README.md` is included from the package root.

    Parameters
    ----------
    layout
        The project's paths.
    guide_dir
        The user guide directory. If `None`, use `user_guide/` in the source directory.

    Returns
    -------
    :
        Existing user guide pages, followed by `README.md` and recipe pages.
    """
    pages: list[Path] = []
    guide_dir = guide_dir or layout.source_dir / "user_guide"
    recipes_dir = layout.source_dir / "recipes"
    readme = layout.package_root / "README.md"

    if guide_dir.exists():
        pages.extend(guide_dir.rglob("*.qmd"))
        pages.extend(guide_dir.rglob("*.md"))
    if readme.exists():
        pages.append(readme)
    if recipes_dir.exists():
        pages.extend(recipes_dir.rglob("*.qmd"))
        pages.extend(recipes_dir.rglob("*.md"))
    return pages


def check(
    files: Sequence[Path],
    root: Path,
    options: Options,
    report: Callable[[str], None],
) -> list[CheckedFile]:
    """
    Proofread files with Harper

    Harper checks `.md` and `.py` files directly. It does not recognise `.qmd`, so each `.qmd`
    page is checked as text with its front matter and fenced code blocks blanked out. Files with
    other suffixes are skipped.

    Parameters
    ----------
    files
        The files to check.
    root
        The project root used for reporting relative `.qmd` paths.
    options
        The dictionary and rule settings.
    report
        A callback that receives each progress line.

    Returns
    -------
    :
        A list of file results, ordered by `.md` files, `.qmd` pages, then `.py` files.

    Raises
    ------
    great_docs._harper.HarperNotFoundError
        If `harper-cli` is not installed.
    great_docs._harper.HarperError
        If `harper-cli` fails on a batch of `.md` or `.py` files. A `HarperError` on a
        `.qmd` page is returned as that page's `error`.
    """
    md_files = [f for f in files if f.suffix == ".md"]
    qmd_files = [f for f in files if f.suffix == ".qmd"]
    py_files = [f for f in files if f.suffix == ".py"]

    words = [
        *(_harper.get_builtin_dictionary() if options.builtin_dictionary else []),
        *options.words,
    ]
    ignore = [
        *(_harper.get_default_ignore_rules() if options.default_ignores else []),
        *options.ignore_rules,
    ]
    dictionary = _write_dictionary(words) if words else None
    only = list(options.only_rules) or None
    run_files = partial(
        _harper.run_harper,
        dialect=options.dialect,
        user_dict_path=dictionary,
        ignore_rules=ignore or None,
        only_rules=only,
    )
    run_text = partial(
        _harper.run_harper_on_text,
        dialect=options.dialect,
        user_dict_path=dictionary,
        ignore_rules=ignore or None,
        only_rules=only,
    )
    results: list[CheckedFile] = []

    try:
        if md_files:
            report(f"Checking {len(md_files)} Markdown file(s)...\n")
            results.extend(_checked(run_files(md_files)))

        for page in qmd_files:
            report(f"Checking {page.name}...")
            results.append(_check_page(page, root, run_text))

        if py_files:
            report(f"\nChecking {len(py_files)} Python file(s) for docstrings...\n")
            results.extend(_checked(run_files(py_files)))
    finally:
        if dictionary:
            with contextlib.suppress(OSError):
                dictionary.unlink()

    return results


def _write_dictionary(words: Sequence[str]) -> Path:
    """
    Write a Harper user dictionary to a temporary file

    Parameters
    ----------
    words
        The accepted words.

    Returns
    -------
    :
        The path to a temporary file containing one word per line. The caller must remove it.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as file:
        _ = file.write("\n".join(words))
    return Path(file.name)


def _checked(results: Sequence[HarperFileResult]) -> list[CheckedFile]:
    """
    Convert Harper batch results to per-file outcomes

    Parameters
    ----------
    results
        The results of one `harper-cli` batch.

    Returns
    -------
    :
        A list of file results preserving each path, issue and error.
    """
    return [CheckedFile(r.file, tuple(r.lints), r.error) for r in results]


def _check_page(
    page: Path,
    root: Path,
    run_text: Callable[[str], list[HarperLint]],
) -> CheckedFile:
    """
    Proofread the prose of a `.qmd` page

    Parameters
    ----------
    page
        The `.qmd` page to check.
    root
        The project root used for reporting the page's relative path.
    run_text
        A callback that checks text and returns Harper issues.

    Returns
    -------
    :
        A file result with issues at their original line numbers. An `OSError`,
        `UnicodeDecodeError` or `HarperError` is returned as the result's `error`.

    Raises
    ------
    great_docs._harper.HarperNotFoundError
        If `harper-cli` is missing. This error stops the run and is not stored per page.
    """
    path = str(page.relative_to(root))
    try:
        prose, line_map = _harper.extract_prose_from_markdown(page.read_text(encoding="utf-8"))
        issues = run_text(prose)
    except (OSError, UnicodeDecodeError, _harper.HarperError) as e:
        # HarperNotFoundError passes through: a missing `harper-cli` prevents the whole run.
        return CheckedFile(path, (), str(e))

    for issue in issues:
        issue.file = path
        issue.line = line_map.get(issue.line, issue.line)
    return CheckedFile(path, tuple(issues))
