try:
    from importlib.metadata import PackageNotFoundError, version
except ImportError:  # pragma: no cover
    from importlib_metadata import PackageNotFoundError, version  # type: ignore[import-not-found]

try:  # pragma: no cover
    __version__ = version("great-docs")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

from ._skill_install import check_skill, install_skill, list_skills
from ._tbl_display import disable_tbl_preview, enable_tbl_preview
from ._tbl_explorer import tbl_explorer
from ._tbl_preview import tbl_preview
from .cli import main
from .config import Config, create_default_config, load_config
from .core import GreatDocs

__all__ = [
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


def render_evolution_table(
    project_path=".",
    symbol="",
    **kwargs,
):
    """Generate a self-contained HTML evolution table for a symbol.

    Convenience re-export of :func:`great_docs._api_diff.render_evolution_table`.
    See that function for the full parameter list.
    """
    from ._api_diff import render_evolution_table as _render

    return _render(project_path, symbol, **kwargs)
