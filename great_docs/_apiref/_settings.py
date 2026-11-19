"""
Settings for loading, rendering and linking the objects of an API reference

Read generation options from the Quarto `api-reference` block and combine them with the
site language and the project's source links. Settings hold values only: building them
never loads the extension, which keeps its own registrations and imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from dataclasses import fields as dc_fields
from typing import TYPE_CHECKING, Any, cast

from .._config_compat import normalise_member_placement

if TYPE_CHECKING:
    from pathlib import Path

    from .._project.repository import Repository


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

    Generation options come from the `api-reference:` block, the language from the site
    configuration and the source links from the project. `make()` ignores the block's
    `version` key, but code that builds settings directly may supply an inventory version.
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
        block: dict[str, Any],
        lang: str = "en",
        source_links: SourceLinks | None = None,
    ) -> Settings:
        """
        Build reference settings from generation options, the site language and source links

        Parameters
        ----------
        block
            The `api-reference:` block.
        lang
            The reference language as a BCP 47 tag.
        source_links
            The source-link destinations, or `None` to disable source links.

        Returns
        -------
        :
            Settings with the supplied generation options, language and source links.
        """
        block = normalise_member_placement(block, default_limit=cls.max_members_on_same_page)
        kwargs: dict[str, Any] = {
            k: block[k]
            for k in _SETTINGS_KEYS
            if k in block and not (k == "out_index" and block[k] is None)
        }
        signatures: dict[str, Any] | None = kwargs.get("callable_signatures")
        if isinstance(signatures, dict):
            kwargs["callable_signatures"] = CallableSignatures(**signatures)

        sidebar = kwargs.get("sidebar")
        if isinstance(sidebar, str):
            kwargs["sidebar"] = {"file": sidebar}
        elif isinstance(sidebar, dict) and "file" not in sidebar:
            # Copy so the caller's config dict is not mutated.
            kwargs["sidebar"] = {**sidebar, "file": "_api-reference-sidebar.yml"}
        return cls(**kwargs, lang=lang, source_links=source_links or SourceLinks())


# Keys read from the reference block. Only code can set the inventory version, and the
# language and source links come from the site and the project.
_SETTINGS_KEYS = {f.name for f in dc_fields(Settings)} - {"version", "lang", "source_links"}
