"""
The settings of an API reference, read from its Quarto config block
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from dataclasses import fields as dc_fields
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass
class CallableSignatures:
    """How the signature of a function, method or class is written"""

    style: str = "highlighted"
    """`highlighted` for a highlighted code block, `plain` for inline markup"""

    wrap: str = "per_parameter"
    """`per_parameter` for one parameter per line, `width` to break only when long"""


@dataclass
class Settings:
    """How an API reference is generated and written — the non-content keys of the `api-reference:` block"""

    parser: str = "numpy"
    callable_signatures: CallableSignatures = field(default_factory=CallableSignatures)
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

    @classmethod
    def make(cls, block: dict[str, Any]) -> Settings:
        """Build settings from the non-content keys of an `api-reference:` block"""
        kwargs: dict[str, Any] = {
            k: block[k]
            for k in _SETTINGS_KEYS
            if k in block and not (k == "out_index" and block[k] is None)
        }
        signatures = kwargs.get("callable_signatures")
        if isinstance(signatures, dict):
            kwargs["callable_signatures"] = CallableSignatures(**signatures)

        sidebar = kwargs.get("sidebar")
        if isinstance(sidebar, str):
            kwargs["sidebar"] = {"file": sidebar}
        elif isinstance(sidebar, dict) and "file" not in sidebar:
            # Copy so the caller's config dict is not mutated.
            kwargs["sidebar"] = {**sidebar, "file": "_api-reference-sidebar.yml"}
        return cls(**kwargs)


# Parity quirk preserved deliberately (do NOT "fix" here): `version` is not
# read from the config block. The old Builder accepted a `version` param but
# its __init__ forced `self.version = None`, so objects.json was always built
# with "0.0.9999". (`interlinks.fast` / `_fast_inventory` was confirmed dead
# and dropped, per spec.)
_SETTINGS_KEYS = {f.name for f in dc_fields(Settings)} - {"version"}


@contextmanager
def active_settings(settings: Settings) -> Iterator[None]:
    """
    Make `settings` the ones the render classes read, for one build

    `RenderBase` receives a node and display flags only, so settings reach the
    render classes through module state, as exclusions already do. The state
    is put back on the way out, because one process can build more than one
    API reference and the settings of one must not govern the next.

    Parameters
    ----------
    settings
        The settings of the API reference being built.

    Yields
    ------
    :
    """
    from . import _globals

    previous = _globals.SETTINGS
    _globals.SETTINGS = settings
    try:
        yield
    finally:
        _globals.SETTINGS = previous
