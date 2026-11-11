"""Project configuration selection for CLI commands"""

from __future__ import annotations

from functools import wraps
from pathlib import Path
from typing import Any, Callable

import click

from .._project.layout import Layout
from ..config import ConfigError


def config_option(function: Callable[..., Any]) -> Callable[..., Any]:
    """Select and validate project configuration after the subcommand"""

    @click.option(
        "--config",
        "config_path",
        type=str if function.__name__ == "migrate_layout" else click.Path(dir_okay=False),
        help="Path to the project configuration file",
    )
    @wraps(function)
    def selected(*args: Any, **kwargs: Any) -> Any:
        standalone_preview = function.__name__ == "preview" and any(
            kwargs.get(option) for option in ("site_dir", "pr", "run", "branch", "clear_cache")
        )
        if (
            function.__name__ != "migrate_layout"
            and not kwargs.get("from_repo")
            and not standalone_preview
        ):
            try:
                _ = Layout.make(
                    Path(kwargs.get("project_path") or Path.cwd()),
                    Path(kwargs["config_path"]) if kwargs.get("config_path") else None,
                    create=function.__name__ in {"init", "config"},
                )
            except ValueError as error:
                raise click.ClickException(str(error)) from error
        try:
            return function(*args, **kwargs)
        except ConfigError as error:
            raise click.ClickException(str(error)) from error

    return selected
