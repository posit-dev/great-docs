"""
The settings of an API reference, read from its Quarto config block
"""

from __future__ import annotations

from dataclasses import dataclass, field
from dataclasses import fields as dc_fields
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class CallableSignatures:
    """How the signature of a function, method or class is written"""

    style: str = "highlighted"
    """`highlighted` for a highlighted code block, `plain` for inline markup"""

    wrap: str = "per_parameter"
    """`per_parameter` for one parameter per line, `width` to break only when long"""


@dataclass(frozen=True)
class SourceLinks:
    """
    GitHub source-link destinations for documented objects

    The default settings produce no source links.
    """

    repo_url: str | None = None
    """The GitHub repository's URL, or `None` when objects have no source links"""

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

    Generation options come from the `api-reference:` block, the language from
    the site configuration and the source links from the project. Block options
    exclude `version`.
    """

    parser: str = "numpy"
    callable_signatures: CallableSignatures = field(default_factory=CallableSignatures)
    dynamic: bool | None = None
    source_dir: str | None = None
    dir: str = "reference"
    out_index: str = "index.qmd"
    out_page_suffix: str = ".qmd"
    sidebar: dict[str, Any] | None = None
    css: str | None = None
    header_level: int = 1
    rewrite_all_pages: bool = False
    typing_module_paths: list[str] = field(default_factory=list[str])
    version: str | None = None
    lang: str = "en"
    """The reference language as a BCP 47 tag"""
    source_links: SourceLinks = field(default_factory=SourceLinks)
    """The source-link destinations for documented objects"""

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


# Parity quirk preserved deliberately (do NOT "fix" here): `version` is not
# read from the config block. The old Builder accepted a `version` param but
# its __init__ forced `self.version = None`, so the inventory was always built
# with "0.0.9999". (`interlinks.fast` / `_fast_inventory` was confirmed dead
# and dropped, per spec.)
# The site configuration supplies the language; the project supplies source links.
_SETTINGS_KEYS = {f.name for f in dc_fields(Settings)} - {"version", "lang", "source_links"}
