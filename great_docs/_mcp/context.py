"""Request-scoped project paths and export discovery"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from .._build.ownership import recognised_build_dirs
from .._build.steps import PROJECT_ERRORS, USER_CODE_ERRORS
from .._project.layout import Layout

if TYPE_CHECKING:
    from .._reference.exports import Exports

# The server reports these errors as failed tool results, resource error text or no
# completion suggestions. `USER_CODE_ERRORS` covers package-loading failures and build
# failures because `BuildError` inherits from `RuntimeError`.
# The set also includes plain `ValueError`: builds and the lint stale-versions check raise it
# for an invalid `versions` list. Builds also raise it for output Great Docs did not
# generate or a directory claimed by both `sections` and either `user_guide` or
# `custom_pages`. Other exceptions propagate as protocol errors.
REPORTED_ERRORS: tuple[type[Exception], ...] = (*PROJECT_ERRORS, *USER_CODE_ERRORS, ValueError)


def get_project_root(project_path: str | None = None) -> Path:
    """Resolve the project root directory."""
    if project_path:
        p = Path(project_path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Project path does not exist: {p}")
        return p
    return Path.cwd()


def sibling_build_dirs(root: Path, layout: Layout | None = None) -> list[Path]:
    """
    Return historical Great Docs build directories under `root`

    Include only directories whose `_quarto.yml` contains the Great Docs
    marker. Ignore symlinks and unmarked matches because they may contain user
    files.

    Parameters
    ----------
    root
        Project root containing the build directories.

    Returns
    -------
    Marked sibling directories in name order.
    """
    return recognised_build_dirs(layout or Layout.make(root))


def build_output_dirs(root: Path, layout: Layout | None = None) -> list[Path]:
    """
    Return all Great Docs build directories under `root`

    The current `great-docs/` directory comes first, when present, followed by
    marked historical sibling directories in name order.

    Parameters
    ----------
    root
        Project root containing the build directories.

    Returns
    -------
    Current and historical build directories.
    """
    layout = layout or Layout.make(root)
    current = (
        [layout.build_dir]
        if layout.build_dir.is_dir() and not layout.build_dir.is_symlink()
        else []
    )
    return current + sibling_build_dirs(root, layout)


def get_exports(project_path: str | None, config_path: str | None) -> Exports:
    """
    Prepare export discovery for the selected project

    Read the configuration and packaging files now; load packages and discover exports
    when requested.

    Parameters
    ----------
    project_path
        The project directory, or `None` to use the current directory.
    config_path
        The configuration file, or `None` to locate it within the project.

    Returns
    -------
    :
        An export discovery object for the selected project.
    """
    from .._reference.exports import Exports

    return Exports.make(
        Layout.make(
            Path(project_path) if project_path else Path.cwd(),
            Path(config_path) if config_path else None,
        )
    )


def get_layout(arguments: dict[str, Any], *, create: bool = False) -> Layout:
    """Resolve paths for a tool's project and configuration arguments"""
    config_path = arguments.get("config_path")
    return Layout.make(
        get_project_root(arguments.get("project_path")),
        Path(config_path) if config_path else None,
        create=create,
    )
