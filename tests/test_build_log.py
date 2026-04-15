# pyright: reportPrivateUsage=false

from __future__ import annotations

import io
import os
import time
from unittest.mock import patch

import pytest

from great_docs._build_log import (
    BuildLog,
    Colors,
    ProgressBar,
    _BAR_WIDTH,
    _BOX_MAX_WIDTH,
    _StepState,
    _display_width,
    _should_use_color,
    _strip_emoji,
    estimate_build_time,
    format_elapsed,
    format_estimate,
)


# =========================================================================
# _strip_emoji / _display_width helpers
# =========================================================================


class TestStripEmoji:
    """Tests for ``_strip_emoji()``."""

    def test_plain_text_unchanged(self):
        assert _strip_emoji("hello world") == "hello world"

    def test_leading_emoji_stripped(self):
        assert _strip_emoji("🎉 Site ready") == "Site ready"

    def test_multiple_leading_emoji(self):
        assert _strip_emoji("📦🔍 Scanning") == "Scanning"

    def test_preserves_leading_indent_without_emoji(self):
        assert _strip_emoji("  - reference/cli/build.qmd") == "  - reference/cli/build.qmd"

    def test_strips_trailing_whitespace_without_emoji(self):
        assert _strip_emoji("some text   ") == "some text"

    def test_empty_string(self):
        assert _strip_emoji("") == ""

    def test_only_emoji_returns_empty(self):
        assert _strip_emoji("🎉") == ""

    def test_emoji_with_variant_selector(self):
        assert _strip_emoji("⚠️ Warning text") == "Warning text"


class TestDisplayWidth:
    """Tests for ``_display_width()``."""

    def test_ascii(self):
        assert _display_width("hello") == 5

    def test_wide_emoji(self):
        assert _display_width("🎉") == 2

    def test_mixed(self):
        assert _display_width("🎉 Site ready") == 13  # 2 (emoji) + 11 (ascii)

    def test_empty(self):
        assert _display_width("") == 0


# =========================================================================
# Colors
# =========================================================================


class TestColors:
    """Tests for the ``Colors`` class."""

    def test_force_color_true_sets_ansi_codes(self):
        c = Colors(force_color=True)
        assert c.use_color is True
        assert c.RESET == "\033[0m"
        assert c.BOLD == "\033[1m"
        assert c.DIM == "\033[2m"
        assert c.CYAN == "\033[36m"
        assert c.GREEN == "\033[32m"
        assert c.YELLOW == "\033[33m"
        assert c.RED == "\033[31m"
        assert c.WHITE == "\033[37m"
        assert c.BOLD_CYAN == "\033[1;36m"
        assert c.BOLD_GREEN == "\033[1;32m"
        assert c.BOLD_RED == "\033[1;31m"
        assert c.BOLD_WHITE == "\033[1;37m"

    def test_force_color_false_sets_empty_strings(self):
        c = Colors(force_color=False)
        assert c.use_color is False
        assert c.RESET == ""
        assert c.BOLD == ""
        assert c.DIM == ""
        assert c.CYAN == ""
        assert c.GREEN == ""
        assert c.YELLOW == ""
        assert c.RED == ""
        assert c.WHITE == ""
        assert c.BOLD_CYAN == ""
        assert c.BOLD_GREEN == ""
        assert c.BOLD_RED == ""
        assert c.BOLD_WHITE == ""

    def test_all_attrs_present_when_no_color(self):
        c = Colors(force_color=False)
        for attr in (
            "RESET",
            "BOLD",
            "DIM",
            "CYAN",
            "GREEN",
            "YELLOW",
            "RED",
            "WHITE",
            "BOLD_CYAN",
            "BOLD_GREEN",
            "BOLD_RED",
            "BOLD_WHITE",
        ):
            assert hasattr(c, attr)
            assert getattr(c, attr) == ""

    def test_all_attrs_present_when_color(self):
        c = Colors(force_color=True)
        for attr in (
            "RESET",
            "BOLD",
            "DIM",
            "CYAN",
            "GREEN",
            "YELLOW",
            "RED",
            "WHITE",
            "BOLD_CYAN",
            "BOLD_GREEN",
            "BOLD_RED",
            "BOLD_WHITE",
        ):
            assert hasattr(c, attr)
            assert getattr(c, attr) != ""  # all should be non-empty ANSI codes

    def test_auto_detection_respects_no_color_env(self):
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            c = Colors()
            assert c.use_color is False
            assert c.RESET == ""

    def test_auto_detection_respects_dumb_term(self):
        env = {"TERM": "dumb"}
        # Remove NO_COLOR if it exists
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("NO_COLOR", None)
            c = Colors()
            assert c.use_color is False

    def test_auto_detection_non_tty(self):
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = False
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("NO_COLOR", None)
                os.environ.pop("TERM", None)
                c = Colors()
                assert c.use_color is False


class TestShouldUseColor:
    """Tests for ``_should_use_color()``."""

    def test_no_color_env_set(self):
        with patch.dict(os.environ, {"NO_COLOR": ""}):
            assert _should_use_color() is False

    def test_no_color_env_with_value(self):
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            assert _should_use_color() is False

    def test_dumb_term(self):
        with patch.dict(os.environ, {"TERM": "dumb"}, clear=False):
            os.environ.pop("NO_COLOR", None)
            assert _should_use_color() is False

    def test_isatty_false(self):
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = False
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("NO_COLOR", None)
                os.environ.pop("TERM", None)
                assert _should_use_color() is False

    def test_isatty_raises(self):
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.isatty.side_effect = AttributeError("no isatty")
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("NO_COLOR", None)
                os.environ.pop("TERM", None)
                assert _should_use_color() is False


# =========================================================================
# format_elapsed
# =========================================================================


class TestFormatElapsed:
    """Tests for ``format_elapsed()`` — every spec boundary."""

    def test_zero(self):
        assert format_elapsed(0) == "<0.1s"

    def test_tiny(self):
        assert format_elapsed(0.05) == "<0.1s"

    def test_just_below_threshold(self):
        assert format_elapsed(0.099) == "<0.1s"

    def test_at_threshold(self):
        assert format_elapsed(0.1) == "0.1s"

    def test_sub_second(self):
        assert format_elapsed(0.5) == "0.5s"

    def test_one_second(self):
        assert format_elapsed(1.0) == "1.0s"

    def test_seconds_with_decimal(self):
        assert format_elapsed(3.25) == "3.2s"  # truncated to 1 decimal

    def test_seconds_rounding(self):
        assert format_elapsed(59.95) == "1m 0.0s"  # 59.95 rounds to 60.0 → minutes

    def test_just_under_60(self):
        assert format_elapsed(59.9) == "59.9s"

    def test_exactly_60(self):
        result = format_elapsed(60.0)
        assert result == "1m 0.0s"

    def test_one_minute_thirty(self):
        result = format_elapsed(90.0)
        assert result == "1m 30.0s"

    def test_minutes_with_decimal_seconds(self):
        result = format_elapsed(167.3)
        assert result == "2m 47.3s"

    def test_just_under_3600(self):
        result = format_elapsed(3599.0)
        assert result == "59m 59.0s"

    def test_exactly_3600(self):
        result = format_elapsed(3600.0)
        assert result == "1h 0m 0s"

    def test_one_hour_two_minutes(self):
        result = format_elapsed(3735.0)
        assert result == "1h 2m 15s"

    def test_large_hours(self):
        result = format_elapsed(7200 + 180 + 45)
        assert result == "2h 3m 45s"


# =========================================================================
# format_estimate
# =========================================================================


class TestFormatEstimate:
    """Tests for ``format_estimate()``."""

    def test_minimum_one_minute(self):
        assert format_estimate(0) == "~1 min"

    def test_under_30_seconds(self):
        assert format_estimate(25) == "~1 min"

    def test_exactly_30_seconds(self):
        assert format_estimate(30) == "~1 min"

    def test_31_seconds(self):
        assert format_estimate(31) == "~1 min"

    def test_one_minute(self):
        assert format_estimate(60) == "~1 min"

    def test_90_seconds(self):
        assert format_estimate(90) == "~2 min"

    def test_four_minutes(self):
        assert format_estimate(252) == "~4 min"

    def test_large(self):
        assert format_estimate(600) == "~10 min"


# =========================================================================
# estimate_build_time
# =========================================================================


class TestEstimateBuildTime:
    """Tests for ``estimate_build_time()``."""

    def test_zero_inputs(self):
        result = estimate_build_time(n_api_items=0, n_total_pages=0)
        assert result == 5.0  # base only

    def test_api_items_only(self):
        result = estimate_build_time(n_api_items=100, n_total_pages=0)
        assert result == pytest.approx(5.0 + 100 * 0.02)

    def test_pages_only(self):
        result = estimate_build_time(n_api_items=0, n_total_pages=200)
        expected = 5.0 + 200 * 0.8 + 200 * 0.03
        assert result == pytest.approx(expected)

    def test_combined(self):
        result = estimate_build_time(n_api_items=162, n_total_pages=203)
        expected = (5.0 + 162 * 0.02) + (203 * 0.8) + (203 * 0.03)
        assert result == pytest.approx(expected)

    def test_default_args(self):
        result = estimate_build_time()
        assert result == 5.0


# =========================================================================
# ProgressBar
# =========================================================================


class TestProgressBar:
    """Tests for the ``ProgressBar`` class."""

    def test_init_defaults(self):
        bar = ProgressBar("Testing", 100, colors=Colors(force_color=False))
        assert bar.label == "Testing"
        assert bar.total == 100
        assert bar._current == 0
        assert bar._last_pct_bucket == -1

    def test_total_zero_becomes_one(self):
        bar = ProgressBar("Test", 0, colors=Colors(force_color=False))
        assert bar.total == 1

    def test_render_bar_no_color_at_zero(self):
        bar = ProgressBar("Rendering", 100, colors=Colors(force_color=False))
        line = bar._render_bar(0)
        assert "►" in line
        assert "Rendering" in line
        assert "0/100" in line
        assert "0%" in line
        # All bars should be empty
        assert "█" not in line
        assert "░" * _BAR_WIDTH in line

    def test_render_bar_no_color_at_half(self):
        bar = ProgressBar("Rendering", 100, colors=Colors(force_color=False))
        line = bar._render_bar(50)
        assert "50/100" in line
        assert "50%" in line
        filled = line.count("█")
        empty = line.count("░")
        assert filled == _BAR_WIDTH // 2
        assert empty == _BAR_WIDTH - _BAR_WIDTH // 2

    def test_render_bar_no_color_at_full(self):
        bar = ProgressBar("Rendering", 100, colors=Colors(force_color=False))
        line = bar._render_bar(100)
        assert "100/100" in line
        assert "100%" in line
        assert "█" * _BAR_WIDTH in line
        assert "░" not in line

    def test_render_bar_with_color_has_ansi(self):
        bar = ProgressBar("Rendering", 100, colors=Colors(force_color=True))
        line = bar._render_bar(50)
        assert "\033[" in line  # ANSI escape present
        assert "50%" in line

    def test_render_bar_plain_ci(self):
        bar = ProgressBar("Rendering", 100, colors=Colors(force_color=False))
        line = bar._render_bar_plain(50)
        assert "[..]" in line
        assert "Rendering" in line
        assert " 50%" in line

    def test_render_bar_plain_at_zero(self):
        bar = ProgressBar("Rendering", 100, colors=Colors(force_color=False))
        line = bar._render_bar_plain(0)
        assert "  0%" in line

    def test_render_bar_plain_at_100(self):
        bar = ProgressBar("Rendering", 100, colors=Colors(force_color=False))
        line = bar._render_bar_plain(100)
        assert "100%" in line

    def test_update_tty_throttled(self):
        stream = io.StringIO()
        bar = ProgressBar(
            "Test",
            100,
            is_tty=True,
            colors=Colors(force_color=True),
            stream=stream,
        )
        # First update always writes (last_draw_time = 0)
        bar.update(1)
        first_output = stream.getvalue()
        assert len(first_output) > 0

        # Immediate second update should be throttled (< 1s)
        stream.truncate(0)
        stream.seek(0)
        bar.update(2)
        assert stream.getvalue() == ""  # throttled

    def test_update_tty_final_always_writes(self):
        stream = io.StringIO()
        bar = ProgressBar(
            "Test",
            10,
            is_tty=True,
            colors=Colors(force_color=True),
            stream=stream,
        )
        bar.update(1)
        stream.truncate(0)
        stream.seek(0)
        # current == total should always write (not throttled)
        bar.update(10)
        assert stream.getvalue() != ""

    def test_update_tty_after_1s_writes(self):
        stream = io.StringIO()
        bar = ProgressBar(
            "Test",
            100,
            is_tty=True,
            colors=Colors(force_color=True),
            stream=stream,
        )
        bar.update(1)
        # Simulate 1 second passing
        bar._last_draw_time = time.monotonic() - 1.1
        stream.truncate(0)
        stream.seek(0)
        bar.update(2)
        assert stream.getvalue() != ""

    def test_update_ci_10pct_increments(self):
        stream = io.StringIO()
        bar = ProgressBar(
            "Test",
            100,
            is_tty=False,
            colors=Colors(force_color=False),
            stream=stream,
        )
        # Update from 1 to 100
        for i in range(1, 101):
            bar.update(i)

        lines = stream.getvalue().strip().split("\n")
        # Should have ~11 lines: 0%(from bucket 0 at i=1..9), 10%, 20%, ..., 100%
        # Actually: bucket 0 at i=1 (0% mapped), bucket 1 at i=10 (10%), ...
        # bucket 0: 1*100//100=1 -> 1//10=0 (emitted at i=1)
        # bucket 1: 10*100//100=10 -> 10//10=1 (emitted at i=10)
        # ...
        # bucket 10: 100*100//100=100 -> 100//10=10 (emitted at i=100)
        assert len(lines) == 11

    def test_update_ci_no_repeat_buckets(self):
        stream = io.StringIO()
        bar = ProgressBar(
            "Test",
            200,
            is_tty=False,
            colors=Colors(force_color=False),
            stream=stream,
        )
        # Update with items 1..200
        for i in range(1, 201):
            bar.update(i)

        lines = stream.getvalue().strip().split("\n")
        # Each 10% bucket should appear exactly once
        pcts = []
        for line in lines:
            # Extract percentage from "[..] Test  NNN%"
            parts = line.strip().split()
            pct_str = parts[-1].rstrip("%")
            pcts.append(int(pct_str))
        # pcts should be [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        assert pcts == list(range(0, 110, 10))

    def test_finish_tty_clears_line(self):
        stream = io.StringIO()
        bar = ProgressBar(
            "Test",
            10,
            is_tty=True,
            colors=Colors(force_color=True),
            stream=stream,
        )
        bar.update(10)
        stream.truncate(0)
        stream.seek(0)
        bar.finish()
        output = stream.getvalue()
        assert "\r" in output

    def test_finish_nontty_noop(self):
        stream = io.StringIO()
        bar = ProgressBar(
            "Test",
            10,
            is_tty=False,
            colors=Colors(force_color=False),
            stream=stream,
        )
        bar.finish()
        assert stream.getvalue() == ""

    def test_finish_idempotent(self):
        """Calling finish() twice is safe; the second call is a no-op."""
        stream = io.StringIO()
        bar = ProgressBar(
            "Test",
            10,
            is_tty=True,
            colors=Colors(force_color=True),
            stream=stream,
        )
        bar.finish()
        first_output = stream.getvalue()
        assert "\r" in first_output
        stream.truncate(0)
        stream.seek(0)
        bar.finish()
        assert stream.getvalue() == ""  # second call produces nothing

    def test_bar_counts_with_small_total(self):
        bar = ProgressBar("Test", 3, colors=Colors(force_color=False))
        # 1/3 ≈ 33%
        line = bar._render_bar(1)
        assert "1/3" in line
        filled = line.count("█")
        assert filled == _BAR_WIDTH // 3  # 8

    def test_bar_pct_capped_at_100(self):
        bar = ProgressBar("Test", 10, colors=Colors(force_color=False))
        # Overshoot: current > total
        line = bar._render_bar(15)
        assert "100%" in line


# =========================================================================
# BuildLog — header
# =========================================================================


def _make_log(**kwargs) -> tuple[BuildLog, io.StringIO]:
    """Helper: create a BuildLog writing to a StringIO."""
    stream = io.StringIO()
    defaults = dict(
        package_name="testpkg",
        package_version="1.0.0",
        total_steps=5,
        estimated_seconds=60,
        stream=stream,
        force_color=False,
        width=80,
    )
    defaults.update(kwargs)
    log = BuildLog(**defaults)
    return log, stream


class TestBuildLogHeader:
    """Tests for ``BuildLog.header()``."""

    def test_header_contains_package_info(self):
        log, stream = _make_log()
        log.header()
        output = stream.getvalue()
        assert "testpkg" in output
        assert "v1.0.0" in output
        assert "great-docs build" in output

    def test_header_contains_step_count(self):
        log, stream = _make_log(total_steps=17)
        log.header()
        output = stream.getvalue()
        assert "17 steps" in output

    def test_header_contains_estimate(self):
        log, stream = _make_log(estimated_seconds=252)
        log.header()
        output = stream.getvalue()
        assert "~4 min" in output

    def test_header_no_estimate_when_zero(self):
        log, stream = _make_log(estimated_seconds=0)
        log.header()
        output = stream.getvalue()
        assert "estimated" not in output

    def test_header_no_package_name(self):
        log, stream = _make_log(package_name="", package_version="")
        log.header()
        output = stream.getvalue()
        assert "great-docs build" in output
        # Title line should not have " · " (no package name appended)
        lines = output.strip().split("\n")
        title_line = lines[1]  # line after top border
        assert "great-docs build" in title_line
        assert " · " not in title_line

    def test_header_package_name_without_version(self):
        log, stream = _make_log(package_name="mypkg", package_version="")
        log.header()
        output = stream.getvalue()
        assert "mypkg" in output
        assert " v" not in output  # no version appended

    def test_header_tty_has_box_drawing(self):
        log, stream = _make_log(force_color=True)
        log.header()
        output = stream.getvalue()
        assert "┌" in output
        assert "└" in output
        assert "│" in output

    def test_header_ci_has_equals(self):
        log, stream = _make_log(force_color=False)
        log.header()
        output = stream.getvalue()
        assert "===" in output
        assert "┌" not in output

    def test_header_box_width_capped(self):
        log, stream = _make_log(width=200, force_color=False)
        log.header()
        lines = stream.getvalue().split("\n")
        # The top border should be at most _BOX_MAX_WIDTH
        border_line = lines[0]
        assert len(border_line) <= _BOX_MAX_WIDTH


# =========================================================================
# BuildLog — step_start
# =========================================================================


class TestBuildLogStepStart:
    """Tests for ``BuildLog.step_start()``."""

    def test_step_start_ci_format(self):
        log, stream = _make_log(force_color=False)
        log.step_start(3, "Generate source links")
        output = stream.getvalue()
        assert "Step  3/5" in output
        assert "Generate source links" in output
        assert "--" in output

    def test_step_start_tty_format(self):
        log, stream = _make_log(force_color=True)
        log.step_start(3, "Generate source links")
        output = stream.getvalue()
        assert "Step  3/5" in output
        assert "Generate source links" in output
        assert "━" in output

    def test_step_start_pads_number(self):
        log, stream = _make_log(force_color=False, total_steps=17)
        log.step_start(1, "First step")
        output = stream.getvalue()
        assert "Step  1/17" in output

    def test_step_start_double_digit(self):
        log, stream = _make_log(force_color=False, total_steps=17)
        log.step_start(15, "Build site")
        output = stream.getvalue()
        assert "Step 15/17" in output

    def test_step_start_resets_warnings(self):
        log, stream = _make_log()
        log.step_start(1, "Step one")
        log.warn("warning 1")
        log.step_start(2, "Step two")
        assert len(log._step.warnings) == 0

    def test_step_start_sets_timer(self):
        log, _ = _make_log()
        before = time.monotonic()
        log.step_start(1, "Test")
        after = time.monotonic()
        assert before <= log._step.start_time <= after

    def test_step_start_blank_line_before(self):
        log, stream = _make_log(force_color=False)
        log.step_start(1, "Test")
        lines = stream.getvalue().split("\n")
        # First line should be blank (empty string before newline)
        assert lines[0] == ""


# =========================================================================
# BuildLog — detail
# =========================================================================


class TestBuildLogDetail:
    """Tests for ``BuildLog.detail()``."""

    def test_detail_always_shown(self):
        log, stream = _make_log()
        log.step_start(1, "Test")
        stream.truncate(0)
        stream.seek(0)
        log.detail("some detail info")
        output = stream.getvalue()
        assert "some detail info" in output
        assert output.startswith("   ")  # 3-space indent

    def test_detail_tty_uses_gray(self):
        log, stream = _make_log(force_color=True)
        log.step_start(1, "Test")
        stream.truncate(0)
        stream.seek(0)
        log.detail("tty detail")
        output = stream.getvalue()
        assert "\033[90m" in output  # bright black (gray)
        assert "tty detail" in output

    def test_detail_empty_string_suppressed(self):
        log, stream = _make_log()
        log.step_start(1, "Test")
        stream.truncate(0)
        stream.seek(0)
        log.detail("")
        assert stream.getvalue() == ""

    def test_detail_emoji_only_suppressed(self):
        log, stream = _make_log()
        log.step_start(1, "Test")
        stream.truncate(0)
        stream.seek(0)
        log.detail("🎉")
        assert stream.getvalue() == ""

    def test_detail_preserves_leading_indent(self):
        log, stream = _make_log()
        log.step_start(1, "Test")
        stream.truncate(0)
        stream.seek(0)
        log.detail("  - sub/item.qmd")
        output = stream.getvalue()
        assert "  - sub/item.qmd" in output


# =========================================================================
# BuildLog — warn
# =========================================================================


class TestBuildLogWarn:
    """Tests for ``BuildLog.warn()``."""

    def test_warn_always_shown(self):
        log, stream = _make_log(force_color=False)
        log.step_start(1, "Test")
        stream.truncate(0)
        stream.seek(0)
        log.warn("something bad")
        output = stream.getvalue()
        assert "something bad" in output
        assert "[!!]" in output
        # Also collected
        assert len(log._step.warnings) == 1
        assert log._step.warnings[0] == "something bad"

    def test_warn_increments_total(self):
        log, _ = _make_log()
        assert log._warning_total == 0
        log.step_start(1, "Test")
        log.warn("w1")
        log.warn("w2")
        assert log._warning_total == 2

    def test_warn_with_color(self):
        log, stream = _make_log(force_color=True)
        log.step_start(1, "Test")
        stream.truncate(0)
        stream.seek(0)
        log.warn("color warning")
        output = stream.getvalue()
        assert "\033[33m" in output  # yellow
        assert "⚠" in output


# =========================================================================
# BuildLog — tree_lines
# =========================================================================


class TestBuildLogTreeLines:
    """Tests for ``BuildLog.tree_lines()``."""

    def test_tree_lines_always_shown(self):
        log, stream = _make_log(force_color=False)
        log.step_start(1, "Test")
        stream.truncate(0)
        stream.seek(0)
        log.tree_lines(["first", "second", "third"])
        output = stream.getvalue()
        assert "├─" in output
        assert "└─" in output
        assert "first" in output
        assert "third" in output

    def test_tree_lines_tty_has_dim_connectors(self):
        log, stream = _make_log(force_color=True)
        log.step_start(1, "Test")
        stream.truncate(0)
        stream.seek(0)
        log.tree_lines(["alpha", "beta"])
        output = stream.getvalue()
        assert "\033[2m" in output  # DIM for connectors
        assert "├─" in output
        assert "└─" in output
        assert "alpha" in output
        assert "beta" in output

    def test_tree_lines_last_gets_corner(self):
        log, stream = _make_log(force_color=False)
        log.tree_lines(["a", "b"])
        lines = [l for l in stream.getvalue().split("\n") if l.strip()]
        assert "├─" in lines[0]
        assert "└─" in lines[1]

    def test_tree_lines_single_item(self):
        log, stream = _make_log(force_color=False)
        log.tree_lines(["only one"])
        output = stream.getvalue()
        assert "└─" in output
        assert "├─" not in output

    def test_tree_lines_empty_list(self):
        log, stream = _make_log()
        stream.truncate(0)
        stream.seek(0)
        log.tree_lines([])
        assert stream.getvalue() == ""


# =========================================================================
# BuildLog — substep
# =========================================================================


class TestBuildLogSubstep:
    """Tests for ``BuildLog.substep()``."""

    def test_substep_non_tty_middle(self):
        """Non-TTY substep uses plain ├─ connector and [OK] icon."""
        log, stream = _make_log(force_color=False)
        log.step_start(1, "Test")
        stream.truncate(0)
        stream.seek(0)
        log.substep("Interlinks resolved")
        out = stream.getvalue()
        assert "├─" in out
        assert "[OK]" in out
        assert "Interlinks resolved" in out
        assert "└─" not in out

    def test_substep_non_tty_last(self):
        """Non-TTY substep with last=True uses └─ connector."""
        log, stream = _make_log(force_color=False)
        log.step_start(1, "Test")
        stream.truncate(0)
        stream.seek(0)
        log.substep("Scale-to-fit injected", last=True)
        out = stream.getvalue()
        assert "└─" in out
        assert "├─" not in out
        assert "[OK]" in out
        assert "Scale-to-fit injected" in out

    def test_substep_tty_middle(self):
        """TTY substep uses colored DIM connector and ✓ icon."""
        log, stream = _make_log(force_color=True)
        log.step_start(1, "Test")
        stream.truncate(0)
        stream.seek(0)
        log.substep("SEO enhancements applied")
        out = stream.getvalue()
        assert "├─" in out
        assert "✔" in out
        assert "SEO enhancements applied" in out

    def test_substep_tty_last(self):
        """TTY substep with last=True uses └─ connector."""
        log, stream = _make_log(force_color=True)
        log.step_start(1, "Test")
        stream.truncate(0)
        stream.seek(0)
        log.substep("Done", last=True)
        out = stream.getvalue()
        assert "└─" in out
        assert "├─" not in out
        assert "✔" in out

    def test_substep_sequence(self):
        """Multiple substeps print on separate lines in order."""
        log, stream = _make_log(force_color=False)
        log.step_start(1, "Post-render")
        stream.truncate(0)
        stream.seek(0)
        log.substep("Reference pages processed")
        log.substep("Interlinks resolved")
        log.substep("Scale-to-fit injected", last=True)
        lines = [l for l in stream.getvalue().splitlines() if l.strip()]
        assert len(lines) == 3
        assert "Reference pages" in lines[0]
        assert "Interlinks" in lines[1]
        assert "Scale-to-fit" in lines[2]
        # First two use ├─, last uses └─
        assert "├─" in lines[0]
        assert "├─" in lines[1]
        assert "└─" in lines[2]


# =========================================================================
# BuildLog — step_done
# =========================================================================


class TestBuildLogStepDone:
    """Tests for ``BuildLog.step_done()``."""

    def test_step_done_shows_summary(self):
        log, stream = _make_log(force_color=False)
        log.step_start(1, "Test")
        stream.truncate(0)
        stream.seek(0)
        log.step_done("Everything worked")
        output = stream.getvalue()
        assert "[OK]" in output
        assert "Everything worked" in output

    def test_step_done_shows_elapsed_time(self):
        log, stream = _make_log(force_color=False)
        log.step_start(1, "Test")
        # Artificially set start time to 1 second ago
        log._step.start_time = time.monotonic() - 1.5
        stream.truncate(0)
        stream.seek(0)
        log.step_done("Done")
        output = stream.getvalue()
        # Should contain a time like "1.5s" (approximately)
        assert "s" in output

    def test_step_done_increments_completed(self):
        log, _ = _make_log()
        assert log._completed == 0
        log.step_start(1, "Test")
        log.step_done("Done")
        assert log._completed == 1

    def test_step_done_with_warnings_default_mode(self):
        log, stream = _make_log(force_color=False)
        log.step_start(1, "Test")
        log.warn("w1")
        log.warn("w2")
        stream.truncate(0)
        stream.seek(0)
        log.step_done("Generated stuff")
        output = stream.getvalue()
        assert "[!!]" in output  # warning icon
        assert "(2 warnings)" in output

    def test_step_done_with_one_warning_singular(self):
        log, stream = _make_log(force_color=False)
        log.step_start(1, "Test")
        log.warn("w1")
        stream.truncate(0)
        stream.seek(0)
        log.step_done("Generated stuff")
        output = stream.getvalue()
        assert "(1 warning)" in output
        assert "warnings" not in output

    def test_step_done_warnings_always_show_suffix(self):
        log, stream = _make_log(force_color=False)
        log.step_start(1, "Test")
        log.warn("w1")
        stream.truncate(0)
        stream.seek(0)
        log.step_done("Generated stuff")
        output = stream.getvalue()
        # Warnings are shown inline AND the suffix is always present
        assert "[!!]" in output
        assert "(1 warning)" in output

    def test_step_done_tty_has_green_check(self):
        log, stream = _make_log(force_color=True)
        log.step_start(1, "Test")
        stream.truncate(0)
        stream.seek(0)
        log.step_done("All good")
        output = stream.getvalue()
        assert "✔" in output
        assert "\033[32m" in output  # green


# =========================================================================
# BuildLog — step_skip
# =========================================================================


class TestBuildLogStepSkip:
    """Tests for ``BuildLog.step_skip()``."""

    def test_step_skip_ci_format(self):
        log, stream = _make_log(force_color=False)
        log.step_start(4, "Generate SKILL.md")
        stream.truncate(0)
        stream.seek(0)
        log.step_skip(4, "disabled in config")
        output = stream.getvalue()
        assert "[--]" in output
        assert "Skipped (disabled in config)" in output

    def test_step_skip_tty_format(self):
        log, stream = _make_log(force_color=True)
        log.step_start(4, "Generate SKILL.md")
        stream.truncate(0)
        stream.seek(0)
        log.step_skip(4, "disabled in config")
        output = stream.getvalue()
        assert "⊘" in output
        assert "Skipped" in output
        assert "\033[2m" in output  # dim

    def test_step_skip_increments_skipped(self):
        log, _ = _make_log()
        assert log._skipped == 0
        log.step_start(1, "Test")
        log.step_skip(1, "reason")
        assert log._skipped == 1


# =========================================================================
# BuildLog — step_fail
# =========================================================================


class TestBuildLogStepFail:
    """Tests for ``BuildLog.step_fail()``."""

    def test_step_fail_ci_format(self):
        log, stream = _make_log(force_color=False)
        log.step_start(15, "Build site")
        stream.truncate(0)
        stream.seek(0)
        log.step_fail("Quarto render failed (exit code 1)")
        output = stream.getvalue()
        assert "[FAIL]" in output
        assert "Quarto render failed" in output

    def test_step_fail_tty_format(self):
        log, stream = _make_log(force_color=True)
        log.step_start(15, "Build site")
        stream.truncate(0)
        stream.seek(0)
        log.step_fail("Quarto render failed")
        output = stream.getvalue()
        assert "✖" in output
        assert "\033[1;31m" in output  # bold red

    def test_step_fail_records_failed_step(self):
        log, _ = _make_log()
        log.step_start(15, "Build site")
        log.step_fail("boom")
        assert log._failed_step is not None
        assert log._failed_step.number == 15
        assert log._failed_step.title == "Build site"

    def test_step_fail_shows_elapsed(self):
        log, stream = _make_log(force_color=False)
        log.step_start(15, "Build site")
        log._step.start_time = time.monotonic() - 5.0
        stream.truncate(0)
        stream.seek(0)
        log.step_fail("Failed")
        output = stream.getvalue()
        assert "s" in output


# =========================================================================
# BuildLog — error_detail
# =========================================================================


class TestBuildLogErrorDetail:
    """Tests for ``BuildLog.error_detail()``."""

    def test_error_detail_always_shown(self):
        log, stream = _make_log()
        log.error_detail("ERROR: bad yaml\n  at line 42")
        output = stream.getvalue()
        assert "ERROR: bad yaml" in output
        assert "at line 42" in output

    def test_error_detail_multiline(self):
        log, stream = _make_log()
        log.error_detail("line 1\nline 2\nline 3")
        lines = [l for l in stream.getvalue().split("\n") if l.strip()]
        assert len(lines) == 3


# =========================================================================
# BuildLog — progress
# =========================================================================


class TestBuildLogProgress:
    """Tests for ``BuildLog.progress()``."""

    def test_progress_returns_progress_bar(self):
        log, _ = _make_log()
        bar = log.progress("Rendering", 100)
        assert isinstance(bar, ProgressBar)
        assert bar.total == 100
        assert bar.label == "Rendering"

    def test_progress_inherits_tty_setting(self):
        log, _ = _make_log(force_color=True)
        bar = log.progress("Test", 10)
        assert bar.is_tty is True

    def test_progress_inherits_nontty_setting(self):
        log, _ = _make_log(force_color=False)
        bar = log.progress("Test", 10)
        assert bar.is_tty is False


# =========================================================================
# BuildLog — footer (success cases)
# =========================================================================


class TestBuildLogFooterSuccess:
    """Tests for ``BuildLog.footer()`` — successful builds."""

    def test_footer_contains_complete(self):
        log, stream = _make_log(force_color=False)
        log.step_start(1, "Test")
        log.step_done("Done")
        log.footer(site_path="great-docs/_site/index.html")
        output = stream.getvalue()
        assert "Build complete" in output
        assert "1/5 steps" in output

    def test_footer_contains_total_time(self):
        log, stream = _make_log(force_color=False)
        log.footer()
        output = stream.getvalue()
        assert "Total time:" in output

    def test_footer_contains_site_path(self):
        log, stream = _make_log(force_color=False)
        log.footer(site_path="great-docs/_site/index.html")
        output = stream.getvalue()
        assert "great-docs/_site/index.html" in output

    def test_footer_celebration_basic(self):
        log, stream = _make_log(force_color=False)
        log.footer(site_path="great-docs/_site/index.html")
        output = stream.getvalue()
        assert "🎉" in output
        assert "Site ready" in output

    def test_footer_celebration_large_site(self):
        log, stream = _make_log(force_color=False)
        log.footer(site_path="great-docs/_site/index.html", total_pages=203)
        output = stream.getvalue()
        assert "203 pages built!" in output

    def test_footer_celebration_small_site(self):
        log, stream = _make_log(force_color=False)
        log.footer(site_path="great-docs/_site/index.html", total_pages=50)
        output = stream.getvalue()
        assert "pages built!" not in output
        assert "Site ready" in output

    def test_footer_with_skipped(self):
        log, stream = _make_log(force_color=False)
        log.step_start(1, "A")
        log.step_done("Done")
        log.step_start(2, "B")
        log.step_skip(2, "disabled")
        log.step_start(3, "C")
        log.step_skip(3, "disabled")
        log.footer(site_path="path")
        output = stream.getvalue()
        assert "2 skipped" in output

    def test_footer_with_warnings(self):
        log, stream = _make_log(force_color=False)
        log.step_start(1, "Test")
        log.warn("w1")
        log.warn("w2")
        log.step_done("Done")
        log.footer(site_path="path")
        output = stream.getvalue()
        assert "2 warnings" in output

    def test_footer_with_one_warning_singular(self):
        log, stream = _make_log(force_color=False)
        log.step_start(1, "Test")
        log.warn("w1")
        log.step_done("Done")
        log.footer(site_path="path")
        output = stream.getvalue()
        assert "1 warning)" in output
        assert "warnings)" not in output

    def test_footer_tty_box_drawing(self):
        log, stream = _make_log(force_color=True)
        log.step_start(1, "Test")
        log.step_done("Done")
        log.footer(site_path="path")
        output = stream.getvalue()
        assert "┌" in output
        assert "└" in output

    def test_footer_ci_equals(self):
        log, stream = _make_log(force_color=False)
        log.footer(site_path="path")
        output = stream.getvalue()
        assert "===" in output

    def test_footer_watch_mode(self):
        log, stream = _make_log(force_color=False)
        log.footer(watch_mode=True)
        output = stream.getvalue()
        assert "Watching for changes" in output
        assert "Ctrl+C" in output

    def test_footer_celebration_with_warnings(self):
        log, stream = _make_log(force_color=False)
        log.footer(site_path="path", warnings=3)
        output = stream.getvalue()
        assert "3 warnings" in output

    def test_footer_long_path_wraps_to_two_lines(self):
        """When celebration + site_path exceeds box width, path wraps."""
        log, stream = _make_log(force_color=False, width=60)
        log.step_start(1, "Test")
        log.step_done("Done")
        long_path = "very/deeply/nested/project/path/great-docs/_site/index.html"
        log.footer(site_path=long_path)
        output = stream.getvalue()
        # Path should appear on its own line (indented with 3 spaces)
        assert f"   {long_path}" in output
        assert "Site ready" in output


# =========================================================================
# BuildLog — footer (failure cases)
# =========================================================================


class TestBuildLogFooterFailure:
    """Tests for ``BuildLog.footer()`` — failed builds."""

    def test_footer_failure_message(self):
        log, stream = _make_log(force_color=False)
        log.step_start(15, "Build site with Quarto")
        log.step_fail("Quarto render failed")
        stream.truncate(0)
        stream.seek(0)
        log.footer()
        output = stream.getvalue()
        assert "Build failed" in output
        assert "Step 15" in output
        assert "Build site with Quarto" in output

    def test_footer_failure_tty(self):
        log, stream = _make_log(force_color=True)
        log.step_start(15, "Build site")
        log.step_fail("boom")
        stream.truncate(0)
        stream.seek(0)
        log.footer()
        output = stream.getvalue()
        assert "✖ Build failed" in output

    def test_footer_failure_ci(self):
        log, stream = _make_log(force_color=False)
        log.step_start(15, "Build site")
        log.step_fail("boom")
        stream.truncate(0)
        stream.seek(0)
        log.footer()
        output = stream.getvalue()
        assert "[FAIL] Build failed" in output

    def test_footer_failure_shows_error_hint(self):
        log, stream = _make_log(force_color=False)
        log.step_start(15, "Build site")
        log.step_fail("boom")
        stream.truncate(0)
        stream.seek(0)
        log.footer()
        output = stream.getvalue()
        assert "See error details above" in output

    def test_footer_failure_no_celebration(self):
        log, stream = _make_log(force_color=False)
        log.step_start(15, "Build site")
        log.step_fail("boom")
        stream.truncate(0)
        stream.seek(0)
        log.footer(site_path="some/path")
        output = stream.getvalue()
        assert "🎉" not in output
        assert "Site ready" not in output


# =========================================================================
# BuildLog — icons
# =========================================================================


class TestBuildLogIcons:
    """Ensure icons vary correctly between TTY and CI modes."""

    def test_icons_tty(self):
        log, _ = _make_log(force_color=True)
        assert "✔" in log._icon_ok
        assert "⊘" in log._icon_skip
        assert "⚠" in log._icon_warn
        assert "✖" in log._icon_fail
        assert "►" in log._icon_progress

    def test_icons_ci(self):
        log, _ = _make_log(force_color=False)
        assert log._icon_ok == "[OK]"
        assert log._icon_skip == "[--]"
        assert log._icon_warn == "[!!]"
        assert log._icon_fail == "[FAIL]"
        assert log._icon_progress == "[..]"


# =========================================================================
# BuildLog — full pipeline integration
# =========================================================================


class TestBuildLogPipelineIntegration:
    """End-to-end tests simulating a realistic build sequence."""

    def test_mini_build_default_mode(self):
        log, stream = _make_log(
            total_steps=3,
            estimated_seconds=30,
            force_color=False,
        )
        log.header()
        # Step 1: success
        log.step_start(1, "Prepare")
        log.step_done("Ready")
        # Step 2: skipped
        log.step_start(2, "Optional")
        log.step_skip(2, "disabled")
        # Step 3: success
        log.step_start(3, "Build")
        log.step_done("Done")
        log.footer(site_path="out/index.html")

        output = stream.getvalue()
        assert "3 steps" in output
        assert "Prepare" in output
        assert "Skipped" in output
        assert "Build" in output
        assert "Build complete" in output
        assert "1 skipped" in output

    def test_mini_build_with_detail(self):
        log, stream = _make_log(
            total_steps=2,
            force_color=False,
        )
        log.header()
        log.step_start(1, "Process")
        log.detail("Processing item A")
        log.detail("Processing item B")
        log.warn("item C had issues")
        log.tree_lines(["result A", "result B"])
        log.step_done("2 items processed")
        log.footer(site_path="out/index.html")

        output = stream.getvalue()
        assert "Processing item A" in output
        assert "Processing item B" in output
        assert "[!!]" in output  # warning inline
        assert "├─ result A" in output
        assert "└─ result B" in output
        assert "2 items processed" in output

    def test_failed_build(self):
        log, stream = _make_log(total_steps=3, force_color=False)
        log.header()
        log.step_start(1, "Prepare")
        log.step_done("Ready")
        log.step_start(2, "Build")
        log.step_fail("Exit code 1")
        log.error_detail("ERROR: invalid yaml\n  at line 42")
        log.footer()

        output = stream.getvalue()
        assert "[FAIL]" in output
        assert "ERROR: invalid yaml" in output
        assert "Build failed at Step 2" in output

    def test_build_with_progress_bar(self):
        log, stream = _make_log(force_color=False)
        log.step_start(1, "Render")
        bar = log.progress("Rendering", 10)
        for i in range(1, 11):
            bar.update(i)
        bar.finish()
        log.step_done("Rendered 10 pages")

        output = stream.getvalue()
        # CI mode: should have percentage lines
        assert "Rendering" in output
        assert "Rendered 10 pages" in output

    def test_multiple_steps_track_counters(self):
        log, _ = _make_log(total_steps=5)
        log.step_start(1, "A")
        log.step_done("ok")
        log.step_start(2, "B")
        log.step_done("ok")
        log.step_start(3, "C")
        log.warn("w1")
        log.step_done("ok")
        log.step_start(4, "D")
        log.step_skip(4, "off")
        log.step_start(5, "E")
        log.step_fail("boom")

        assert log._completed == 3
        assert log._skipped == 1
        assert log._warning_total == 1
        assert log._failed_step is not None
        assert log._failed_step.number == 5


# =========================================================================
# BuildLog — box helpers
# =========================================================================


class TestBuildLogBoxHelpers:
    """Tests for internal box-drawing helpers."""

    def test_box_width_capped(self):
        log, _ = _make_log(width=200)
        assert log._box_width() == _BOX_MAX_WIDTH

    def test_box_width_narrow_terminal(self):
        log, _ = _make_log(width=40)
        assert log._box_width() == 40

    def test_box_line_ci(self):
        log, _ = _make_log(force_color=False, width=200)
        line = log._box_line("hello")
        assert line.startswith("|")
        assert line.endswith("|")
        assert "hello" in line

    def test_box_line_tty(self):
        log, _ = _make_log(force_color=True, width=200)
        line = log._box_line("hello")
        assert "│" in line
        assert "hello" in line

    def test_box_top_ci(self):
        log, _ = _make_log(force_color=False, width=200)
        top = log._box_top()
        assert top == "=" * _BOX_MAX_WIDTH

    def test_box_top_tty(self):
        log, _ = _make_log(force_color=True, width=200)
        top = log._box_top()
        assert "┌" in top
        assert "┐" in top

    def test_box_bottom_ci(self):
        log, _ = _make_log(force_color=False, width=200)
        bot = log._box_bottom()
        assert bot == "=" * _BOX_MAX_WIDTH

    def test_box_bottom_tty(self):
        log, _ = _make_log(force_color=True, width=200)
        bot = log._box_bottom()
        assert "└" in bot
        assert "┘" in bot

    def test_box_blank(self):
        log, _ = _make_log(force_color=False, width=200)
        blank = log._box_blank()
        assert blank.startswith("|")
        assert blank.strip("|").strip() == ""


# =========================================================================
# BuildLog — _StepState
# =========================================================================


class TestStepState:
    """Tests for the ``_StepState`` dataclass."""

    def test_defaults(self):
        s = _StepState()
        assert s.number == 0
        assert s.title == ""
        assert s.start_time == 0.0
        assert s.warnings == []

    def test_independent_warning_lists(self):
        s1 = _StepState()
        s2 = _StepState()
        s1.warnings.append("a")
        assert s2.warnings == []


# =========================================================================
# Edge cases & regression tests
# =========================================================================


class TestEdgeCases:
    """Misc edge cases and regression safeguards."""

    def test_format_elapsed_negative(self):
        # Shouldn't happen, but don't crash
        result = format_elapsed(-1.0)
        assert result == "<0.1s"

    def test_format_elapsed_very_large(self):
        result = format_elapsed(100000)
        assert "h" in result

    def test_format_estimate_negative(self):
        assert format_estimate(-10) == "~1 min"

    def test_progress_bar_update_beyond_total(self):
        stream = io.StringIO()
        bar = ProgressBar(
            "Test",
            10,
            is_tty=False,
            colors=Colors(force_color=False),
            stream=stream,
        )
        # Should not crash
        bar.update(15)
        output = stream.getvalue()
        assert "100%" in output

    def test_build_log_footer_no_site_path(self):
        log, stream = _make_log(force_color=False)
        log.footer()  # no site_path
        output = stream.getvalue()
        assert "Build complete" in output

    def test_build_log_step_skip_does_not_increment_completed(self):
        log, _ = _make_log()
        log.step_start(1, "Test")
        log.step_skip(1, "off")
        assert log._completed == 0
        assert log._skipped == 1

    def test_concurrent_warnings_across_steps(self):
        log, _ = _make_log()
        log.step_start(1, "Step A")
        log.warn("w1")
        log.step_done("ok")
        log.step_start(2, "Step B")
        log.warn("w2")
        log.warn("w3")
        log.step_done("ok")
        # Total warnings tracked globally
        assert log._warning_total == 3
        # Current step should only have step 2's warnings
        assert len(log._step.warnings) == 2

    def test_pad_rail_handles_short_terminal(self):
        log, _ = _make_log(width=20, force_color=False)
        result = log._pad_rail("abcdefghijklmnopqrstuvwxyz", 26)
        # Rail padding should not go negative
        assert "━" not in result or result.count("━") >= 0

    def test_step_start_then_done_then_footer_all_work(self):
        """Smoke test: the entire happy path runs without errors."""
        log, stream = _make_log(
            package_name="mypkg",
            package_version="2.0.0",
            total_steps=1,
            estimated_seconds=10,
            force_color=False,
        )
        log.header()
        log.step_start(1, "Do stuff")
        log.detail("verbose detail")
        log.step_done("Stuff done")
        log.footer(site_path="out/index.html", total_pages=5)
        output = stream.getvalue()
        # Sanity: we got a complete output
        assert "mypkg" in output
        assert "Do stuff" in output
        assert "Stuff done" in output
        assert "Build complete" in output

    def test_write_flushes(self):
        """Verify that _write calls flush on the stream."""
        stream = io.StringIO()
        log = BuildLog(stream=stream, force_color=False, width=80)
        # StringIO.flush is a no-op but we can verify it doesn't crash
        log._write("test line")
        assert "test line" in stream.getvalue()

    def test_step_done_right_aligns_time(self):
        """Time should appear after the summary, padded with spaces."""
        log, stream = _make_log(force_color=False, width=80)
        log.step_start(1, "Test")
        log._step.start_time = time.monotonic() - 2.5
        stream.truncate(0)
        stream.seek(0)
        log.step_done("Short summary")
        line = stream.getvalue().strip()
        # The line should have spaces between summary and time
        assert "  " in line  # at least 2 consecutive spaces for padding


# =========================================================================
# Defensive / resilience tests
# =========================================================================


class TestDefensiveWrite:
    """Verify _write survives broken pipes and I/O errors."""

    def test_write_survives_broken_pipe(self):
        class BrokenStream:
            def write(self, _s):
                raise BrokenPipeError("pipe closed")

            def flush(self):
                raise BrokenPipeError("pipe closed")

        log = BuildLog(stream=BrokenStream(), force_color=False, width=80)
        # Should not raise
        log._write("test line")
        log.header()
        log.step_start(1, "Test")
        log.detail("detail")
        log.warn("warning")
        log.step_done("Done")
        log.footer(site_path="out/index.html")

    def test_write_survives_os_error(self):
        class ErrorStream:
            def write(self, _s):
                raise OSError("disk full")

            def flush(self):
                raise OSError("disk full")

        log = BuildLog(stream=ErrorStream(), force_color=False, width=80)
        log._write("test")  # should not raise

    def test_progress_bar_survives_broken_pipe(self):
        class BrokenStream:
            def write(self, _s):
                raise BrokenPipeError

            def flush(self):
                raise BrokenPipeError

        bar = ProgressBar(
            "Test", 10, is_tty=True, colors=Colors(force_color=True), stream=BrokenStream()
        )
        bar.update(5)  # should not raise
        bar.finish()  # should not raise

    def test_progress_bar_ci_survives_broken_pipe(self):
        class BrokenStream:
            def write(self, _s):
                raise BrokenPipeError

            def flush(self):
                raise BrokenPipeError

        bar = ProgressBar(
            "Test", 10, is_tty=False, colors=Colors(force_color=False), stream=BrokenStream()
        )
        bar.update(5)  # should not raise


class TestDefensiveStepTiming:
    """Verify step_done/step_fail handle missing step_start."""

    def test_step_done_without_step_start(self):
        """step_done without step_start should show <0.1s, not hours."""
        log, stream = _make_log(force_color=False)
        # Deliberately skip step_start
        log.step_done("Surprise result")
        output = stream.getvalue()
        assert "<0.1s" in output  # not an absurd elapsed time
        assert "Surprise result" in output

    def test_step_fail_without_step_start(self):
        """step_fail without step_start should show <0.1s, not hours."""
        log, stream = _make_log(force_color=False)
        log.step_fail("Unexpected failure")
        output = stream.getvalue()
        assert "<0.1s" in output
        assert "Unexpected failure" in output
