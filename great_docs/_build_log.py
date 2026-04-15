from __future__ import annotations

import os
import re
import shutil
import sys
import time
import unicodedata
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Emoji / decoration stripping
# ---------------------------------------------------------------------------

# Common emoji used by internal print() calls that we want to normalise away in structured verbose
# output. We match a broad set of multi-byte emoji codepoints at the *start* of a line (after
# optional whitespace).
_EMOJI_RE = re.compile(
    r"^[\s]*([\U0001f300-\U0001f9ff\u2600-\u27bf\u2700-\u27bf"
    r"\U0001fa00-\U0001faff\u200d\ufe0f\u26a0\u2705\u274c"
    r"\U0001f4c2\U0001f4e6\U0001f4d6\U0001f50d\U0001f310"
    r"\U0001f389]+[\ufe0f\u200d]*\s*)",
)


def _strip_emoji(text: str) -> str:
    """Remove leading emoji decoration from a line of text.

    Preserves intentional leading indentation when no emoji is present.
    """
    result, n = _EMOJI_RE.subn("", text, count=1)
    if n:
        # Emoji removed — strip residual whitespace around it
        return result.strip()
    # No emoji — preserve leading indent, strip only trailing whitespace
    return text.rstrip()


def _display_width(text: str) -> int:
    """Return the terminal display width of *text*.

    Wide characters (e.g. ``🎉``, ``👀``) occupy two columns; everything
    else occupies one.
    """
    w = 0
    for ch in text:
        eaw = unicodedata.east_asian_width(ch)
        w += 2 if eaw in ("W", "F") else 1
    return w


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

_COLOR_ATTRS = (
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
)


class Colors:
    """ANSI colour codes with automatic ``NO_COLOR`` / non-TTY detection."""

    RESET: str
    BOLD: str
    DIM: str
    CYAN: str
    GREEN: str
    YELLOW: str
    RED: str
    WHITE: str
    BOLD_CYAN: str
    BOLD_GREEN: str
    BOLD_RED: str
    BOLD_WHITE: str

    def __init__(self, *, force_color: bool | None = None) -> None:
        if force_color is True:
            use_color = True
        elif force_color is False:
            use_color = False
        else:
            use_color = _should_use_color()

        if use_color:
            self.RESET = "\033[0m"
            self.BOLD = "\033[1m"
            self.DIM = "\033[2m"
            self.CYAN = "\033[36m"
            self.GREEN = "\033[32m"
            self.YELLOW = "\033[33m"
            self.RED = "\033[31m"
            self.WHITE = "\033[37m"
            self.BOLD_CYAN = "\033[1;36m"
            self.BOLD_GREEN = "\033[1;32m"
            self.BOLD_RED = "\033[1;31m"
            self.BOLD_WHITE = "\033[1;37m"
        else:
            for attr in _COLOR_ATTRS:
                setattr(self, attr, "")

        self.use_color = use_color


def _should_use_color() -> bool:
    """Return *True* when ANSI colours should be emitted."""
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Time formatting
# ---------------------------------------------------------------------------


def format_elapsed(seconds: float) -> str:
    """Format an elapsed duration for display.

    Rules (from the spec):
    * < 0.1 s  → `<0.1s`
    * 0.1–59.9 → `{n:.1f}s`
    * 60–3599  → `{m}m {s:.1f}s`
    * ≥ 3600   → `{h}h {m}m {s}s`
    """
    if seconds < 0.1:
        return "<0.1s"
    if round(seconds, 1) < 60.0:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        total = round(seconds, 1)
        m = int(total) // 60
        s = total - m * 60
        return f"{m}m {s:.1f}s"
    h = int(seconds) // 3600
    remainder = seconds - h * 3600
    m = int(remainder) // 60
    s = int(remainder) % 60
    return f"{h}h {m}m {s}s"


def format_estimate(seconds: float) -> str:
    """Format the time-estimate shown in the build header.

    Always returns `~N min` (minimum `~1 min`).
    """
    minutes = max(1, round(seconds / 60))
    return f"~{minutes} min"


def estimate_build_time(
    *,
    n_api_items: int = 0,
    n_total_pages: int = 0,
    n_code_cells: int = 0,
) -> float:
    """Return an estimated build time in seconds.

    Calibrated against large real-world projects on a current-generation MacBook Pro (M-series).
    Each coefficient represents a single dominant cost observed in profiling:

    =========  ===========  ============================================
    Phase      Coefficient  Rationale
    =========  ===========  ============================================
    griffe     3.2 s/item   Import + introspection (~1.3 s) **plus**
                            source-link resolution (~1.9 s) per
                            `_object_types.json` entry.
    quarto     0.5 s/page   Markdown-only page render average
    code cell  3.0 s/cell   Jupyter kernel startup amortised per cell
    post-rend  0.3 s/page   HTML transforms (BeautifulSoup)
    =========  ===========  ============================================

    Parameters
    ----------
    n_api_items
        Total entries in `_object_types.json` (classes + methods +
        functions + attributes — **not** just top-level exports).
    n_total_pages
        Total `.qmd` / `.md` pages Quarto will render (reference +
        user guide + sections + changelog + homepage + CLI).
    n_code_cells
        Number of executable ````` ```{python} ````` fences across
        all `.qmd` files.  Each cell adds ~3 s of Jupyter overhead.
    """
    base = 5.0  # fixed overhead (directory setup, asset copy, etc.)
    griffe = n_api_items * 3.2  # import + introspect + source links
    quarto = n_total_pages * 0.5  # plain page rendering
    code = n_code_cells * 3.0  # executable code cell overhead
    post_render = n_total_pages * 0.3  # HTML post-processing
    return base + griffe + quarto + code + post_render


# ---------------------------------------------------------------------------
# Progress bar
# ---------------------------------------------------------------------------

_BAR_WIDTH = 24


class ProgressBar:
    """In-place progress bar for long-running steps.

    Parameters
    ----------
    label
        Text shown before the bar (e.g. `"Rendering pages"`).
    total
        Total number of items.
    is_tty
        Whether to use `\r` overwriting.  When *False* (CI), discrete
        lines are emitted at every 10 % boundary.
    colors
        A :class:`Colors` instance for styling.
    stream
        The output stream (default `sys.stdout`).
    """

    def __init__(
        self,
        label: str,
        total: int,
        *,
        is_tty: bool = True,
        colors: Colors | None = None,
        stream=None,
    ) -> None:
        self.label = label
        self.total = max(total, 1)  # avoid division by zero
        self.is_tty = is_tty
        self.colors = colors or Colors(force_color=False)
        self.stream = stream or sys.stdout
        self._current = 0
        self._last_draw_time: float = 0.0
        self._last_pct_bucket: int = -1  # for CI 10 % steps
        self._finished: bool = False

    # -- rendering ----------------------------------------------------------

    def _render_bar(self, current: int) -> str:
        """Return a single progress-bar line (no newline)."""
        pct = min(current * 100 // self.total, 100)
        filled = current * _BAR_WIDTH // self.total
        filled = min(filled, _BAR_WIDTH)
        empty = _BAR_WIDTH - filled

        c = self.colors
        bar = f"{c.CYAN}{'█' * filled}{c.DIM}{'░' * empty}{c.RESET}"
        counter = f"{current}/{self.total}"
        return f"   {c.CYAN}►{c.RESET} {self.label}  {bar}  {counter}  {pct}%"

    def _render_bar_plain(self, current: int) -> str:
        """Plain-text bar for non-TTY (CI)."""
        pct = min(current * 100 // self.total, 100)
        return f"   [..] {self.label}  {pct:>3d}%"

    # -- public API ---------------------------------------------------------

    def update(self, current: int) -> None:
        """Advance the bar to *current* (1-based)."""
        self._current = current

        try:
            if self.is_tty:
                now = time.monotonic()
                if now - self._last_draw_time < 1.0 and current < self.total:
                    return  # throttle to 1 Hz
                self._last_draw_time = now
                line = self._render_bar(current)
                self.stream.write(f"\r{line}")
                self.stream.flush()
            else:
                # CI mode: emit at every 10 % boundary
                bucket = min(current * 100 // self.total, 100) // 10
                if bucket > self._last_pct_bucket:
                    self._last_pct_bucket = bucket
                    self.stream.write(self._render_bar_plain(current) + "\n")
                    self.stream.flush()
        except (BrokenPipeError, OSError):
            pass

    def finish(self, summary: str | None = None) -> None:  # noqa: ARG002
        """Clear the progress line.

        The caller is responsible for printing the final result line
        via :meth:`BuildLog.step_done`.  Safe to call more than once.
        """
        if self._finished:
            return
        self._finished = True
        if self.is_tty:
            # Clear the in-place line
            try:
                width = shutil.get_terminal_size((80, 24)).columns
                self.stream.write("\r" + " " * width + "\r")
                self.stream.flush()
            except (BrokenPipeError, OSError):
                pass


# ---------------------------------------------------------------------------
# Build log
# ---------------------------------------------------------------------------

_BOX_MAX_WIDTH = 78


@dataclass
class _StepState:
    """Mutable bookkeeping for the current step."""

    number: int = 0
    title: str = ""
    start_time: float = 0.0
    warnings: list[str] = field(default_factory=list)


class BuildLog:
    """Structured build-log output.

    Parameters
    ----------
    package_name
        Name of the package being built.
    package_version
        Version string.
    total_steps
        Number of pipeline steps (including skippable ones).
    estimated_seconds
        Estimated total build time in seconds.
    stream
        Output stream (default `sys.stdout`).
    force_color
        Override colour auto-detection (*True* = always, *False* = never).
    width
        Override terminal width (mainly for testing).
    """

    def __init__(
        self,
        *,
        package_name: str = "",
        package_version: str = "",
        total_steps: int = 17,
        estimated_seconds: float = 0,
        stream=None,
        force_color: bool | None = None,
        width: int | None = None,
    ) -> None:
        self.package_name = package_name
        self.package_version = package_version
        self.total_steps = total_steps
        self.estimated_seconds = estimated_seconds
        self.stream = stream or sys.stdout
        self.colors = Colors(force_color=force_color)
        self._width = width or shutil.get_terminal_size((80, 24)).columns
        self._is_tty = self.colors.use_color  # co-varies with colour

        # Counters for the footer
        self._completed: int = 0
        self._skipped: int = 0
        self._warning_total: int = 0
        self._failed_step: _StepState | None = None
        self._build_start: float = time.monotonic()

        # Current step bookkeeping
        self._step = _StepState()

    # -- internal helpers ---------------------------------------------------

    def _write(self, text: str) -> None:
        try:
            self.stream.write(text + "\n")
            self.stream.flush()
        except (BrokenPipeError, OSError):
            pass  # never crash the build for a logging failure

    def _pad_rail(self, inner: str, inner_plain_len: int) -> str:
        """Pad a step header *inner* string with ``━`` to fill the width."""
        remaining = max(self._width - inner_plain_len, 0)
        return inner + "━" * remaining

    # -- icons --------------------------------------------------------------

    @property
    def _icon_ok(self) -> str:
        c = self.colors
        return f"{c.GREEN}✔{c.RESET}" if self._is_tty else "[OK]"

    @property
    def _icon_skip(self) -> str:
        c = self.colors
        return f"{c.DIM}⊘{c.RESET}" if self._is_tty else "[--]"

    @property
    def _icon_warn(self) -> str:
        c = self.colors
        return f"{c.YELLOW}⚠{c.RESET}" if self._is_tty else "[!!]"

    @property
    def _icon_fail(self) -> str:
        c = self.colors
        return f"{c.BOLD_RED}✖{c.RESET}" if self._is_tty else "[FAIL]"

    @property
    def _icon_progress(self) -> str:
        c = self.colors
        return f"{c.CYAN}►{c.RESET}" if self._is_tty else "[..]"

    # -- header / footer boxes ----------------------------------------------

    def _box_width(self) -> int:
        return min(self._width, _BOX_MAX_WIDTH)

    def _box_line(self, text: str) -> str:
        """Return a box content line, padded to box width."""
        c = self.colors
        bw = self._box_width()
        inner_w = bw - 5  # "│  " (3) + " │" (2)
        pad = max(inner_w - _display_width(text), 0)
        padded = text + " " * pad
        if self._is_tty:
            return f"{c.CYAN}│{c.RESET}  {padded} {c.CYAN}│{c.RESET}"
        else:
            return f"|  {padded} |"

    def _box_top(self) -> str:
        c = self.colors
        bw = self._box_width()
        if self._is_tty:
            return f"{c.CYAN}┌{'─' * (bw - 2)}┐{c.RESET}"
        else:
            return "=" * bw

    def _box_bottom(self) -> str:
        c = self.colors
        bw = self._box_width()
        if self._is_tty:
            return f"{c.CYAN}└{'─' * (bw - 2)}┘{c.RESET}"
        else:
            return "=" * bw

    def _box_blank(self) -> str:
        """An empty line inside the box."""
        return self._box_line("")

    # -- public API: header -------------------------------------------------

    def header(self) -> None:
        """Print the build header box."""
        title = "great-docs build"
        if self.package_name:
            title += f" · {self.package_name}"
            if self.package_version:
                title += f" v{self.package_version}"

        info = f"{self.total_steps} steps"
        if self.estimated_seconds > 0:
            info += f" · estimated {format_estimate(self.estimated_seconds)}"

        self._write(self._box_top())
        self._write(self._box_line(title))
        self._write(self._box_line(info))
        self._write(self._box_bottom())

    # -- public API: steps --------------------------------------------------

    def step_start(self, n: int, title: str) -> None:
        """Print the step header rail and start the timer."""
        self._step = _StepState(
            number=n,
            title=title,
            start_time=time.monotonic(),
            warnings=[],
        )

        c = self.colors
        label = f" Step {n:>2d}/{self.total_steps} "
        sep = "─"
        inner = f"━━{label}{sep} {title} "
        inner_plain_len = len(f"━━{label}{sep} {title} ")

        if self._is_tty:
            coloured = (
                f"{c.BOLD_CYAN}━━{c.BOLD_WHITE}{label}{c.BOLD_CYAN}{sep}"
                f" {c.BOLD_WHITE}{title}{c.RESET} "
            )
            line = self._pad_rail(coloured, inner_plain_len)
        else:
            line = f"-- Step {n:>2d}/{self.total_steps} - {title} "
            line += "-" * max(self._width - len(line), 0)

        self._write("")
        self._write(line)

    def detail(self, msg: str) -> None:
        """Emit a detail line.

        Leading emoji are stripped and the text is rendered in dim colour
        on TTY so that detail lines are visually subordinate to result lines.
        """
        clean = _strip_emoji(msg)
        if not clean:
            return
        c = self.colors
        if self._is_tty:
            self._write(f"      \033[90m{clean}{c.RESET}")
        else:
            self._write(f"      {clean}")

    def warn(self, msg: str) -> None:
        """Record and display a warning for the current step."""
        self._step.warnings.append(msg)
        self._warning_total += 1
        self._write(f"   {self._icon_warn} {msg}")

    def tree_lines(self, lines: list[str]) -> None:
        """Emit tree-formatted sub-items."""
        if not lines:
            return
        c = self.colors
        for i, line in enumerate(lines):
            connector = "└─" if i == len(lines) - 1 else "├─"
            if self._is_tty:
                self._write(f"   {c.DIM}{connector}{c.RESET} {line}")
            else:
                self._write(f"   {connector} {line}")

    def substep(self, label: str, *, last: bool = False) -> None:
        """Print a mini-pipeline check-off sub-item (always visible).

        Parameters
        ----------
        label
            Short description of the sub-step (e.g. `"Interlinks resolved"`).
        last
            If *True*, use a `└─` connector instead of `├─`.
        """
        c = self.colors
        connector = "└─" if last else "├─"
        icon = self._icon_ok
        if self._is_tty:
            self._write(f"   {c.DIM}{connector}{c.RESET} {icon} {label}")
        else:
            self._write(f"   {connector} {icon} {label}")

    def step_done(self, summary: str) -> None:
        """Print a success result line with elapsed time."""
        if self._step.start_time:
            elapsed = time.monotonic() - self._step.start_time
        else:
            elapsed = 0.0  # step_start was never called
        elapsed_str = format_elapsed(elapsed)
        self._completed += 1

        n_warnings = len(self._step.warnings)
        c = self.colors
        time_part = f"{c.DIM}{elapsed_str}{c.RESET}" if self._is_tty else elapsed_str

        if n_warnings:
            suffix = f" ({n_warnings} warning{'s' if n_warnings != 1 else ''})"
            icon = self._icon_warn
        else:
            suffix = ""
            icon = self._icon_ok

        text = f"{summary}{suffix}"
        # Right-align the time
        plain_left = f"   X {text}"  # X = icon placeholder
        padding = max(self._width - len(plain_left) - len(elapsed_str), 1)

        self._write(f"   {icon} {text}{' ' * padding}{time_part}")

    def step_skip(self, n: int, reason: str) -> None:  # noqa: ARG002
        """Print a skipped-step result line.

        The caller must have already called :meth:`step_start` to print the
        step header rail.
        """
        self._skipped += 1
        c = self.colors
        if self._is_tty:
            self._write(f"   {self._icon_skip} {c.DIM}Skipped ({reason}){c.RESET}")
        else:
            self._write(f"   {self._icon_skip} Skipped ({reason})")

    def step_fail(self, message: str) -> None:
        """Print a failure result line with elapsed time."""
        if self._step.start_time:
            elapsed = time.monotonic() - self._step.start_time
        else:
            elapsed = 0.0  # step_start was never called
        elapsed_str = format_elapsed(elapsed)
        self._failed_step = _StepState(
            number=self._step.number,
            title=self._step.title,
            start_time=self._step.start_time,
        )

        c = self.colors
        time_part = f"{c.DIM}{elapsed_str}{c.RESET}" if self._is_tty else elapsed_str
        plain_left = f"   FAIL {message}"
        padding = max(self._width - len(plain_left) - len(elapsed_str), 1)
        self._write(f"   {self._icon_fail} {message}{' ' * padding}{time_part}")

    def error_detail(self, text: str) -> None:
        """Print error detail lines (always visible, even in non-verbose)."""
        for line in text.splitlines():
            self._write(f"   {line}")

    # -- public API: progress bar -------------------------------------------

    def progress(self, label: str, total: int) -> ProgressBar:
        """Create and return a :class:`ProgressBar` for a long-running step."""
        return ProgressBar(
            label=label,
            total=total,
            is_tty=self._is_tty,
            colors=self.colors,
            stream=self.stream,
        )

    # -- public API: footer -------------------------------------------------

    def footer(
        self,
        *,
        site_path: str = "",
        total_pages: int = 0,
        warnings: int | None = None,
        watch_mode: bool = False,
    ) -> None:
        """Print the build footer box."""
        total_elapsed = time.monotonic() - self._build_start
        elapsed_str = format_elapsed(total_elapsed)
        warn_count = warnings if warnings is not None else self._warning_total

        if self._failed_step:
            status_line = (
                f"✖ Build failed at Step {self._failed_step.number} — {self._failed_step.title}"
            )
            if not self._is_tty:
                status_line = (
                    f"[FAIL] Build failed at Step {self._failed_step.number}"
                    f" - {self._failed_step.title}"
                )
        else:
            ran = self._completed + self._skipped
            parts: list[str] = []
            if self._skipped:
                parts.append(f"{self._skipped} skipped")
            if warn_count:
                parts.append(f"{warn_count} warning{'s' if warn_count != 1 else ''}")
            suffix = f" ({', '.join(parts)})" if parts else ""
            icon = "✔" if self._is_tty else "[OK]"
            status_line = f"{icon} Build complete — {ran}/{self.total_steps} steps{suffix}"

        time_line = f"Total time: {elapsed_str}"

        # Celebration / site-ready line
        if self._failed_step:
            extra_line = "See error details above."
        elif watch_mode:
            extra_line = "👀 Watching for changes... (Ctrl+C to stop)"
        else:
            celebration = "🎉 "
            if total_pages > 100:
                celebration += f"{total_pages} pages built! "
            if warn_count and not self._failed_step:
                celebration += (
                    f"Site ready ({warn_count} warning{'s' if warn_count != 1 else ''}) → "
                )
            else:
                celebration += "Site ready → "
            extra_line = celebration

        self._write("")
        self._write(self._box_top())
        self._write(self._box_line(status_line))
        self._write(self._box_line(time_line))
        self._write(self._box_blank())

        if site_path and not self._failed_step:
            # May need two lines if path is long
            full_extra = extra_line + site_path
            bw = self._box_width()
            inner_w = bw - 5  # must match _box_line arithmetic
            if _display_width(full_extra) <= inner_w:
                self._write(self._box_line(full_extra))
            else:
                self._write(self._box_line(extra_line))
                self._write(self._box_line(f"   {site_path}"))
        elif self._failed_step:
            self._write(self._box_line(extra_line))
        elif watch_mode:
            self._write(self._box_line(extra_line))

        self._write(self._box_bottom())
