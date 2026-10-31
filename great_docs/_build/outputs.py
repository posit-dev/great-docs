"""
Validation and removal of a project's generated output

Builds replace the project's Quarto projects and site; uninstallation removes them. Both
operations refuse to touch a directory that Great Docs did not generate.
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from .._content import sections
from .._utils import recognised_build_dirs, validate_build_dir, validate_layout_outputs

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from .._layout import Layout
    from ..config import Config

__all__ = ["remove", "validate"]


def validate(config: Config, layout: Layout) -> None:
    """
    Reject version and ownership conflicts before a build changes project files

    Parameters
    ----------
    config
        The project's configuration, which lists its versions, sections, user guide and
        custom pages.
    layout
        The project's layout, which locates the build and site directories.

    Raises
    ------
    ValueError
        If a build, site or historical version directory exists but Great Docs did not
        generate it; if a version tag has an unsafe or shared directory or URL; or if
        `user_guide` or `custom_pages` names a directory that a `sections` entry publishes.
    """
    validate_layout_outputs(layout)
    if config.versions:
        from .._versioned_build import check_build_dir_collisions
        from .._versioning import get_latest_version, parse_versions_config

        versions = parse_versions_config(config.versions)
        latest = get_latest_version(versions)
        latest_tag = latest.tag if latest else versions[0].tag
        check_build_dir_collisions(layout.build_dir, versions, latest_tag, layout)
        for entry in versions:
            validate_build_dir(layout.build_dir_for(entry.tag, latest_tag))
    _validate_section_claims(config, layout)


def _validate_section_claims(config: Config, layout: Layout) -> None:
    """
    Reject an explicit user guide or custom pages directory that is also a section

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's layout, which locates the configured directories.

    Raises
    ------
    ValueError
        If `user_guide` or `custom_pages` names a directory that a `sections` entry
        publishes.
    """
    claimed = sections.source_dirs(config, layout)
    if not claimed:
        return

    package_root = layout.source_dir
    explicit: list[tuple[str, Path]] = []
    if config.user_guide_dir is not None:
        explicit.append(("user_guide", package_root / config.user_guide_dir))
    elif config.user_guide_is_explicit:
        # A list-form guide still reads its files from the conventional directory.
        for name in ("user_guide", "user-guide"):
            candidate = package_root / name
            if candidate.is_dir():
                explicit.append(("user_guide", candidate))
                break
    if config["custom_pages"] is not None:
        explicit.extend(
            ("custom_pages", package_root / entry["dir"]) for entry in config.custom_pages
        )

    for key, directory in explicit:
        if directory.resolve() in claimed:
            raise ValueError(
                f"Directory '{directory.relative_to(package_root)}' is claimed by both "
                f"`{key}` and `sections`; remove it from one of them"
            )


def remove(layout: Layout, *, report: Callable[[str], None]) -> None:
    """
    Remove the configuration and the output Great Docs generated

    Remove the configuration file, the default build directory and each historical version
    directory that Great Docs generated. If the configuration is in a subdirectory such as
    `docs/`, also remove its site directory and, if left empty, its build container. Keep
    historical directories that are symbolic links or that Great Docs did not generate.

    Parameters
    ----------
    layout
        The project's layout, which locates the configuration and the output.
    report
        A callback that receives a line for each path removed, except the site directory
        and the build container.

    Raises
    ------
    ValueError
        If the default build directory or the site directory exists but Great Docs did not
        generate it, or a generated directory contains a symbolic link. Nothing is removed.
    """
    validate_layout_outputs(layout)
    builds = [layout.build_dir, *recognised_build_dirs(layout)]

    config_path = layout.config_path
    if config_path.exists():
        config_path.unlink()
        report(f"Removed {config_path.relative_to(layout.package_root)}")

    for build_dir in builds:
        if build_dir.exists():
            shutil.rmtree(build_dir)
            report(f"Removed {build_dir.relative_to(layout.package_root)}/ directory")
    if layout.source_dir != layout.package_root:
        if layout.site_dir.exists():
            shutil.rmtree(layout.site_dir)
        container = layout.build_dir.parent
        if container.exists() and not any(container.iterdir()):
            container.rmdir()
