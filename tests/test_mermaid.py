# pyright: reportPrivateUsage=false

import base64
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from great_docs._mermaid import (
    encode_mermaid,
    encode_mermaid_simple,
    extract_mermaid_blocks,
    get_diagram_hash,
    process_qmd_mermaid,
    render_diagrams_for_page,
    render_mermaid_string,
    render_mermaid_to_png,
    render_mermaid_to_svg,
)


SIMPLE_DIAGRAM = "graph TD\n  A --> B"
FLOWCHART = "flowchart LR\n  Start --> Stop"


def test_encode_mermaid_base64():
    """Encoded output is valid base64."""
    result = encode_mermaid(SIMPLE_DIAGRAM)
    decoded = base64.urlsafe_b64decode(result)
    state = json.loads(decoded)
    assert state["code"] == SIMPLE_DIAGRAM
    assert state["mermaid"]["theme"] == "default"


def test_encode_mermaid_dark_theme():
    """Encoding with dark theme sets theme in config."""
    result = encode_mermaid(SIMPLE_DIAGRAM, theme="dark")
    decoded = base64.urlsafe_b64decode(result)
    state = json.loads(decoded)
    assert state["mermaid"]["theme"] == "dark"


def test_encode_mermaid_custom_theme():
    """Encoding with forest theme works."""
    result = encode_mermaid(SIMPLE_DIAGRAM, theme="forest")
    decoded = base64.urlsafe_b64decode(result)
    state = json.loads(decoded)
    assert state["mermaid"]["theme"] == "forest"


def test_encode_mermaid_simple_roundtrip():
    """Simple encoding round-trips correctly."""
    encoded = encode_mermaid_simple(SIMPLE_DIAGRAM)
    decoded = base64.urlsafe_b64decode(encoded).decode("utf-8")
    assert decoded == SIMPLE_DIAGRAM


def test_encode_mermaid_simple_returns_string():
    """Returns a string, not bytes."""
    result = encode_mermaid_simple(SIMPLE_DIAGRAM)
    assert isinstance(result, str)


def test_diagram_hash_12_char_hex():
    """Hash is a 12-char hex string."""
    result = get_diagram_hash(SIMPLE_DIAGRAM)
    assert len(result) == 12
    assert all(c in "0123456789abcdef" for c in result)


def test_diagram_hash_deterministic():
    """Same input produces same hash."""
    h1 = get_diagram_hash(SIMPLE_DIAGRAM)
    h2 = get_diagram_hash(SIMPLE_DIAGRAM)
    assert h1 == h2


def test_diagram_hash_different_inputs():
    """Different inputs produce different hashes."""
    h1 = get_diagram_hash(SIMPLE_DIAGRAM)
    h2 = get_diagram_hash(FLOWCHART)
    assert h1 != h2


def test_extract_curly_brace_syntax():
    """Extracts ```{mermaid} blocks."""
    content = "Some text\n```{mermaid}\ngraph TD\n  A --> B\n```\nMore text"
    blocks = extract_mermaid_blocks(content)
    assert len(blocks) == 1
    assert blocks[0][1] == "graph TD\n  A --> B"


def test_extract_plain_syntax():
    """Extracts ```mermaid blocks."""
    content = "Text\n```mermaid\nflowchart LR\n  X --> Y\n```\n"
    blocks = extract_mermaid_blocks(content)
    assert len(blocks) == 1
    assert blocks[0][1] == "flowchart LR\n  X --> Y"


def test_extract_multiple_blocks():
    """Extracts multiple mermaid blocks."""
    content = (
        "```{mermaid}\ngraph TD\n  A --> B\n```\nMiddle\n```mermaid\nflowchart LR\n  X --> Y\n```\n"
    )
    blocks = extract_mermaid_blocks(content)
    assert len(blocks) == 2


def test_extract_no_blocks():
    """Returns empty list when no mermaid blocks exist."""
    content = "# Just markdown\n\nNo diagrams here.\n```python\nprint('hi')\n```\n"
    blocks = extract_mermaid_blocks(content)
    assert blocks == []


def test_extract_positions_are_correct():
    """Start and end positions correspond to the match."""
    content = "prefix\n```{mermaid}\ngraph TD\n  A --> B\n```\nsuffix"
    blocks = extract_mermaid_blocks(content)
    full_match, _, start, end = blocks[0]
    assert content[start:end] == full_match


@patch("great_docs._mermaid.urllib.request.urlopen")
def test_render_png_default_theme(mock_urlopen):
    """Successful render returns PNG bytes."""
    mock_response = MagicMock()
    mock_response.read.return_value = b"\x89PNG fake data"
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_urlopen.return_value = mock_response

    result = render_mermaid_to_png(SIMPLE_DIAGRAM, theme="default")
    assert result == b"\x89PNG fake data"


@patch("great_docs._mermaid.urllib.request.urlopen")
def test_render_png_dark_theme(mock_urlopen):
    """Dark theme render uses dark bgColor."""
    mock_response = MagicMock()
    mock_response.read.return_value = b"\x89PNG dark"
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_urlopen.return_value = mock_response

    result = render_mermaid_to_png(SIMPLE_DIAGRAM, theme="dark")
    assert result == b"\x89PNG dark"

    # Verify URL uses dark theme
    call_args = mock_urlopen.call_args
    req = call_args[0][0]
    assert "theme=dark" in req.full_url
    assert "bgColor=!1f2937" in req.full_url


@patch("great_docs._mermaid.urllib.request.urlopen")
def test_render_png_url_error(mock_urlopen):
    """URLError returns None."""
    import urllib.error

    mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
    result = render_mermaid_to_png(SIMPLE_DIAGRAM)
    assert result is None


@patch("great_docs._mermaid.urllib.request.urlopen")
def test_render_png_timeout(mock_urlopen):
    """Timeout returns None."""
    mock_urlopen.side_effect = TimeoutError("Request timed out")
    result = render_mermaid_to_png(SIMPLE_DIAGRAM)
    assert result is None


@patch("great_docs._mermaid.urllib.request.urlopen")
def test_render_svg_success(mock_urlopen):
    """Successful render returns SVG string."""
    svg = "<svg><text>diagram</text></svg>"
    mock_response = MagicMock()
    mock_response.read.return_value = svg.encode("utf-8")
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_urlopen.return_value = mock_response

    result = render_mermaid_to_svg(SIMPLE_DIAGRAM)
    assert result == svg


@patch("great_docs._mermaid.urllib.request.urlopen")
def test_render_svg_error(mock_urlopen):
    """Network error returns None."""
    import urllib.error

    mock_urlopen.side_effect = urllib.error.URLError("fail")
    result = render_mermaid_to_svg(SIMPLE_DIAGRAM)
    assert result is None


def test_render_page_no_mermaid_blocks():
    """Returns empty dict when no mermaid blocks in file."""
    with tempfile.TemporaryDirectory() as tmp:
        qmd = Path(tmp) / "test.qmd"
        qmd.write_text("# No diagrams\n\nPlain text.\n")
        output = Path(tmp) / "output"
        result = render_diagrams_for_page(qmd, output)
        assert result == {}


@patch("great_docs._mermaid.render_mermaid_to_png")
def test_render_page_light_and_dark(mock_render):
    """Renders both light and dark PNGs."""
    mock_render.side_effect = [b"light-png", b"dark-png"]

    with tempfile.TemporaryDirectory() as tmp:
        qmd = Path(tmp) / "test.qmd"
        qmd.write_text("```{mermaid}\ngraph TD\n  A --> B\n```\n")
        output = Path(tmp) / "output"

        result = render_diagrams_for_page(qmd, output)
        assert len(result) == 1
        diagram_hash = list(result.keys())[0]
        light_path, dark_path = result[diagram_hash]
        assert light_path.exists()
        assert dark_path.exists()
        assert light_path.read_bytes() == b"light-png"
        assert dark_path.read_bytes() == b"dark-png"


@patch("great_docs._mermaid.render_mermaid_to_png")
def test_render_page_failure_skips(mock_render):
    """When rendering fails, diagram is not in results."""
    mock_render.return_value = None

    with tempfile.TemporaryDirectory() as tmp:
        qmd = Path(tmp) / "test.qmd"
        qmd.write_text("```{mermaid}\ngraph TD\n  A --> B\n```\n")
        output = Path(tmp) / "output"

        result = render_diagrams_for_page(qmd, output)
        assert result == {}


@patch("great_docs._mermaid.render_mermaid_to_png")
def test_render_page_cache_hit(mock_render):
    """Cached diagrams are loaded from cache dir without rendering."""
    with tempfile.TemporaryDirectory() as tmp:
        qmd = Path(tmp) / "test.qmd"
        qmd.write_text("```{mermaid}\ngraph TD\n  A --> B\n```\n")
        output = Path(tmp) / "output"
        cache = Path(tmp) / "cache"
        cache.mkdir()

        # Pre-populate cache
        diagram_hash = get_diagram_hash("graph TD\n  A --> B")
        (cache / f"mermaid-{diagram_hash}-light.png").write_bytes(b"cached-light")
        (cache / f"mermaid-{diagram_hash}-dark.png").write_bytes(b"cached-dark")

        result = render_diagrams_for_page(qmd, output, cache_dir=cache)
        assert len(result) == 1
        light_path, dark_path = result[diagram_hash]
        assert light_path.read_bytes() == b"cached-light"
        assert dark_path.read_bytes() == b"cached-dark"

        # Should NOT have called the render function
        mock_render.assert_not_called()


def test_process_qmd_no_blocks():
    """Content without mermaid blocks is returned unchanged."""
    with tempfile.TemporaryDirectory() as tmp:
        qmd = Path(tmp) / "test.qmd"
        content = "# Title\n\nJust text.\n"
        qmd.write_text(content)
        output = Path(tmp) / "output"

        result = process_qmd_mermaid(qmd, output)
        assert result == content


@patch("great_docs._mermaid.render_mermaid_to_png")
def test_process_qmd_replaces_block(mock_render):
    """Mermaid block is replaced with theme-aware image HTML."""
    mock_render.side_effect = [b"light-data", b"dark-data"]

    with tempfile.TemporaryDirectory() as tmp:
        qmd = Path(tmp) / "test.qmd"
        qmd.write_text("Before\n```{mermaid}\ngraph TD\n  A --> B\n```\nAfter\n")
        output = Path(tmp) / "output"

        result = process_qmd_mermaid(qmd, output)
        assert "Before" in result
        assert "After" in result
        assert "mermaid-diagram" in result
        assert "mermaid-light" in result
        assert "mermaid-dark" in result
        assert "```{mermaid}" not in result


@patch("great_docs._mermaid.render_mermaid_to_png")
def test_process_qmd_failure_keeps_original(mock_render):
    """When rendering fails, original mermaid block is preserved."""
    mock_render.return_value = None

    with tempfile.TemporaryDirectory() as tmp:
        qmd = Path(tmp) / "test.qmd"
        original = "Before\n```{mermaid}\ngraph TD\n  A --> B\n```\nAfter\n"
        qmd.write_text(original)
        output = Path(tmp) / "output"

        result = process_qmd_mermaid(qmd, output)
        assert "```{mermaid}" in result


@patch("great_docs._mermaid.render_mermaid_to_png")
def test_process_qmd_cache_write(mock_render):
    """Rendered diagrams are saved to cache."""
    mock_render.side_effect = [b"light", b"dark"]

    with tempfile.TemporaryDirectory() as tmp:
        qmd = Path(tmp) / "test.qmd"
        qmd.write_text("```{mermaid}\ngraph TD\n  A --> B\n```\n")
        output = Path(tmp) / "output"
        cache = Path(tmp) / "cache"

        process_qmd_mermaid(qmd, output, cache_dir=cache)

        diagram_hash = get_diagram_hash("graph TD\n  A --> B")
        assert (cache / f"mermaid-{diagram_hash}-light.png").exists()
        assert (cache / f"mermaid-{diagram_hash}-dark.png").exists()


@patch("great_docs._mermaid.render_mermaid_to_png")
def test_process_qmd_cache_read(mock_render):
    """Cached diagrams are used without re-rendering."""
    with tempfile.TemporaryDirectory() as tmp:
        qmd = Path(tmp) / "test.qmd"
        qmd.write_text("```{mermaid}\ngraph TD\n  A --> B\n```\n")
        output = Path(tmp) / "output"
        cache = Path(tmp) / "cache"
        cache.mkdir()

        # Pre-populate cache
        diagram_hash = get_diagram_hash("graph TD\n  A --> B")
        (cache / f"mermaid-{diagram_hash}-light.png").write_bytes(b"c-light")
        (cache / f"mermaid-{diagram_hash}-dark.png").write_bytes(b"c-dark")

        result = process_qmd_mermaid(qmd, output, cache_dir=cache)
        assert "mermaid-diagram" in result
        mock_render.assert_not_called()


@patch("great_docs._mermaid.render_mermaid_to_png")
def test_process_qmd_multiple_blocks(mock_render):
    """Multiple mermaid blocks are all processed."""
    mock_render.side_effect = [b"l1", b"d1", b"l2", b"d2"]

    with tempfile.TemporaryDirectory() as tmp:
        qmd = Path(tmp) / "test.qmd"
        qmd.write_text(
            "```{mermaid}\ngraph TD\n  A --> B\n```\n"
            "\nMiddle\n\n"
            "```mermaid\nflowchart LR\n  X --> Y\n```\n"
        )
        output = Path(tmp) / "output"

        result = process_qmd_mermaid(qmd, output)
        assert result.count("mermaid-diagram") == 2


@patch("great_docs._mermaid.render_mermaid_to_svg")
def test_render_string_success(mock_svg):
    """Successful render writes SVG and returns True."""
    mock_svg.return_value = "<svg>ok</svg>"

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "sub" / "diagram.svg"
        result = render_mermaid_string(SIMPLE_DIAGRAM, out)
        assert result is True
        assert out.exists()
        assert out.read_text() == "<svg>ok</svg>"


@patch("great_docs._mermaid.render_mermaid_to_svg")
def test_render_string_failure(mock_svg):
    """Failed render returns False and doesn't create file."""
    mock_svg.return_value = None

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "diagram.svg"
        result = render_mermaid_string(SIMPLE_DIAGRAM, out)
        assert result is False
        assert not out.exists()
