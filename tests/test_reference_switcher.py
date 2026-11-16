from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

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


@pytest.mark.parametrize(
    ("sections", "preferred", "ordered"),
    [
        (("mcp",), None, "mcp"),
        (("cli", "mcp"), None, "cli,mcp"),
        (("cli", "mcp"), ["mcp", "cli"], "mcp,cli"),
    ],
)
def test_switcher_without_python_lists_only_available_references(
    tmp_path: Path, sections: tuple[str, ...], preferred: list[str] | None, ordered: str
) -> None:
    for section in sections:
        _write_index(tmp_path, section)
    quarto_config = _quarto_config()
    quarto_config["website"]["navbar"]["left"] = [
        {"text": "Custom reference", "href": f"reference/{sections[0]}/index.qmd"}
    ]

    _register(quarto_config, tmp_path, has_api_reference=False, ref_section_order=preferred)

    assert quarto_config["format"]["html"]["include-in-header"][1] == _sections_script(ordered)
    assert quarto_config["website"]["navbar"]["left"] == [
        {"text": "Custom reference", "href": f"reference/{ordered.split(',')[0]}/index.qmd"}
    ]
