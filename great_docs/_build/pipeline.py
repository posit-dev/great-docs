"""
State shared by the steps of one documentation build
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .._project import Project
from .._reference.exports import Exports

if TYPE_CHECKING:
    from .._content.user_guide import UserGuide
    from .._layout import Layout
    from ..config import Config
    from .facts import Facts

__all__ = ["Run"]


@dataclass
class Run:
    """
    Values read by several steps of one documentation build

    Each build starts from a new `Run` with no results from earlier builds.

    Attributes
    ----------
    project
        The documented project, read from its files when the build starts.
    exports
        The package models and exports shared by this build, loaded on demand.
    watch
        Whether the site is served in watch mode.
    has_api_reference
        Whether the site has an API reference. Preparing the build directory sets it to
        `False` when the reference is disabled, the project is not a Python project, no
        package name is detected, or the package has nothing to document.
    api_discovery_done
        Whether this build has already discovered the package's exports.
    user_guide
        The user guide discovered during build preparation, or `None` when no guide
        pages were found.
    facts
        The navbar's GitHub data, fetched when the Quarto configuration is first
        written and reused on later writes within the build. `None` before the
        first write.
    """

    project: Project
    exports: Exports
    watch: bool
    has_api_reference: bool = True
    api_discovery_done: bool = False
    user_guide: UserGuide | None = None
    facts: Facts | None = None

    @classmethod
    def make(cls, config: Config, layout: Layout, *, watch: bool) -> Run:
        """
        Create build state from the project's current files

        Parameters
        ----------
        config
            The project's configuration.
        layout
            The project's directories.
        watch
            Whether the site is served in watch mode.

        Returns
        -------
        :
            The initial build state with the project's name, metadata and GitHub repository.
        """
        project = Project.make(config, layout)
        return cls(project=project, exports=Exports(config, project), watch=watch)
