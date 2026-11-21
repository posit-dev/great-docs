"""
Settings for loading, rendering and linking the objects of an API reference

Read generation options from the documentation configuration and combine them with the
project's source links. Settings contain only values, so constructing them leaves the
extension unloaded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from pathlib import Path

    from .._project.repository import Repository
    from ..config import Config


@dataclass
class CallableSignatures:
    """How the signature of a function, method or class is written and wrapped"""

    style: str = "highlighted"
    """`highlighted` for a highlighted code block, `plain` for inline markup"""

    wrap: str = "per_parameter"
    """`per_parameter` for one parameter per line, `width` to break only when long"""


@dataclass(frozen=True)
class SourceLinks:
    """
    Repository source-link destinations for documented objects

    The default settings produce no source links.
    """

    repository: Repository | None = None
    """The repository, or `None` when objects have no source links"""

    ref: str = "main"
    """The tag or branch targeted by source links"""

    package_root: Path | None = None
    """The repository root for relative source file paths"""

    path: str | None = None
    """
    The source directory override, relative to the repository root

    Links use each file's name within this directory, regardless of its actual
    location. `None` preserves paths relative to `package_root`.
    """


@dataclass
class Settings:
    """
    Settings for generating an API reference

    The site's configuration supplies generation options and language. A build can
    supply source links and choose static introspection when its dynamic attempt fails.
    """

    parser: str = "numpy"
    """The docstring parser for every object in the reference"""
    callable_signatures: CallableSignatures = field(default_factory=CallableSignatures)
    """How callable signatures are written and wrapped"""
    dynamic: bool | None = None
    """Whether to load objects by importing the package, or `None` for the default"""
    members_on_same_page: bool | None = None
    """Same-page override for top-level entries, or `None` to use the member limit"""
    max_members_on_same_page: int = 5
    """Automatic limit on documented direct members sharing their parent page"""
    source_dir: str | None = None
    """An extra directory to search for imports, or `None`"""
    dir: str = "reference"
    """The output directory for reference pages"""
    out_index: str = "index.qmd"
    """The index page's filename within the reference directory"""
    out_page_suffix: str = ".qmd"
    """The filename suffix of object pages"""
    sidebar: dict[str, Any] | None = None
    """Sidebar options, or `None` to write no sidebar"""
    css: str | None = None
    header_level: int = 1
    """The heading level at which reference pages start"""
    rewrite_all_pages: bool = False
    """Whether to rewrite object pages whose content has not changed"""
    typing_module_paths: list[str] = field(default_factory=list[str])
    """Import paths of modules whose own typing objects get dedicated pages"""
    version: str | None = None
    """The inventory version, which only code can set, or `None` for the default"""
    lang: str = "en"
    """The reference language as a BCP 47 tag"""
    source_links: SourceLinks = field(default_factory=SourceLinks)
    """The source-link destinations for documented objects"""

    show_bases: bool = False
    """Whether class documentation lists direct base classes"""

    def __post_init__(self) -> None:
        """Validate display and member placement settings"""
        if not isinstance(cast("object", self.show_bases), bool):
            raise ValueError("`show_bases` must be true or false.")
        same_page = cast("object", self.members_on_same_page)
        if same_page is not None and not isinstance(same_page, bool):
            raise ValueError("Global `members_on_same_page` must be true, false or null.")
        maximum = cast("object", self.max_members_on_same_page)
        if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum < 0:
            raise ValueError("`max_members_on_same_page` must be a non-negative integer.")

    @classmethod
    def make(
        cls,
        config: Config,
        *,
        dynamic: bool | None = None,
        source_links: SourceLinks | None = None,
    ) -> Settings:
        """
        Read reference generation settings from the documentation configuration

        Parameters
        ----------
        config
            The project's documentation configuration.
        dynamic
            The introspection mode for this attempt, or `None` to use the site setting.
        source_links
            The destinations for source links, or `None` to disable them.

        Returns
        -------
        :
            The settings for this reference.
        """
        return cls(
            parser=config.parser or "numpy",
            callable_signatures=CallableSignatures(
                style=config.callable_signatures_style,
                wrap=config.callable_signatures_wrap,
            ),
            dynamic=config.dynamic if dynamic is None else dynamic,
            members_on_same_page=config.members_on_same_page,
            max_members_on_same_page=config.max_members_on_same_page,
            lang=config.lang,
            source_links=source_links or SourceLinks(),
            show_bases=config.reference_show_bases,
        )
