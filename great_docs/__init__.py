try:
    from importlib.metadata import PackageNotFoundError, version
except ImportError:  # pragma: no cover
    from importlib_metadata import PackageNotFoundError, version  # type: ignore[import-not-found]

try:  # pragma: no cover
    __version__ = version("great-docs")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

from .cli import main
from .config import Config, create_default_config, load_config
from .core import GreatDocs

__all__ = [
    "Config",
    "GreatDocs",
    "create_default_config",
    "load_config",
    "main",
    "render_evolution_table",
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
