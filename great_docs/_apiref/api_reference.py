"""The `APIReference` façade and its `Settings`, built from a Quarto config block."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from yaml12 import read_yaml

from .inventory import convert_inventory, create_inventory
from .resolve import resolve
from .spec import SpecOptions, SpecSection
from .write import (
    PageWriter,
    write_index,
    write_sidebar,
    write_typing_information,
)

if TYPE_CHECKING:
    from .inventory import InventoryItem

_log = logging.getLogger(__name__)

# Compatibility-only keys that earlier configs carried but the renderer never
# consumed; dropped before parsing so they neither reach `Settings` nor error.
_REMOVED_KEYS = {"style", "renderer", "render_interlinks"}

# Parity quirks preserved deliberately (do NOT "fix" here):
#   • `version` is omitted: the old Builder accepted a `version` param but its
#     __init__ forced `self.version = None`, so objects.json was always built
#     with "0.0.9999". That behavior is kept; config `version` is not wired in.
#   • `interlinks.fast` / `_fast_inventory` is NOT read (confirmed dead — set,
#     never used). Dropped, per spec.
_SETTINGS_KEYS = {
    "parser",
    "dynamic",
    "source_dir",
    "dir",
    "out_index",
    "out_inventory",
    "out_page_suffix",
    "sidebar",
    "css",
    "header_level",
    "rewrite_all_pages",
    "typing_module_paths",
}


@dataclass
class Settings:
    """How an API reference is generated and written — the non-content keys of the `api-reference:` block"""

    parser: str = "numpy"
    dynamic: bool | None = None
    source_dir: str | None = None
    dir: str = "reference"
    out_index: str = "index.qmd"
    out_inventory: str = "objects.json"
    out_page_suffix: str = ".qmd"
    sidebar: dict[str, Any] | None = None
    css: str | None = None
    header_level: int = 1
    rewrite_all_pages: bool = False
    typing_module_paths: list[str] = field(default_factory=list[str])
    version: str | None = None


class APIReference:
    """A package's API reference: the sections to document plus the settings that govern how they are generated"""

    package: str
    title: str
    desc: str | None
    sections: list[SpecSection]
    options: SpecOptions | None
    settings: Settings
    items: list[InventoryItem]

    def __init__(self, config: dict[str, Any] | str | Path) -> None:
        block = self._select_block(config)
        block = {k: v for k, v in block.items() if k not in _REMOVED_KEYS}

        settings_kwargs: dict[str, Any] = {
            k: block[k]
            for k in _SETTINGS_KEYS
            if k in block and not (k == "out_index" and block[k] is None)
        }
        sidebar = settings_kwargs.get("sidebar")
        if isinstance(sidebar, str):
            settings_kwargs["sidebar"] = {"file": sidebar}
        elif isinstance(sidebar, dict) and "file" not in sidebar:
            sidebar["file"] = "_api-reference-sidebar.yml"
        self.settings = Settings(**settings_kwargs)

        self.package = block["package"]
        self.title = block.get("title", "Function reference")
        self.desc = block.get("desc")
        # Parity: stored as-is (no coercion), matching the previous behavior.
        self.options = block.get("options")
        # Raw config dicts become `SpecSection` objects; their `contents` are
        # upgraded to `SpecObject` inside `SpecSection.__post_init__`.
        raw_sections: list[Any] = block.get("sections", []) or []
        self.sections = [
            s if isinstance(s, SpecSection) else SpecSection(**s) for s in raw_sections
        ]
        self.items = []

    @staticmethod
    def _select_block(config: dict[str, Any] | str | Path) -> dict[str, Any]:
        """The `api-reference:` (or legacy `quartodoc:`) mapping for a config dict, file path, or full _quarto.yml"""
        if isinstance(config, (str, Path)):
            loaded = read_yaml(str(config))
            cfg: dict[str, Any] = cast("dict[str, Any]", loaded) if isinstance(loaded, dict) else {}
        else:
            cfg = config
        block = cfg.get("api-reference") or cfg.get("quartodoc") or cfg
        if not isinstance(block, dict) or "package" not in block:
            raise KeyError("No `api-reference:` section found in your _quarto.yml.")
        return dict(cast("dict[str, Any]", block))

    def build(self, filter: str = "*") -> None:
        """Reference pages, index, inventory, and (optionally) sidebar written to disk"""
        s = self.settings

        if s.source_dir:
            sys.path.append(str(Path(s.source_dir).absolute()))

        from .collect import build_manifest

        _log.info("Generating blueprint.")
        resolved = resolve(self.sections, package=self.package, settings=s)

        _log.info("Collecting pages and inventory items.")
        manifest = build_manifest(resolved, dir=s.dir)
        pages, self.items = manifest.pages, manifest.items

        _log.info("Writing index")
        _ = write_index(
            self, resolved, dir=s.dir, out_index=s.out_index, header_level=s.header_level
        )

        _log.info("Writing docs pages")
        PageWriter().write_all(
            pages,
            dir=s.dir,
            out_page_suffix=s.out_page_suffix,
            rewrite_all_pages=s.rewrite_all_pages,
            header_level=s.header_level,
            filter=filter,
        )
        write_typing_information(s.typing_module_paths, self)

        _log.info("Creating inventory file")
        version = "0.0.9999" if s.version is None else s.version
        convert_inventory(create_inventory(self.package, version, self.items), s.out_inventory)

        if s.sidebar:
            _log.info(f"Writing sidebar yaml to {s.sidebar['file']}")
            write_sidebar(self, resolved, dir=s.dir, out_page_suffix=s.out_page_suffix)
