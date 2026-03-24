"""
Git utilities for extracting file timestamps and metadata.

This module provides functions to extract creation and modification dates
from Git history, with fallback to file system timestamps.
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


def get_file_created_date(
    filepath: Path,
    project_root: Path,
    *,
    fallback_to_mtime: bool = True,
) -> datetime | None:
    """
    Get the creation date of a file from Git history.

    This returns the date of the first Git commit that added the file.

    Parameters
    ----------
    filepath
        Absolute or relative path to the file.
    project_root
        Root directory of the Git repository.
    fallback_to_mtime
        If True and Git history is unavailable, fall back to file modification time.

    Returns
    -------
    datetime | None
        The creation date as a datetime object, or None if unavailable.

    Examples
    --------
    >>> from pathlib import Path
    >>> get_file_created_date(Path("docs/guide.qmd"), Path("/project"))
    datetime.datetime(2026, 1, 15, 10, 30, 0)
    """
    filepath = Path(filepath)
    project_root = Path(project_root)

    # Make filepath relative to project_root for Git
    try:
        if filepath.is_absolute():
            rel_path = filepath.relative_to(project_root)
        else:
            rel_path = filepath
    except ValueError:
        # filepath is not under project_root
        rel_path = filepath

    # Try Git first
    try:
        # Get the first commit that added this file (--diff-filter=A)
        # --follow tracks file renames
        result = subprocess.run(
            [
                "git",
                "log",
                "--diff-filter=A",
                "--follow",
                "--format=%aI",  # ISO 8601 author date
                "--",
                str(rel_path),
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0 and result.stdout.strip():
            # Get the last line (earliest commit)
            lines = result.stdout.strip().split("\n")
            iso_date = lines[-1].strip()
            if iso_date:
                return datetime.fromisoformat(iso_date)

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    # Fallback to file system
    if fallback_to_mtime:
        abs_path = project_root / rel_path if not filepath.is_absolute() else filepath
        if abs_path.exists():
            # Use ctime on Unix (inode change time, closest to creation)
            # Note: On Windows, ctime is actual creation time
            stat = abs_path.stat()
            ctime = min(stat.st_ctime, stat.st_mtime)
            return datetime.fromtimestamp(ctime)

    return None


def get_file_modified_date(
    filepath: Path,
    project_root: Path,
    *,
    fallback_to_mtime: bool = True,
) -> datetime | None:
    """
    Get the last modification date of a file from Git history.

    This returns the date of the most recent Git commit that modified the file.

    Parameters
    ----------
    filepath
        Absolute or relative path to the file.
    project_root
        Root directory of the Git repository.
    fallback_to_mtime
        If True and Git history is unavailable, fall back to file modification time.

    Returns
    -------
    datetime | None
        The modification date as a datetime object, or None if unavailable.

    Examples
    --------
    >>> from pathlib import Path
    >>> get_file_modified_date(Path("docs/guide.qmd"), Path("/project"))
    datetime.datetime(2026, 3, 24, 14, 45, 0)
    """
    filepath = Path(filepath)
    project_root = Path(project_root)

    # Make filepath relative to project_root for Git
    try:
        if filepath.is_absolute():
            rel_path = filepath.relative_to(project_root)
        else:
            rel_path = filepath
    except ValueError:
        rel_path = filepath

    # Try Git first
    try:
        # Get the most recent commit that modified this file
        result = subprocess.run(
            [
                "git",
                "log",
                "-1",  # Only the most recent
                "--format=%aI",  # ISO 8601 author date
                "--",
                str(rel_path),
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0 and result.stdout.strip():
            iso_date = result.stdout.strip()
            return datetime.fromisoformat(iso_date)

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    # Fallback to file system mtime
    if fallback_to_mtime:
        abs_path = project_root / rel_path if not filepath.is_absolute() else filepath
        if abs_path.exists():
            return datetime.fromtimestamp(abs_path.stat().st_mtime)

    return None


def get_file_contributors(
    filepath: Path,
    project_root: Path,
) -> list[str]:
    """
    Get list of unique commit authors who have modified a file.

    Parameters
    ----------
    filepath
        Absolute or relative path to the file.
    project_root
        Root directory of the Git repository.

    Returns
    -------
    list[str]
        List of unique author names, ordered by most recent contribution first.

    Examples
    --------
    >>> from pathlib import Path
    >>> get_file_contributors(Path("docs/guide.qmd"), Path("/project"))
    ['Alice Smith', 'Bob Jones']
    """
    filepath = Path(filepath)
    project_root = Path(project_root)

    try:
        if filepath.is_absolute():
            rel_path = filepath.relative_to(project_root)
        else:
            rel_path = filepath
    except ValueError:
        rel_path = filepath

    try:
        result = subprocess.run(
            [
                "git",
                "log",
                "--format=%aN",  # Author name
                "--follow",
                "--",
                str(rel_path),
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0 and result.stdout.strip():
            # Preserve order (most recent first) while removing duplicates
            seen: set[str] = set()
            contributors: list[str] = []
            for name in result.stdout.strip().split("\n"):
                name = name.strip()
                if name and name not in seen:
                    seen.add(name)
                    contributors.append(name)
            return contributors

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return []


def is_git_repository(path: Path) -> bool:
    """
    Check if a path is inside a Git repository.

    Parameters
    ----------
    path
        Path to check.

    Returns
    -------
    bool
        True if the path is inside a Git repository.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def format_date(dt: datetime | None, fmt: str = "%B %d, %Y") -> str:
    """
    Format a datetime object as a string.

    Parameters
    ----------
    dt
        The datetime to format, or None.
    fmt
        Python strftime format string.

    Returns
    -------
    str
        Formatted date string, or empty string if dt is None.

    Examples
    --------
    >>> from datetime import datetime
    >>> format_date(datetime(2026, 3, 24), "%B %d, %Y")
    'March 24, 2026'
    >>> format_date(datetime(2026, 3, 24), "%Y-%m-%d")
    '2026-03-24'
    """
    if dt is None:
        return ""
    return dt.strftime(fmt)
