"""
Selected-page execution and cached results for later builds

Quarto reuses a page's cached results only while its source is unchanged. Pages are frozen
from the same sources a build would render.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .steps import count_listed, run_steps

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from .._build_log import BuildLog
    from .steps import Step

__all__ = ["prepare"]


def prepare(steps: Iterable[Step], log: BuildLog, build_dir: Path) -> None:
    """
    Prepare the Quarto project with the build's steps before rendering

    Run preparation steps in build order, excluding steps that publish remote content.
    Number listed steps consecutively and count only the listed steps that run.

    Parameters
    ----------
    steps
        The build's preparation steps.
    log
        The build log that the steps write to.
    build_dir
        The working directory for steps that run the project's code.

    Raises
    ------
    BuildError
        If a step reports a failure. The log already contains the report.
    """
    local = [step for step in steps if not step.remote_content]
    log.total_steps = count_listed(local)
    run_steps(local, log, build_dir)
