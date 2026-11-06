from pathlib import Path
from typing import Any

from great_docs._website import appearance
from tests.support import write_config


def _texts(quarto_config: dict[str, Any], slot: str) -> list[str]:
    return [str(item) for item in quarto_config["format"]["html"].get(slot, [])]


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
