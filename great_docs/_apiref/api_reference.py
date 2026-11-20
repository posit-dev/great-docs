"""
The `APIReference` façade, built from a Quarto config block

A reference loads its objects through one loader and prepares them with one extension,
whose `setup` runs before the first object is prepared or rendered. Manifests, symbol
queries and the text export reuse the prepared tree. Building renders every page before
it fingerprints the extension's inputs and writes any file. Close the reference after
its last use.
"""

from __future__ import annotations

import logging
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
from .resolve import ObjectNotFoundError, Resolver
from .spec import SpecObject, SpecOptions, SpecSection, unique_page_paths
from .write import (
    collect_index,
    collect_pages,
    collect_typing_information,
    write_sidebar,
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
    """
    A package's API reference: its sections, their settings and its extension

    Reading the sections never loads the extension file. The first preparation or
    rendering runs the extension's `setup`, and every page then shares the prepared
    objects, exclusions and renderer choices. The resolved tree and manifest are cached.
    Call `close()` after the last use, including after a failure.
    """

    package: str
    title: str
    desc: str | None
    sections: list[SpecSection]
    options: SpecOptions | None
    settings: Settings
    site_toc_depth: int
    extension: Extension

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
        self.site_toc_depth = self._read_site_toc_depth(config)
        block = self._select_block(config)
        block = {k: v for k, v in block.items() if k not in _REMOVED_KEYS}

        self.settings = Settings.make(
            block, lang=self._read_lang(config), source_links=source_links
        )
        self.package = block["package"]
        self.title = block.get("title", "Function reference")
        self.desc = block.get("desc")
        # Parity: stored as-is (no coercion), matching the previous behaviour.
        self.options = block.get("options")
        self.extension = Extension(self.settings, extension_source, output_root=output_root)
        # Raw config dicts become `SpecSection` objects; their `contents` are
        # upgraded to `SpecObject` inside `SpecSection.__post_init__`.
        self._resolver = Resolver(self.settings, self.extension)
        self._resolver.current_package = self.package

        raw_sections: list[Any] = block.get("sections", []) or []
        # Page paths are settled here, before anything reads them, so the pages,
        # the index, the sidebar and `llms.txt` all agree on where each page lives.
        self.sections = unique_page_paths(
            [s if isinstance(s, SpecSection) else SpecSection(**s) for s in raw_sections],
            self._entry_label,
        )

    @property
    def renderers(self) -> Renderers:
        """The renderers that the extension's `setup` selected, running `setup` on first read"""
        return self.extension.renderers

    @property
    def extension_watch_paths(self) -> tuple[Path, ...]:
        """
        The paths that a preview watches for the extension, readable after closing

        Globs stay unexpanded, so the preview can watch for new matches. Reading the paths
        never loads the extension file, so before `setup` runs they hold only the
        extension file's directory.
        """
        return self.extension.watch_paths

    def get_object(self, path: str) -> gf.Object | gf.Alias:
        """
        Load a Python object through the reference's shared loader

        Use the reference's parser, source directory and dynamic setting. Loading neither
        runs the extension's `setup` nor prepares the object.

        Parameters
        ----------
        path
            The object's import path.

        Returns
        -------
        :
            The loaded object or alias.

        Raises
        ------
        ObjectNotFoundError
            If the package has no object at `path`.
        """
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
        return self._resolver.prepare(obj)

    def close(self) -> None:
        """Close the extension without loading it, removing the modules it imported"""
        self.extension.close()

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
        :
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
        :
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
        :
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
        Read the kind label of an entry whose page path collides with another's

        Load the object without running the extension's `setup` or the object and
        docstring hooks.

        Parameters
        ----------
        section
            The section that contains the entry.
        entry
            The entry whose page path collides.

        Returns
        -------
        :
            The label, or `None` when the object cannot be loaded, so the page falls back
            to a numbered suffix.
        """
        from ._rendering._label import get_label

        try:
            return get_label(self._resolver.entry_object(section, entry))
        except (ObjectNotFoundError, ImportError, AliasResolutionError, CyclicAliasError):
            return None

    @cached_property
    def resolved(self) -> list[Section]:
        """
        The resolved section tree, computed once per reference

        Reading it runs the extension's `setup` and the object and docstring hooks,
        including during member selection. It leaves file generation to the build.
        """
        from .collect import unique_member_page_paths

        # Load before resolving, so a broken extension fails a query that selects
        # no objects.
        self.extension.load()
        secs = self.sections or unique_page_paths(
            self._resolver.autogenerate_sections(self.package), self._entry_label
        )
        return unique_member_page_paths(self._resolver.resolve_sections(secs))

    @cached_property
    def documented_symbols(self) -> list[str]:
        """
        The authored names of documented objects and their selected members

        Names keep their first-seen order, use dots as module separators and leave out
        objects that object hooks exclude. Reading them prepares the reference without
        generating pages.
        """
        stems: list[str] = []

        def visit(node: Doc | Page, stem: str) -> None:
            """
            Record the name of an object and of its nested members

            Parameters
            ----------
            node
                The object, or the member page that holds it.
            stem
                The object's dotted name.
            """
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
        """
        Write the reference pages, index, inventory and, optionally, sidebar

        Render the index, object pages and typing pages before writing any of them. When
        an extension file is configured, every page then carries one fingerprint of its
        inputs, including helpers first imported while rendering. Leave unchanged object
        pages alone unless `rewrite_all_pages` is set.
        """
        s = self.settings

        _log.info("Resolving sections.")
        resolved = self.resolved

        _log.info("Collecting pages and inventory items.")
        pages = self.manifest.pages
        if s.show_bases:
            self.extension.class_targets = self.manifest.class_targets

        _log.info("Collecting index")
        index = collect_index(
            self, resolved, dir=s.dir, out_index=s.out_index, header_level=s.header_level
        )

        _log.info("Collecting docs pages")
        object_pages = collect_pages(pages, self.extension, site_toc_depth=self.site_toc_depth)
        typing_pages = collect_typing_information(s.typing_module_paths, self)
        fingerprint = self.extension.fingerprint()
        index.write(fingerprint=fingerprint)
        for page in object_pages:
            page.write(fingerprint=fingerprint, rewrite_unchanged=s.rewrite_all_pages)
        for page in typing_pages:
            page.write(fingerprint=fingerprint)

        _log.info("Creating inventory file")
        version = "0.0.9999" if s.version is None else s.version
        write_inventory(create_inventory(self.package, version, self.items), INVENTORY_FILENAME)

        if s.sidebar:
            _log.info(f"Writing sidebar yaml to {s.sidebar['file']}")
            write_sidebar(self, resolved, dir=s.dir, out_page_suffix=s.out_page_suffix)


def _member_name(node: Doc | Page) -> str:
    """
    Return a member's name relative to its documented parent

    Parameters
    ----------
    node
        The member, or the member page that holds it.

    Returns
    -------
    :
        The name.
    """
    if isinstance(node, Page):
        return node.contents[0].name
    return node.name


def _member_children(node: Doc | Page) -> list[Doc | Page]:
    """
    Return the nested members and dataclass fields of a resolved object or member page

    Parameters
    ----------
    node
        The object, or the member page that holds it.

    Returns
    -------
    :
        The members, then any dataclass fields, or an empty list for an object that has
        neither.
    """
    doc = node.contents[0] if isinstance(node, Page) else node
    return [*getattr(doc, "members", []), *getattr(doc, "fields", [])]
