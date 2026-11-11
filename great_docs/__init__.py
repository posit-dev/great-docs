from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("great-docs")
except PackageNotFoundError:
    __version__ = "0.0.0"

from . import _builtin  # noqa: F401  — registers great-docs' built-in event handlers
from ._build.steps import BuildError
from ._skills.install import check_skill, install_skill, list_skills
from ._tables.display import disable_tbl_preview, enable_tbl_preview
from ._tables.explorer import tbl_explorer
from ._tables.preview import tbl_preview
from .config import Config, create_default_config, load_config
from .core import GreatDocs

__all__ = [
    "BuildError",
    "Config",
    "GreatDocs",
    "check_skill",
    "create_default_config",
    "disable_tbl_preview",
    "enable_tbl_preview",
    "install_skill",
    "list_skills",
    "load_config",
    "main",
    "render_evolution_table",
    "tbl_explorer",
    "tbl_preview",
]


def main() -> None:
    """Main CLI entry point for great-docs."""
    from .cli import main as _main

    _main()


def render_evolution_table(
    project_path=".",
    symbol="",
    **kwargs,
):
    """Generate a self-contained HTML evolution table for a symbol"""
    from ._api_evolution.render import render_evolution_table as _render

    return _render(project_path, symbol, **kwargs)
