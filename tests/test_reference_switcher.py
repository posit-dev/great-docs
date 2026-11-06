from __future__ import annotations

from pathlib import Path
from typing import Any

from great_docs._website.navigation import reference_switcher
from tests.support import mock_config

_THEME = {"text": '<script src="/theme-init.js"></script>'}
_BADGE = {"text": "<meta name='badge'>"}
_SWITCHER = {"text": '<script src="/reference-switcher.js"></script>'}
_TOOLTIPS = {"text": '<script src="/tooltips.js"></script>'}


def _quarto_config() -> dict[str, Any]:
    return {
        "website": {"navbar": {"left": [{"text": "Reference", "href": "reference/index.qmd"}]}},
        "format": {
            "html": {
                "include-in-header": [_THEME, _BADGE],
                "include-after-body": [_TOOLTIPS],
            }
        },
    }


def _write_index(build_dir: Path, section: str) -> None:
    index = build_dir / "reference" / section / "index.qmd"
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text("", encoding="utf-8")


def _register(
    quarto_config: dict[str, Any],
    build_dir: Path,
    *,
    has_api_reference: bool = True,
    **settings: Any,
) -> dict[str, Any]:
    reference_switcher.register(
        quarto_config, mock_config(**settings), build_dir, has_api_reference=has_api_reference
    )
    return quarto_config


def _sections_script(sections: str) -> dict[str, str]:
    return {
        "text": "<script>document.addEventListener('DOMContentLoaded',function(){"
        f"document.body.setAttribute('data-gd-ref-sections','{sections}');"
        "});</script>"
    }


def test_lists_sections_after_the_theme_script_and_loads_switcher_before_tooltips(tmp_path: Path):
    _write_index(tmp_path, "cli")
    _write_index(tmp_path, "mcp")

    quarto_config = _register(_quarto_config(), tmp_path)

    html = quarto_config["format"]["html"]
    assert html["include-in-header"] == [_THEME, _sections_script("api,cli,mcp"), _BADGE]
    assert html["include-after-body"] == [_SWITCHER, _TOOLTIPS]
    assert quarto_config["project"]["resources"] == ["reference-switcher.js"]
    assert (tmp_path / "reference-switcher.js").is_file()


def test_omits_enabled_references_without_pages(tmp_path: Path):
    quarto_config = _register(_quarto_config(), tmp_path, cli_enabled=True, mcp_enabled=True)

    assert quarto_config == _quarto_config()
    assert not (tmp_path / "reference-switcher.js").exists()


def test_orders_sections_and_opens_the_first_from_the_navbar(tmp_path: Path):
    _write_index(tmp_path, "cli")

    quarto_config = _register(_quarto_config(), tmp_path, ref_section_order=["cli", "api"])

    assert quarto_config["format"]["html"]["include-in-header"][1] == _sections_script("cli,api")
    assert quarto_config["website"]["navbar"]["left"][0]["href"] == "reference/cli/index.qmd"
