# pyright: reportPrivateUsage=false

import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from great_docs._website.d2 import (
    DEFAULT_DARK_THEME,
    DEFAULT_LIGHT_THEME,
    _build_d2_args,
    _ensure_svg_dimensions,
    _resolve_themes,
    d2_available,
    extract_d2_blocks,
    get_diagram_hash,
    parse_d2_block,
    process_d2_content,
    process_directory,
    process_qmd_file,
    render_d2_svg,
)

SIMPLE_DIAGRAM = "a -> b\nb -> c"
LIGHT_SVG = "<svg>light</svg>"
DARK_SVG = "<svg>dark</svg>"


def _ok(output: str) -> MagicMock:
    """A subprocess result that succeeded with *output* on stdout."""
    result = MagicMock()
    result.returncode = 0
    result.stdout = output.encode("utf-8")
    result.stderr = b""
    return result


# --------------------------------------------------------------------------- #
# Availability
# --------------------------------------------------------------------------- #
def test_d2_available_true():
    with patch("great_docs._website.d2.shutil.which", return_value="/usr/bin/d2"):
        assert d2_available() is True


def test_d2_available_false():
    with patch("great_docs._website.d2.shutil.which", return_value=None):
        assert d2_available() is False


# --------------------------------------------------------------------------- #
# Block extraction
# --------------------------------------------------------------------------- #
def test_extract_quarto_fence():
    content = "# T\n\n```{d2}\na -> b\n```\n"
    blocks = extract_d2_blocks(content)
    assert len(blocks) == 1
    assert blocks[0][1] == "a -> b"


def test_extract_plain_fence():
    content = "```d2\nx -> y\n```"
    blocks = extract_d2_blocks(content)
    assert len(blocks) == 1
    assert blocks[0][1] == "x -> y"


def test_extract_dot_fence():
    content = "```{.d2}\nx -> y\n```"
    blocks = extract_d2_blocks(content)
    assert len(blocks) == 1
    assert blocks[0][1] == "x -> y"


def test_extract_multiple_blocks():
    content = "```d2\na -> b\n```\n\ntext\n\n```{d2}\nc -> d\n```"
    blocks = extract_d2_blocks(content)
    assert len(blocks) == 2
    # Positions are ordered and non-overlapping.
    assert blocks[0][2] < blocks[1][2]


def test_extract_none():
    assert extract_d2_blocks("no diagrams here") == []


def test_extract_does_not_match_mermaid():
    content = "```{mermaid}\ngraph TD\n  A --> B\n```"
    assert extract_d2_blocks(content) == []


def test_extract_ignores_inline_fence_in_prose():
    # An inline `` ```d2 `` mention mid-sentence must NOT be treated as a fence,
    # and must not swallow a real fenced block that follows it.
    content = (
        "The plain ```` ```d2 ```` fence is also recognized:\n\nx -> y block below:\n\n"
        "```d2\nx -> y -> z\n```\n"
    )
    blocks = extract_d2_blocks(content)
    assert len(blocks) == 1
    assert blocks[0][1] == "x -> y -> z"


def test_extract_indented_fence():
    content = "  ```{d2}\n  a -> b\n  ```"
    blocks = extract_d2_blocks(content)
    assert len(blocks) == 1
    assert "a -> b" in blocks[0][1]


def test_extract_ignores_d2_nested_in_display_fence():
    # A ````markdown display fence SHOWS d2 syntax literally; the inner ```{d2}
    # must NOT be rendered. Only the real top-level block below it should match.
    content = (
        "````markdown\n"
        "```{d2}\n"
        "Start -> Decision\n"
        "```\n"
        "````\n"
        "\n"
        "Real diagram:\n"
        "\n"
        "```{d2}\n"
        "a -> b\n"
        "```\n"
    )
    blocks = extract_d2_blocks(content)
    assert len(blocks) == 1, "only the real top-level block should match"
    assert blocks[0][1] == "a -> b"


def test_extract_unterminated_fence_ignored():
    # An opening fence with no closing fence is not rendered.
    content = "```{d2}\na -> b\nno closing fence here\n"
    assert extract_d2_blocks(content) == []


# --------------------------------------------------------------------------- #
# Option parsing
# --------------------------------------------------------------------------- #
def test_parse_block_options_stripped():
    block = "#| theme: 4\n#| layout: elk\na -> b"
    source, options = parse_d2_block(block)
    assert source == "a -> b"
    assert options == {"theme": "4", "layout": "elk"}


def test_parse_block_unknown_option_dropped():
    block = "#| bogus: 1\n#| pad: 40\na -> b"
    source, options = parse_d2_block(block)
    assert "bogus" not in options
    assert options == {"pad": "40"}
    assert source == "a -> b"


def test_parse_block_no_options():
    source, options = parse_d2_block("a -> b\nb -> c")
    assert source == "a -> b\nb -> c"
    assert options == {}


def test_parse_block_hash_line_without_colon_dropped():
    # A `#|` directive with no colon is not an option and is stripped from source.
    source, options = parse_d2_block("#| just a comment\na -> b")
    assert source == "a -> b"
    assert options == {}


# --------------------------------------------------------------------------- #
# Hashing
# --------------------------------------------------------------------------- #
def test_hash_stable():
    assert get_diagram_hash("a -> b", {}) == get_diagram_hash("a -> b", {})


def test_hash_changes_with_options():
    assert get_diagram_hash("a -> b", {}) != get_diagram_hash("a -> b", {"theme": "4"})


def test_hash_changes_with_source():
    assert get_diagram_hash("a -> b", {}) != get_diagram_hash("a -> c", {})


# --------------------------------------------------------------------------- #
# Theme resolution
# --------------------------------------------------------------------------- #
def test_resolve_themes_defaults():
    assert _resolve_themes({}) == (DEFAULT_LIGHT_THEME, DEFAULT_DARK_THEME)


def test_resolve_themes_overrides():
    assert _resolve_themes({"theme": "4", "dark-theme": "201"}) == (4, 201)


def test_resolve_themes_invalid_falls_back():
    assert _resolve_themes({"theme": "nope"}) == (DEFAULT_LIGHT_THEME, DEFAULT_DARK_THEME)


# --------------------------------------------------------------------------- #
# Arg building
# --------------------------------------------------------------------------- #
def test_build_args_defaults():
    args = _build_d2_args(0, {})
    assert args[:3] == ["d2", "--theme", "0"]
    assert "--pad" in args
    assert args[-2:] == ["-", "-"]


def test_build_args_all_options():
    args = _build_d2_args(200, {"pad": "40", "layout": "elk", "scale": "1.5", "sketch": "true"})
    assert "--layout" in args and "elk" in args
    assert "--scale" in args and "1.5" in args
    assert "--sketch" in args
    assert args[args.index("--pad") + 1] == "40"


def test_build_args_sketch_false():
    args = _build_d2_args(0, {"sketch": "false"})
    assert "--sketch" not in args


# --------------------------------------------------------------------------- #
# SVG dimension backfill
# --------------------------------------------------------------------------- #
def test_ensure_dimensions_adds_width_height():
    svg = '<svg xmlns="x" viewBox="0 0 425 621"><rect/></svg>'
    fixed = _ensure_svg_dimensions(svg)
    assert 'width="425"' in fixed
    assert 'height="621"' in fixed


def test_ensure_dimensions_noop_when_width_present():
    svg = '<svg width="100" height="50" viewBox="0 0 100 50"></svg>'
    assert _ensure_svg_dimensions(svg) == svg


def test_ensure_dimensions_noop_without_viewbox():
    svg = '<svg xmlns="x"></svg>'
    assert _ensure_svg_dimensions(svg) == svg


def test_ensure_dimensions_noop_without_svg_tag():
    # No <svg> tag at all: returned unchanged.
    text = "<div>not an svg</div>"
    assert _ensure_svg_dimensions(text) == text


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def test_render_success():
    svg_out = '<svg viewBox="0 0 10 20"></svg>'
    with patch("great_docs._website.d2.subprocess.run", return_value=_ok(svg_out)) as run:
        svg = render_d2_svg("a -> b", 0)
        # Dimensions are backfilled from the viewBox.
        assert 'width="10"' in svg and 'height="20"' in svg
        # Diagram is fed via stdin.
        assert run.call_args.kwargs["input"] == b"a -> b"


def test_render_nonzero_returncode():
    bad = MagicMock()
    bad.returncode = 1
    bad.stdout = b""
    bad.stderr = b"syntax error"
    with patch("great_docs._website.d2.subprocess.run", return_value=bad):
        assert render_d2_svg("a -> b", 0) is None


def test_render_subprocess_error():
    with patch("great_docs._website.d2.subprocess.run", side_effect=OSError("boom")):
        assert render_d2_svg("a -> b", 0) is None


def test_render_timeout():
    with patch(
        "great_docs._website.d2.subprocess.run",
        side_effect=subprocess.TimeoutExpired("d2", 30),
    ):
        assert render_d2_svg("a -> b", 0) is None


# --------------------------------------------------------------------------- #
# Content processing
# --------------------------------------------------------------------------- #
def _render_side_effect(diagram, theme, options=None, timeout=30):
    return LIGHT_SVG if theme == DEFAULT_LIGHT_THEME else DARK_SVG


def test_process_content_renders_and_writes():
    content = "# T\n\n```{d2}\na -> b\n```\n"
    out_dir = Path(tempfile.mkdtemp())
    with patch("great_docs._website.d2.render_d2_svg", side_effect=_render_side_effect):
        new, n = process_d2_content(content, out_dir)
    assert n == 1
    assert "```{d2}" not in new
    assert ".d2-diagram" in new
    assert ".light-mode-only" in new and ".dark-mode-only" in new
    svgs = sorted(p.name for p in out_dir.glob("*.svg"))
    assert len(svgs) == 2
    assert any("-light.svg" in s for s in svgs)
    assert any("-dark.svg" in s for s in svgs)


def test_process_content_no_blocks():
    new, n = process_d2_content("just prose", Path(tempfile.mkdtemp()))
    assert n == 0
    assert new == "just prose"


def test_process_content_empty_source_block_kept():
    # A d2 block with only options (no diagram source) renders nothing and is
    # left untouched; the renderer is never invoked.
    content = "```{d2}\n#| pad: 10\n```"
    with patch("great_docs._website.d2.render_d2_svg") as run:
        new, n = process_d2_content(content, Path(tempfile.mkdtemp()))
        run.assert_not_called()
    assert n == 0
    assert new == content


def test_process_content_render_failure_keeps_block():
    content = "```{d2}\na -> b\n```"
    with patch("great_docs._website.d2.render_d2_svg", return_value=None):
        new, n = process_d2_content(content, Path(tempfile.mkdtemp()))
    assert n == 0
    assert new == content  # original block preserved


def test_process_content_uses_cache():
    content = "```{d2}\na -> b\n```"
    out_dir = Path(tempfile.mkdtemp())
    cache_dir = Path(tempfile.mkdtemp())

    # First pass renders and populates the cache.
    with patch("great_docs._website.d2.render_d2_svg", side_effect=_render_side_effect) as run:
        process_d2_content(content, out_dir, cache_dir)
        assert run.call_count == 2

    # Second pass should hit the cache and not call the renderer.
    out_dir2 = Path(tempfile.mkdtemp())
    with patch("great_docs._website.d2.render_d2_svg", side_effect=_render_side_effect) as run:
        _, n = process_d2_content(content, out_dir2, cache_dir)
        assert n == 1
        run.assert_not_called()
    assert len(list(out_dir2.glob("*.svg"))) == 2


# --------------------------------------------------------------------------- #
# File / directory processing
# --------------------------------------------------------------------------- #
def test_process_qmd_file_modifies():
    d = Path(tempfile.mkdtemp())
    qmd = d / "page.qmd"
    qmd.write_text("```{d2}\na -> b\n```", encoding="utf-8")
    with patch("great_docs._website.d2.render_d2_svg", side_effect=_render_side_effect):
        assert process_qmd_file(qmd) is True
    assert "```{d2}" not in qmd.read_text(encoding="utf-8")


def test_process_qmd_file_no_d2_early_out():
    d = Path(tempfile.mkdtemp())
    qmd = d / "page.qmd"
    qmd.write_text("# Just prose, no diagrams", encoding="utf-8")
    with patch("great_docs._website.d2.render_d2_svg") as run:
        assert process_qmd_file(qmd) is False
        run.assert_not_called()


def test_process_qmd_file_d2_substring_but_no_block():
    # "d2" appears in prose (passing the cheap early-out) but there is no d2
    # block, so nothing is rendered and the file is reported unmodified.
    d = Path(tempfile.mkdtemp())
    qmd = d / "page.qmd"
    original = "This page mentions d2 but has no diagram block."
    qmd.write_text(original, encoding="utf-8")
    assert process_qmd_file(qmd) is False
    assert qmd.read_text(encoding="utf-8") == original


def test_process_directory_skips_when_d2_unavailable():
    d = Path(tempfile.mkdtemp())
    (d / "page.qmd").write_text("```{d2}\na -> b\n```", encoding="utf-8")
    with patch("great_docs._website.d2.d2_available", return_value=False):
        assert process_directory(d) == []
    # File is untouched.
    assert "```{d2}" in (d / "page.qmd").read_text(encoding="utf-8")


def test_process_directory_unavailable_no_blocks_no_warning():
    # d2 unavailable, but no page contains a d2 block: the warning scan runs to
    # completion without breaking and returns an empty list.
    d = Path(tempfile.mkdtemp())
    (d / "page.qmd").write_text("# Prose only, no diagrams", encoding="utf-8")
    with patch("great_docs._website.d2.d2_available", return_value=False):
        assert process_directory(d) == []


def test_process_directory_renders():
    d = Path(tempfile.mkdtemp())
    (d / "a.qmd").write_text("```{d2}\na -> b\n```", encoding="utf-8")
    (d / "b.qmd").write_text("no diagrams", encoding="utf-8")
    with (
        patch("great_docs._website.d2.d2_available", return_value=True),
        patch("great_docs._website.d2.render_d2_svg", side_effect=_render_side_effect),
    ):
        modified = process_directory(d)
    assert modified == ["a.qmd"]


def test_process_directory_reports_nested_pages_relative_to_directory(tmp_path):
    (tmp_path / "guide").mkdir()
    (tmp_path / "guide" / "c.qmd").write_text("```{d2}\na -> b\n```", encoding="utf-8")
    with (
        patch("great_docs._website.d2.d2_available", return_value=True),
        patch("great_docs._website.d2.render_d2_svg", side_effect=_render_side_effect),
    ):
        modified = process_directory(tmp_path)
    assert modified == [str(Path("guide") / "c.qmd")]


# --------------------------------------------------------------------------- #
# Integration: exercise the real `d2` binary (skipped when it is not installed).
# Guards against d2 CLI/API drift that the mocked tests above cannot catch.
# CI installs d2, so this runs there; local runs without d2 simply skip it.
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(shutil.which("d2") is None, reason="d2 CLI not installed")
def test_real_d2_render_end_to_end(tmp_path):
    # The real binary produces a valid SVG with backfilled dimensions.
    svg = render_d2_svg("a -> b\nb -> c", DEFAULT_LIGHT_THEME)

    assert svg is not None
    assert "<svg" in svg
    assert "width=" in svg and "height=" in svg

    # End to end: a d2 block becomes a themed diagram with two SVG files.
    content = "# Title\n\n```{d2}\na -> b\n```\n"
    new, n = process_d2_content(content, tmp_path)

    assert n == 1
    assert ".d2-diagram" in new

    svgs = sorted(p.name for p in tmp_path.glob("*.svg"))

    assert len(svgs) == 2
    assert any(s.endswith("-light.svg") for s in svgs)
    assert any(s.endswith("-dark.svg") for s in svgs)
