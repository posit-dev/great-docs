"""
The `APIReference` façade, built from a Quarto config block
"""

from __future__ import annotations

import logging
import sys
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import griffe as gf
from griffe import AliasResolutionError, CyclicAliasError

from .._interlinks.sphinx_inventory import INVENTORY_FILENAME
from ._customisation import Extension
from ._extension_loading import _ExtensionSource
from ._rendering._renderers import Renderers
from ._settings import Settings, SourceLinks
from .content import Doc, Page
from .inventory import create_inventory, write_inventory
from .resolve import ObjectNotFoundError, Resolver, resolution_lang
from .spec import SpecObject, SpecOptions, SpecSection, unique_page_paths
from .write import (
    write_index,
    write_pages,
    write_sidebar,
    write_typing_information,
)

if TYPE_CHECKING:
    from .collect import Manifest
    from .content import Section
    from .inventory import InventoryItem

_log = logging.getLogger(__name__)

# Compatibility-only keys that earlier configs carried but the renderer never
# consumed; dropped before parsing so they neither reach `Settings` nor error.
_REMOVED_KEYS = {"style", "renderer", "render_interlinks"}

# Use the default site depth when a bare API reference config supplies no site
# settings.
_DEFAULT_SITE_TOC_DEPTH = 2


class APIReference:
    """A package's API reference: the sections to document plus the settings that govern how they are generated"""

    package: str
    title: str
    desc: str | None
    sections: list[SpecSection]
    options: SpecOptions | None
    settings: Settings
    site_toc_depth: int

    def __init__(
        self,
        config: dict[str, Any],
        source_links: SourceLinks | None = None,
        *,
        extension_source: _ExtensionSource | None = None,
        output_root: Path | None = None,
    ) -> None:
        """
        Configure an API reference from Quarto settings and source-link destinations

        Parameters
        ----------
        config
            The Quarto configuration mapping or its `api-reference` block.
        source_links
            The source-link destinations, or `None` to disable source links.
        extension_source
            The extension file and the project directories, or `None` to use only the
            handlers registered through `great_docs.hooks`. Reading the configuration
            and sections never loads the file.
        output_root
            The generated documentation root, or `None` when the reference writes no
            files.
        """
        self._extension_source = extension_source
        self.output_root = output_root
        self._extension: Extension | None = None
        self._closed = False
        self.site_toc_depth = self._read_site_toc_depth(config)
        block = self._select_block(config)
        block = {k: v for k, v in block.items() if k not in _REMOVED_KEYS}

        self.settings = Settings.make(
            block, lang=self._read_lang(config), source_links=source_links
        )
        self.package = block["package"]
        self.title = block.get("title", "Function reference")
        self.desc = block.get("desc")
        # Parity: stored as-is (no coercion), matching the previous behavior.
        self.options = block.get("options")
        # Raw config dicts become `SpecSection` objects; their `contents` are
        # upgraded to `SpecObject` inside `SpecSection.__post_init__`.
        self._resolver = Resolver(self.settings)
        self._resolver.current_package = self.package

        raw_sections: list[Any] = block.get("sections", []) or []
        # Page paths are settled here, before anything reads them, so the pages,
        # the index, the sidebar and `llms.txt` all agree on where each page lives.
        self.sections = unique_page_paths(
            [s if isinstance(s, SpecSection) else SpecSection(**s) for s in raw_sections],
            self._entry_label,
        )

    @property
    def extension(self) -> Extension:
        """
        The operation owner, loading configured Python on first access

        Execute the entry file and its `setup(extension)` once for this reference.
        Reading authored sections and closing an unused reference do not access it.
        """
        if self._closed:
            raise RuntimeError("The API reference is closed.")
        if self._extension is None:
            self._extension = Extension(self.settings, self._extension_source)
        if self.settings.source_dir:
            source_dir = str(Path(self.settings.source_dir).absolute())
            if source_dir not in sys.path:
                sys.path.append(source_dir)
        self._extension.load()
        self._resolver.extension = self._extension
        return self._extension

    @property
    def renderers(self) -> Renderers:
        """Renderer choices selected by this operation's setup"""
        return self.extension.renderers

    def get_object(self, path: str) -> gf.Object | gf.Alias:
        """
        Load a Python object through the reference's shared loader

        Initialise configured setup and use the operation's parser, source path
        and dynamic setting. Keep acquisition separate from semantic preparation.
        """
        _ = self.extension
        return self._resolver.get_object_or_raise(path, dynamic=self._resolver.dynamic)

    def prepare(self, obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias | None:
        """
        Prepare a loaded object's documentation with the reference's extension

        Each underlying object is prepared once, and pages, helpers and typing pages
        share its result or exclusion. An alias keeps its own name without a second copy
        of the documentation.

        Parameters
        ----------
        obj
            The loaded object or alias.

        Returns
        -------
        :
            The prepared object, or `None` when an object hook excludes it.
        """
        _ = self.extension
        return self._resolver.prepare(obj)

    def close(self) -> None:
        """Release an active extension without loading an unused reference"""
        if self._closed:
            return
        self._closed = True
        if self._extension is not None:
            self._extension.close()

    @staticmethod
    def _read_lang(cfg: dict[str, Any]) -> str:
        """
        Read the reference language from the Quarto HTML settings

        Parameters
        ----------
        cfg
            Configuration mapping.

        Returns
        -------
        The language at `format.html.lang`, with `en` as the default when absent.
        """
        format_config = cfg.get("format")
        html = (
            cast("dict[str, Any]", format_config).get("html")
            if isinstance(format_config, dict)
            else None
        )
        return cast("dict[str, Any]", html).get("lang", "en") if isinstance(html, dict) else "en"

    @staticmethod
    def _read_site_toc_depth(cfg: dict[str, Any]) -> int:
        """
        Read the configured table-of-contents depth

        Use the integer at `format.html.toc-depth` when available, then the
        integer at `site.toc-depth`. Return the built-in default when neither
        setting is an integer.

        Parameters
        ----------
        cfg
            Configuration mapping.

        Returns
        -------
        Configured depth or the built-in default.
        """
        format_config = cfg.get("format")
        html = (
            cast("dict[str, Any]", format_config).get("html")
            if isinstance(format_config, dict)
            else None
        )
        depth = cast("dict[str, Any]", html).get("toc-depth") if isinstance(html, dict) else None
        if isinstance(depth, int):
            return depth

        site = cfg.get("site")
        depth = cast("dict[str, Any]", site).get("toc-depth") if isinstance(site, dict) else None
        return depth if isinstance(depth, int) else _DEFAULT_SITE_TOC_DEPTH

    @staticmethod
    def _select_block(cfg: dict[str, Any]) -> dict[str, Any]:
        """
        Select the API reference configuration

        Select a non-empty `api-reference` mapping before the legacy
        `quartodoc` mapping. Treat the full configuration as the API reference
        mapping when both sections are empty or absent.

        Parameters
        ----------
        cfg
            Configuration mapping.

        Returns
        -------
        Copy of the selected API reference mapping.

        Raises
        ------
        KeyError
            If the selected value is not a mapping or omits `package`.
        """
        block = cfg.get("api-reference") or cfg.get("quartodoc") or cfg
        if not isinstance(block, dict) or "package" not in block:
            raise KeyError("No `api-reference:` section found in your _quarto.yml.")
        return dict(cast("dict[str, Any]", block))

    def _entry_label(self, section: SpecSection, entry: SpecObject) -> str | None:
        """
        The label shown on the page of the object an entry documents

        Used to name the page of an entry whose path collides with another's.
        Returns `None` when the object cannot be found, so the page falls back
        to a numbered suffix.
        """
        from ._rendering._label import get_label

        s = self.settings
        if s.source_dir and (source_dir := str(Path(s.source_dir).absolute())) not in sys.path:
            sys.path.append(source_dir)
        try:
            return get_label(self._resolver.entry_object(section, entry))
        except (ObjectNotFoundError, ImportError, AliasResolutionError, CyclicAliasError):
            return None

    @cached_property
    def resolved(self) -> list[Section]:
        """The resolved section tree, computed once per instance"""
        _ = self.extension
        token = resolution_lang.set(self.settings.lang)
        try:
            secs = self.sections or unique_page_paths(
                self._resolver.autogenerate_sections(self.package), self._entry_label
            )
            return self.resolve_sections(secs)
        finally:
            resolution_lang.reset(token)

    def resolve_sections(self, sections: list[SpecSection]) -> list[Section]:
        """
        Resolve selected sections through this operation's prepared object graph

        Share acquisition, language, semantic hooks and member destinations with
        the complete reference. Standalone exports may resolve entries separately
        to retain valid siblings when another entry cannot be acquired. Errors
        propagate so the caller can apply its own acquisition policy.
        """
        from .collect import unique_member_page_paths

        _ = self.extension
        token = resolution_lang.set(self.settings.lang)
        try:
            return unique_member_page_paths(self._resolver.resolve_sections(sections))
        finally:
            resolution_lang.reset(token)

    @cached_property
    def documented_symbols(self) -> list[str]:
        """
        Return the authored Python names of documented objects, `%nodoc` excluded

        Preserve first-occurrence order and include each documented member
        recursively. Convert module separators to dots and keep names independent
        of the filenames assigned to reference pages.
        """
        stems: list[str] = []

        def visit(node: Doc | Page, stem: str) -> None:
            stems.append(stem)
            for member in _member_children(node):
                visit(member, f"{stem}.{_member_name(member)}")

        for section in self.resolved:
            for entry in section.contents:
                if isinstance(entry, Page):
                    for doc in entry.contents:
                        visit(doc, doc.name.replace(":", "."))
        return list(dict.fromkeys(stems))

    @cached_property
    def manifest(self) -> Manifest:
        """The pages to write and the objects to index, computed once per instance"""
        from .collect import build_manifest

        return build_manifest(self.resolved, dir=self.settings.dir)

    @property
    def items(self) -> list[InventoryItem]:
        """The objects this reference publishes, each with the page it lands on"""
        return self.manifest.items

    def build(self) -> None:
        """Write reference pages, index, inventory, and (optionally) sidebar to disk"""
        s = self.settings

        _log.info("Resolving sections.")
        resolved = self.resolved

        _log.info("Collecting pages and inventory items.")
        pages = self.manifest.pages

        _log.info("Writing index")
        _ = write_index(
            self, resolved, dir=s.dir, out_index=s.out_index, header_level=s.header_level
        )

        _log.info("Writing docs pages")
        write_pages(
            pages,
            s,
            site_toc_depth=self.site_toc_depth,
            renderers=self.renderers,
            extension=self.extension,
            output_root=self.output_root,
        )
        write_typing_information(s.typing_module_paths, self)

        _log.info("Creating inventory file")
        version = "0.0.9999" if s.version is None else s.version
        write_inventory(create_inventory(self.package, version, self.items), INVENTORY_FILENAME)

        if s.sidebar:
            _log.info(f"Writing sidebar yaml to {s.sidebar['file']}")
            write_sidebar(self, resolved, dir=s.dir, out_page_suffix=s.out_page_suffix)


def _member_name(node: Doc | Page) -> str:
    """
    Return a member's name relative to its documented parent
    """
    if isinstance(node, Page):
        return node.contents[0].name
    return node.name


def _member_children(node: Doc | Page) -> list[Doc | Page]:
    """The nested member nodes of a resolved member node, if any"""
    doc = node.contents[0] if isinstance(node, Page) else node
    return list(getattr(doc, "members", []))
