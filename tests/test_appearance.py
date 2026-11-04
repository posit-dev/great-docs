from pathlib import Path
from typing import Any

from great_docs._website import appearance
from tests.support import write_config


def _texts(quarto_config: dict[str, Any], slot: str) -> list[str]:
    return [str(item) for item in quarto_config["format"]["html"].get(slot, [])]


def test_wide_layout_disabling_removes_stale_entries(tmp_path: Path):
    """Entries left from an earlier enabled build are removed when disabled"""
    quarto_config: dict[str, Any] = {"format": {"html": {}}}
    enabled = write_config(tmp_path)

    appearance.register_wide_layout(quarto_config, enabled)
    appearance.register_wide_layout(quarto_config, enabled)
    assert len(_texts(quarto_config, "include-in-header")) == 1
    assert len(_texts(quarto_config, "include-after-body")) == 1

    appearance.register_wide_layout(quarto_config, write_config(tmp_path, "wide_layout: false\n"))
    assert quarto_config["format"]["html"]["include-in-header"] == []
    assert quarto_config["format"]["html"]["include-after-body"] == []


def test_wide_layout_handles_string_includes(tmp_path: Path):
    """String include values are converted to lists and preserved"""
    quarto_config: dict[str, Any] = {
        "format": {"html": {"include-in-header": "head.html", "include-after-body": "x.html"}}
    }

    appearance.register_wide_layout(quarto_config, write_config(tmp_path))

    header = _texts(quarto_config, "include-in-header")
    after_body = _texts(quarto_config, "include-after-body")
    assert header[0] == "head.html"
    assert after_body[0] == "x.html"
    assert len(header) == 2 and len(after_body) == 2


def test_repeated_registration_keeps_every_entry_in_place(tmp_path: Path):
    config = write_config(
        tmp_path,
        "announcement: News\n"
        "navbar_color: '#123456'\n"
        "accent_color: '#ff0000'\n"
        "content_style: aurora\n"
        "scale_to_fit: ['.wide']\n",
    )
    quarto_config: dict[str, Any] = {"format": {"html": {}}}
    appearance.register(quarto_config, config)
    # Entries from later configuration steps follow the appearance entries
    for slot in ("include-in-header", "include-after-body"):
        quarto_config["format"]["html"][slot].append({"text": '<script src="/later.js"></script>'})
    header = _texts(quarto_config, "include-in-header")
    after_body = _texts(quarto_config, "include-after-body")

    appearance.register(quarto_config, config)

    assert _texts(quarto_config, "include-in-header") == header
    assert _texts(quarto_config, "include-after-body") == after_body
    assert "accent_color" in after_body[1] and "content-style.js" in after_body[3]
