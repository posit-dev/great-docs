from __future__ import annotations

from typing import Any

from great_docs._website.navigation import reference_switcher
from tests.support import mock_config

_SWITCHER = '<script src="/reference-switcher.js"></script>'
_TOOLTIPS = '<script src="/tooltips.js"></script>'


def _quarto_config() -> dict[str, Any]:
    return {
        "website": {"navbar": {"left": [{"text": "Reference", "href": "reference/index.qmd"}]}},
        "format": {
            "html": {
                "include-in-header": [{"text": "<meta name='first'>"}],
                "include-after-body": [{"text": _TOOLTIPS}],
            }
        },
    }


def _register(
    quarto_config: dict[str, Any],
    *,
    has_api_reference: bool = True,
    has_mcp_reference: bool | None = False,
    **settings: Any,
) -> dict[str, Any]:
    reference_switcher.register(
        quarto_config,
        mock_config(**settings),
        has_api_reference=has_api_reference,
        has_mcp_reference=has_mcp_reference,
    )
    return quarto_config


def _sections_script(sections: str) -> dict[str, str]:
    return {
        "text": "<script>document.addEventListener('DOMContentLoaded',function(){"
        f"document.body.setAttribute('data-gd-ref-sections','{sections}');"
        "});</script>"
    }


def test_lists_sections_and_loads_switcher_before_tooltips():
    html = _register(_quarto_config(), cli_enabled=True, has_mcp_reference=True)["format"]["html"]

    assert html["include-in-header"][1] == _sections_script("api,cli,mcp")
    assert html["include-after-body"] == [{"text": _SWITCHER}, {"text": _TOOLTIPS}]


def test_assumes_mcp_pages_until_the_mcp_step_decides():
    html = _register(_quarto_config(), mcp_enabled=True, has_mcp_reference=None)["format"]["html"]

    assert html["include-in-header"][1] == _sections_script("api,mcp")


def test_orders_sections_and_opens_the_first_from_the_navbar():
    quarto_config = _register(
        _quarto_config(), go_cli_enabled=True, ref_section_order=["cli", "api"]
    )

    assert quarto_config["format"]["html"]["include-in-header"][1] == _sections_script("cli,api")
    assert quarto_config["website"]["navbar"]["left"][0]["href"] == "reference/cli/index.qmd"


def test_replaces_the_sections_in_place():
    quarto_config = _register(_quarto_config(), cli_enabled=True, has_mcp_reference=True)
    quarto_config["format"]["html"]["include-in-header"].append({"text": "<meta name='last'>"})

    headers = _register(quarto_config, cli_enabled=True)["format"]["html"]["include-in-header"]

    assert headers[1:] == [_sections_script("api,cli"), {"text": "<meta name='last'>"}]


def test_removes_the_switcher_when_only_the_api_reference_remains():
    quarto_config = _register(_quarto_config(), has_mcp_reference=True)

    html = _register(quarto_config, has_mcp_reference=False)["format"]["html"]

    assert html == _quarto_config()["format"]["html"]
