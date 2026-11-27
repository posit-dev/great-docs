"""Tests for the switcher that `reference-switcher.js` builds, run with Node in a stub page."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "great_docs" / "assets" / "reference-switcher.js"
HARNESS = ROOT / "tests" / "js" / "reference_switcher_harness.js"

# The upper snake's eye, a path drawn only in the Python logo
_PYTHON_EYE = 'd="M11 6l0 .01"'


def _switcher(sections: str, pathname: str = "/reference/index.html") -> str:
    completed = subprocess.run(
        [
            "node",
            str(HARNESS),
            str(SCRIPT),
            json.dumps({"sections": sections, "pathname": pathname}),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    html = json.loads(completed.stdout)["html"]
    assert html is not None
    return html


def _icons(html: str) -> list[str]:
    """The class of each `i.bi` icon, followed by `+svg` when it holds an inline icon."""
    return [
        cls + ("+svg" if inner.startswith("<svg") else "")
        for cls, inner in re.findall(r'<i class="([^"]*)">(.*?)</i>', html)
    ]


def _labels(html: str) -> list[str]:
    """The text after each icon."""
    return re.findall(r"</i><span[^>]*>([^<]*)</span>", html)


def test_segmented_buttons_show_the_python_logo_and_a_plug():
    html = _switcher("api,mcp")
    assert _icons(html) == ["bi gd-ref-svg-icon+svg", "bi bi-plug"]
    assert _labels(html) == ["Python", "MCP"]
    assert html.count(_PYTHON_EYE) == 1


def test_dropdown_shows_the_current_section_and_each_section_with_their_icons():
    html = _switcher("api,cli,mcp", "/reference/cli/index.html")
    assert _icons(html) == [
        "bi bi-terminal",
        "bi gd-ref-svg-icon+svg",
        "bi bi-terminal",
        "bi bi-plug",
    ]
    assert _labels(html) == ["CLI", "Python", "CLI", "MCP"]


def test_dropdown_toggle_shows_the_python_logo_on_the_api_reference():
    html = _switcher("api,cli,mcp")
    assert _icons(html)[0] == "bi gd-ref-svg-icon+svg"
    assert html.count(_PYTHON_EYE) == 2


def test_python_logo_is_decorative_and_takes_the_text_colour():
    svg = re.search(r"<svg[^>]*>", _switcher("api,cli")).group(0)
    assert 'aria-hidden="true"' in svg
    assert 'stroke="currentColor"' in svg
    assert 'width="1em" height="1em"' in svg
