"""
Version selector entries in the Quarto configuration of a versioned site
"""

import html
import json
from pathlib import Path
from typing import Any

from great_docs._versions import selector
from great_docs.config import Config
from tests.support import write_config

VERSIONS = 'versions:\n  - "0.2"\n  - "0.1"\n'
NAVBAR_WIDGETS = {"text": '<script src="/navbar-widgets.js"></script>'}


def _register(quarto_config: dict[str, Any], config: Config) -> dict[str, Any]:
    """
    Register the selector and return the updated HTML configuration

    Parameters
    ----------
    quarto_config
        Quarto configuration, updated in place.
    config
        Project configuration with at least one version.

    Returns
    -------
    :
        The updated `format.html` mapping.
    """
    selector.register(quarto_config, config)
    return quarto_config["format"]["html"]


def _texts(entries: list[Any], marker: str) -> list[str]:
    """
    Return the text of include entries containing `marker`

    Parameters
    ----------
    entries
        Quarto include entries.
    marker
        Text to match in each entry's string representation.

    Returns
    -------
    :
        The string representations of matching entries, in their original order.
    """
    return [str(entry) for entry in entries if marker in str(entry)]


def _version_map(header: list[Any]) -> dict[str, Any]:
    """
    Decode the version map from its header meta element

    Parameters
    ----------
    header
        Header includes containing exactly one version-map meta element.

    Returns
    -------
    :
        The version map decoded from the HTML-escaped JSON attribute value.
    """
    (entry,) = [e for e in header if "gd-version-map" in str(e)]
    prefix, suffix = '<meta name="gd-version-map" content="', '">'
    text = entry["text"]
    assert text.startswith(prefix) and text.endswith(suffix)
    return json.loads(html.unescape(text[len(prefix) : -len(suffix)]))


class TestRegister:
    def test_version_map_lists_versions_without_pages(self, tmp_path: Path):
        html_config = _register({"format": {"html": {}}}, write_config(tmp_path, VERSIONS))
        version_map = _version_map(html_config["include-in-header"])
        assert [v["tag"] for v in version_map["versions"]] == ["0.2", "0.1"]
        assert version_map["pages"] == {}

    def test_banner_meta_only_when_banner_disabled(self, tmp_path: Path):
        enabled = _register({"format": {"html": {}}}, write_config(tmp_path, VERSIONS))
        assert not _texts(enabled["include-in-header"], "gd-version-warning-banner")

        disabled_config = write_config(
            tmp_path, VERSIONS + "version_selector:\n  warning_banner: false\n"
        )
        disabled = _register({"format": {"html": {}}}, disabled_config)
        assert _texts(disabled["include-in-header"], "gd-version-warning-banner") == [
            str({"text": '<meta name="gd-version-warning-banner" content="false">'})
        ]

    def test_script_precedes_navbar_widgets(self, tmp_path: Path):
        quarto_config = {
            "format": {"html": {"include-after-body": [{"text": "first"}, NAVBAR_WIDGETS]}}
        }
        html_config = _register(quarto_config, write_config(tmp_path, VERSIONS))
        assert html_config["include-after-body"] == [
            {"text": "first"},
            {"text": '<script src="/version-selector.js"></script>'},
            NAVBAR_WIDGETS,
        ]

    def test_script_appended_without_navbar_widgets(self, tmp_path: Path):
        quarto_config = {"format": {"html": {"include-after-body": "body.html"}}}
        html_config = _register(quarto_config, write_config(tmp_path, VERSIONS))
        assert html_config["include-after-body"] == [
            "body.html",
            {"text": '<script src="/version-selector.js"></script>'},
        ]
