"""
D2 diagram pre-rendering for Great Docs.

Renders `d2` diagrams to static SVG files at build time using the local `d2` CLI
(https://d2lang.com). Each diagram is rendered twice (once with a light theme and once with a dark
theme) and swapped at read time via the site's `.light-mode-only` / `.dark-mode-only` classes, so
diagrams match the page background in both light and dark mode.

Unlike Mermaid (which Quarto renders client-side), `d2` has no native Quarto support, so diagrams
are pre-rendered here before Quarto sees the page. The rendered SVGs are self-contained (fonts are
embedded), so no JavaScript is needed on the reader's side.

If the `d2` binary is not installed, the original code block is left untouched and a warning is
printed, so builds degrade gracefully.
"""

import hashlib
import re
import shutil
import subprocess
from pathlib import Path

# Default d2 themes. Light "Neutral Default" (0) and dark "Dark Mauve" (200).
# See `d2 themes` for the full catalog.
DEFAULT_LIGHT_THEME = 0
DEFAULT_DARK_THEME = 200

# Default padding (px) around the diagram. Smaller than d2's own default (100)
# so diagrams sit tighter inside their framed container.
DEFAULT_PAD = 20

# Recognized `#| key: value` option lines inside a d2 block. Everything else is
# treated as diagram source.
_OPTION_KEYS = {"theme", "dark-theme", "layout", "sketch", "pad", "scale"}

# A fence line: optional indent, a run of >= 3 backticks, then an info string.
_FENCE_OPEN = re.compile(r"^[ \t]*(`{3,})[ \t]*(.*?)[ \t]*$")
# A d2 info string: `d2`, `{d2}`, `{.d2}`, `{d2 …}` — d2 followed by a boundary.
_D2_INFO = re.compile(r"^\{?\.?d2(?:[\s}].*)?$")

# Match the opening tag of the root <svg> element.
_SVG_TAG_PATTERN = re.compile(r"<svg\b[^>]*>", re.IGNORECASE)
_VIEWBOX_PATTERN = re.compile(
    r'viewBox\s*=\s*"[\d.\-]+\s+[\d.\-]+\s+([\d.]+)\s+([\d.]+)"',
    re.IGNORECASE,
)


def _ensure_svg_dimensions(svg: str) -> str:
    """
    Add explicit `width`/`height` to the root `<svg>` if it only has a viewBox.

    d2 emits a root `<svg>` with a `viewBox` but no intrinsic dimensions. When such an SVG is loaded
    via an `<img>` tag, browsers fall back to a tiny default size, so we backfill width/height from
    the viewBox.
    """
    tag_match = _SVG_TAG_PATTERN.search(svg)
    if not tag_match:
        return svg

    tag = tag_match.group(0)
    if re.search(r"\bwidth\s*=", tag, re.IGNORECASE):
        return svg

    vb = _VIEWBOX_PATTERN.search(tag)
    if not vb:
        return svg

    width, height = vb.group(1), vb.group(2)
    new_tag = tag[:-1] + f' width="{width}" height="{height}">'
    return svg[: tag_match.start()] + new_tag + svg[tag_match.end() :]


def d2_available() -> bool:
    """Return `True` if the `d2` CLI is on the PATH."""
    return shutil.which("d2") is not None


def extract_d2_blocks(content: str) -> list[tuple[str, str, int, int]]:
    """
    Extract top-level d2 code blocks from qmd/md content.

    Returns a list of `(full_match, diagram_code, start_pos, end_pos)` tuples.

    Fence-aware: a fenced block is opened by a run of >= 3 backticks and closed
    by a line with at least as many backticks. Only *top-level* d2 blocks are
    returned, so a ``` ```{d2} ``` example shown inside a longer ```` ````markdown ````
    display fence (or any other outer fence) is left untouched, and an inline
    `` ```d2 `` mention in prose is never treated as a fence.
    """
    lines = content.splitlines(keepends=True)

    # Character offset of the start of each line, for slicing positions.
    offsets: list[int] = []
    off = 0
    for ln in lines:
        offsets.append(off)
        off += len(ln)

    matches: list[tuple[str, str, int, int]] = []
    i = 0
    n = len(lines)
    while i < n:
        open_match = _FENCE_OPEN.match(lines[i].rstrip("\n"))
        if not open_match:
            i += 1
            continue

        ticks, info = open_match.group(1), open_match.group(2).strip()
        # A closing fence: at least as many backticks, nothing else but space.
        close_re = re.compile(r"^[ \t]*`{" + str(len(ticks)) + r",}[ \t]*$")

        j = i + 1
        while j < n and not close_re.match(lines[j].rstrip("\n")):
            j += 1

        if j < n and _D2_INFO.match(info):
            start = offsets[i]
            end = offsets[j] + len(lines[j])
            body = "".join(lines[i + 1 : j]).strip("\n")
            matches.append((content[start:end], body, start, end))

        # Skip past this whole fence (its inner lines are never re-scanned),
        # which is what keeps nested d2 blocks from being matched.
        i = j + 1 if j < n else n

    return matches


def parse_d2_block(block: str) -> tuple[str, dict[str, str]]:
    """
    Split a d2 block body into its diagram source and `#|` option lines.

    Parameters
    ----------
    block
        The raw contents of a d2 fenced block (without the fences).

    Returns
    -------
    tuple[str, dict[str, str]]
        The diagram source (options stripped) and a dict of recognized options.
    """
    options: dict[str, str] = {}
    source_lines: list[str] = []
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith("#|"):
            body = stripped[2:].strip()
            if ":" in body:
                key, _, value = body.partition(":")
                key = key.strip().lower()
                if key in _OPTION_KEYS:
                    options[key] = value.strip()
                    continue
            # Unrecognized `#|` line — keep it out of the d2 source anyway.
            continue
        source_lines.append(line)
    return "\n".join(source_lines).strip("\n"), options


def get_diagram_hash(diagram: str, options: dict[str, str]) -> str:
    """Return a short, stable hash of the diagram plus its options (for caching)."""
    key = diagram + "\x00" + repr(sorted(options.items()))
    return hashlib.md5(key.encode("utf-8")).hexdigest()[:12]


def _build_d2_args(theme: int, options: dict[str, str]) -> list[str]:
    """Assemble `d2` CLI flags from resolved options for a given theme."""
    args = ["d2", "--theme", str(theme)]

    pad = options.get("pad")
    args += ["--pad", str(pad) if pad is not None else str(DEFAULT_PAD)]

    layout = options.get("layout")
    if layout:
        args += ["--layout", layout]

    scale = options.get("scale")
    if scale:
        args += ["--scale", scale]

    sketch = options.get("sketch")
    if sketch and sketch.lower() in {"true", "1", "yes"}:
        args += ["--sketch"]

    # Read from stdin, write to stdout.
    args += ["-", "-"]
    return args


def render_d2_svg(
    diagram: str,
    theme: int,
    options: dict[str, str] | None = None,
    timeout: int = 30,
) -> str | None:
    """
    Render a d2 diagram to SVG using the `d2` CLI.

    Parameters
    ----------
    diagram
        The d2 diagram source.
    theme
        The d2 theme id (see `d2 themes`).
    options
        Optional resolved options (`layout`, `pad`, `sketch`, `scale`).
    timeout
        Subprocess timeout in seconds.

    Returns
    -------
    str | None
        The SVG content, or `None` if rendering failed.
    """
    args = _build_d2_args(theme, options or {})
    try:
        result = subprocess.run(
            args,
            input=diagram.encode("utf-8"),
            capture_output=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as e:
        print(f"Warning: Failed to render d2 diagram (theme {theme}): {e}")
        return None

    if result.returncode != 0:
        err = result.stderr.decode("utf-8", "replace").strip()
        print(f"Warning: d2 failed to render diagram (theme {theme}): {err}")
        return None

    return _ensure_svg_dimensions(result.stdout.decode("utf-8"))


def _resolve_themes(options: dict[str, str]) -> tuple[int, int]:
    """Resolve the light and dark theme ids from options + defaults."""

    def _as_int(value: str | None, default: int) -> int:
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            return default

    light = _as_int(options.get("theme"), DEFAULT_LIGHT_THEME)
    dark = _as_int(options.get("dark-theme"), DEFAULT_DARK_THEME)
    return light, dark


def _render_block(
    diagram_code: str,
    output_dir: Path,
    cache_dir: Path | None,
) -> str | None:
    """
    Render one d2 block to light + dark SVGs and return the replacement markup.

    Returns `None` if rendering failed (caller keeps the original block).
    """
    source, options = parse_d2_block(diagram_code)
    if not source.strip():
        return None

    light_theme, dark_theme = _resolve_themes(options)
    diagram_hash = get_diagram_hash(source, options)

    light_filename = f"d2-{diagram_hash}-light.svg"
    dark_filename = f"d2-{diagram_hash}-dark.svg"
    light_path = output_dir / light_filename
    dark_path = output_dir / dark_filename

    light_svg: str | None = None
    dark_svg: str | None = None

    # Check the cache first.
    if cache_dir:
        cache_light = cache_dir / light_filename
        cache_dark = cache_dir / dark_filename
        if cache_light.exists() and cache_dark.exists():
            light_svg = cache_light.read_text(encoding="utf-8")
            dark_svg = cache_dark.read_text(encoding="utf-8")

    if light_svg is None or dark_svg is None:
        light_svg = render_d2_svg(source, light_theme, options)
        dark_svg = render_d2_svg(source, dark_theme, options)
        if light_svg and dark_svg and cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)
            (cache_dir / light_filename).write_text(light_svg, encoding="utf-8")
            (cache_dir / dark_filename).write_text(dark_svg, encoding="utf-8")

    if not light_svg or not dark_svg:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    light_path.write_text(light_svg, encoding="utf-8")
    dark_path.write_text(dark_svg, encoding="utf-8")

    # Theme-aware markup using the site's existing light/dark toggle classes.
    # Empty image captions avoid Quarto rendering a stray "figure caption"
    # under each diagram; `fig-alt` still provides screen-reader text.
    return (
        "\n"
        "::: {.d2-diagram}\n"
        f'![]({light_filename}){{.light-mode-only fig-alt="D2 diagram"}}\n\n'
        f'![]({dark_filename}){{.dark-mode-only fig-alt="D2 diagram"}}\n'
        ":::\n"
    )


def process_d2_content(
    content: str,
    output_dir: Path,
    cache_dir: Path | None = None,
) -> tuple[str, int]:
    """
    Rewrite all d2 blocks in *content* to theme-aware SVG markup.

    SVG files are written into *output_dir* (typically the page's own directory, so relative image
    paths resolve).

    Returns
    -------
    tuple[str, int]
        The rewritten content and the number of diagrams rendered.
    """
    blocks = extract_d2_blocks(content)
    if not blocks:
        return content, 0

    rendered = 0
    # Process in reverse so earlier match positions stay valid.
    for _, diagram_code, start, end in reversed(blocks):
        replacement = _render_block(diagram_code, output_dir, cache_dir)
        if replacement is None:
            # Keep the original block (rendering failed or d2 unavailable).
            continue
        content = content[:start] + replacement + content[end:]
        rendered += 1

    return content, rendered


def process_qmd_file(path: Path, cache_dir: Path | None = None) -> bool:
    """
    Process a single `.qmd` file, rewriting d2 blocks in place.

    Returns `True` if the file was modified.
    """
    content = path.read_text(encoding="utf-8")
    if "d2" not in content:  # cheap early-out
        return False

    rewritten, rendered = process_d2_content(content, path.parent, cache_dir)
    if rendered == 0 or rewritten == content:
        return False

    path.write_text(rewritten, encoding="utf-8")
    return True


def process_directory(directory: Path, cache_dir: Path | None = None) -> list[str]:
    """
    Process all `.qmd` files under *directory*, rendering d2 diagrams.

    Returns the relative paths of files that were modified. If the `d2` CLI is not installed,
    returns an empty list without touching any files (a warning is printed once).
    """
    if not d2_available():
        # Only warn if there is actually a d2 block somewhere to render.
        for qmd in directory.rglob("*.qmd"):
            text = qmd.read_text(encoding="utf-8")
            if extract_d2_blocks(text):
                print(
                    "Warning: 'd2' CLI not found on PATH so d2 diagrams are left "
                    "as code blocks. Install it from https://d2lang.com "
                    "(e.g. 'brew install d2')."
                )
                break
        return []

    modified: list[str] = []
    for qmd in sorted(directory.rglob("*.qmd")):
        if process_qmd_file(qmd, cache_dir):
            try:
                rel = str(qmd.relative_to(directory))
            except ValueError:  # pragma: no cover - rglob always yields subpaths
                rel = str(qmd)
            modified.append(rel)
    return modified
