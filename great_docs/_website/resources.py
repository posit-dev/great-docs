"""
Project resources that Quarto copies into the site as they are

Quarto copies only the files that rendered pages link to. These resources are
files that pages load some other way, such as notebooks for marimo islands and
images in asset directories, and files the site serves for AI agents.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from .._content.pages import section_destination
from .._content.walk import is_asset_dir
from .._contribution import Contribution
from . import quarto_yml

if TYPE_CHECKING:
    from .._project.layout import Layout
    from ..config import Config

__all__ = ["register"]

_MCP_MANIFEST = ".well-known/mcp.json"
"""The MCP discovery manifest, relative to the Quarto project directory"""


def register(quarto_config: dict[str, Any], config: Config, layout: Layout) -> None:
    """
    List the site's fixed resources in `project.resources`

    Add marimo notebooks and island fragments when marimo is enabled. Include asset
    directories from the user guide and each section, along with `assets/` and `_shared/`.

    With skills enabled, include `skill.md`. Also include `.well-known/` when
    `well_known` is enabled. Exclude both from rendering; Quarto would otherwise
    render `skill.md` as a page. Without `.well-known/`, include the MCP discovery
    manifest `.well-known/mcp.json` on its own.

    Asset directories, `notebooks/`, `assets/` and the MCP manifest are listed only
    when they exist in the build directory, so a call after the user guide, sections,
    MCP reference and assets are written finds more of them.

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.
    config
        Project configuration.
    layout
        Project directories for finding build resources and published sections.

    Returns
    -------
    :
    """
    build_dir = layout.build_dir
    resources = [
        *_marimo(config, build_dir),
        *_asset_dirs(build_dir / "user-guide", build_dir),
        *(["assets/**"] if (build_dir / "assets").is_dir() else []),
        "_shared/**",
        *_section_asset_dirs(config, layout),
    ]
    render_excludes: list[str] = []
    if config.skill_enabled:
        skill_files = ["skill.md", *([".well-known/**"] if config.skill_well_known else [])]
        resources.extend(skill_files)
        render_excludes.extend(skill_files)
    if ".well-known/**" not in resources and (build_dir / _MCP_MANIFEST).is_file():
        resources.append(_MCP_MANIFEST)
    quarto_yml.apply(
        quarto_config,
        Contribution(resources=tuple(resources), render_excludes=tuple(render_excludes)),
        config,
    )


def _marimo(config: Config, build_dir: Path) -> Iterator[str]:
    """
    Yield the notebooks and pre-generated island fragments that marimo shortcodes load

    Parameters
    ----------
    config
        Project configuration.
    build_dir
        The Quarto project directory.

    Returns
    -------
    :
        Resource globs, or no values when marimo is disabled.
    """
    if not config.marimo_enabled:
        return
    if (build_dir / "notebooks").is_dir():
        yield "notebooks/**"
    yield "_marimo_islands/**"


def _asset_dirs(directory: Path, build_dir: Path) -> Iterator[str]:
    """
    Yield a glob for each asset directory directly inside a published directory

    Quarto does not discover files referenced only through data attributes, such as
    dark-mode image variants.

    Parameters
    ----------
    directory
        The published directory in the build, which may not exist.
    build_dir
        The Quarto project directory.

    Returns
    -------
    :
        The resource globs relative to `build_dir`, in directory listing order.
    """
    if not directory.is_dir():
        return
    prefix = directory.relative_to(build_dir).as_posix()
    for item in directory.iterdir():
        if item.is_dir() and is_asset_dir(item):
            yield f"{prefix}/{item.name}/**"


def _section_asset_dirs(config: Config, layout: Layout) -> Iterator[str]:
    """
    Yield a glob for each asset directory of each configured section

    Parameters
    ----------
    config
        Project configuration.
    layout
        Project directories for locating published sections and expressing their
        asset paths relative to the build directory.

    Returns
    -------
    :
        The resource globs relative to the build directory, in section order.
    """
    sections = cast("object", config.sections)
    if not isinstance(sections, list):
        return
    for entry in cast("list[object]", sections):
        if not isinstance(entry, dict):
            continue
        destination = section_destination(layout, cast("Mapping[str, object]", entry))
        if destination is not None:
            yield from _asset_dirs(destination, layout.build_dir)
