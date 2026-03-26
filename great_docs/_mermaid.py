"""
Mermaid diagram pre-rendering for Great Docs.

Renders mermaid diagrams to static PNG files at build time using the mermaid.ink API.
Generates both light and dark theme versions for proper theme switching.
"""

import base64
import hashlib
import json
import re
import urllib.error
import urllib.request
from pathlib import Path


def encode_mermaid(diagram: str, theme: str = "default") -> str:
    """Encode a mermaid diagram for the mermaid.ink API with theme config."""
    # Create config with theme
    config = {"theme": theme}

    # Use pako-compatible encoding (base64)
    diagram_bytes = diagram.encode("utf-8")
    config_bytes = json.dumps(config).encode("utf-8")

    # Combine as JSON state
    state = {
        "code": diagram,
        "mermaid": config,
    }
    state_json = json.dumps(state)

    return base64.urlsafe_b64encode(state_json.encode("utf-8")).decode("utf-8")


def encode_mermaid_simple(diagram: str) -> str:
    """Simple base64 encoding for mermaid diagram."""
    return base64.urlsafe_b64encode(diagram.encode("utf-8")).decode("utf-8")


def get_diagram_hash(diagram: str) -> str:
    """Get a short hash of the diagram for caching."""
    return hashlib.md5(diagram.encode("utf-8")).hexdigest()[:12]


def render_mermaid_to_png(diagram: str, theme: str = "default", timeout: int = 30) -> bytes | None:
    """
    Render a mermaid diagram to PNG using the mermaid.ink API.

    Parameters
    ----------
    diagram
        The mermaid diagram code.
    theme
        The mermaid theme: 'default', 'dark', 'forest', 'neutral'.
    timeout
        Request timeout in seconds.

    Returns
    -------
    bytes | None
        The PNG image data, or None if rendering failed.
    """
    encoded = encode_mermaid_simple(diagram)
    # Use theme parameter in URL
    url = f"https://mermaid.ink/img/{encoded}?theme={theme}&bgColor=!white"
    if theme == "dark":
        url = f"https://mermaid.ink/img/{encoded}?theme=dark&bgColor=!1f2937"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "great-docs/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"Warning: Failed to render mermaid diagram ({theme}): {e}")
        return None


def render_mermaid_to_svg(diagram: str, timeout: int = 30) -> str | None:
    """
    Render a mermaid diagram to SVG using the mermaid.ink API.

    Parameters
    ----------
    diagram
        The mermaid diagram code.
    timeout
        Request timeout in seconds.

    Returns
    -------
    str | None
        The SVG content, or None if rendering failed.
    """
    encoded = encode_mermaid_simple(diagram)
    url = f"https://mermaid.ink/svg/{encoded}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "great-docs/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            svg_content = response.read().decode("utf-8")
            return svg_content
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"Warning: Failed to render mermaid diagram: {e}")
        return None


def extract_mermaid_blocks(content: str) -> list[tuple[str, str, int, int]]:
    """
    Extract mermaid code blocks from qmd/md content.

    Returns list of (full_match, diagram_code, start_pos, end_pos).
    """
    # Match ```{mermaid} or ```mermaid blocks
    pattern = r"```\{?mermaid\}?\s*\n(.*?)```"
    matches = []
    for match in re.finditer(pattern, content, re.DOTALL):
        full_match = match.group(0)
        diagram_code = match.group(1).strip()
        matches.append((full_match, diagram_code, match.start(), match.end()))
    return matches


def render_diagrams_for_page(
    qmd_path: Path,
    output_dir: Path,
    cache_dir: Path | None = None,
) -> dict[str, tuple[Path, Path]]:
    """
    Render all mermaid diagrams in a qmd file to PNG (light + dark).

    Parameters
    ----------
    qmd_path
        Path to the qmd file.
    output_dir
        Directory to save PNG files.
    cache_dir
        Optional cache directory.

    Returns
    -------
    dict
        Map of diagram hash to (light_path, dark_path) tuples.
    """
    content = qmd_path.read_text(encoding="utf-8")
    blocks = extract_mermaid_blocks(content)

    if not blocks:
        return {}

    output_dir.mkdir(parents=True, exist_ok=True)
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    for _, diagram_code, _, _ in blocks:
        diagram_hash = get_diagram_hash(diagram_code)

        light_filename = f"mermaid-{diagram_hash}-light.png"
        dark_filename = f"mermaid-{diagram_hash}-dark.png"

        light_path = output_dir / light_filename
        dark_path = output_dir / dark_filename

        # Check cache
        if cache_dir:
            cache_light = cache_dir / light_filename
            cache_dark = cache_dir / dark_filename
            if cache_light.exists() and cache_dark.exists():
                # Copy from cache
                light_path.write_bytes(cache_light.read_bytes())
                dark_path.write_bytes(cache_dark.read_bytes())
                results[diagram_hash] = (light_path, dark_path)
                continue

        # Render both themes
        light_data = render_mermaid_to_png(diagram_code, theme="default")
        dark_data = render_mermaid_to_png(diagram_code, theme="dark")

        if light_data and dark_data:
            light_path.write_bytes(light_data)
            dark_path.write_bytes(dark_data)

            # Save to cache
            if cache_dir:
                (cache_dir / light_filename).write_bytes(light_data)
                (cache_dir / dark_filename).write_bytes(dark_data)

            results[diagram_hash] = (light_path, dark_path)

    return results


def process_qmd_mermaid(
    qmd_path: Path,
    output_dir: Path,
    cache_dir: Path | None = None,
) -> str:
    """
    Process a qmd file and render all mermaid diagrams to PNG (light + dark).

    Parameters
    ----------
    qmd_path
        Path to the qmd file.
    output_dir
        Directory to save PNG files.
    cache_dir
        Optional cache directory.

    Returns
    -------
    str
        The modified qmd content with mermaid blocks replaced by theme-aware images.
    """
    content = qmd_path.read_text(encoding="utf-8")
    blocks = extract_mermaid_blocks(content)

    if not blocks:
        return content

    output_dir.mkdir(parents=True, exist_ok=True)
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)

    # Process blocks in reverse order to preserve positions
    for full_match, diagram_code, start, end in reversed(blocks):
        diagram_hash = get_diagram_hash(diagram_code)

        light_filename = f"mermaid-{diagram_hash}-light.png"
        dark_filename = f"mermaid-{diagram_hash}-dark.png"

        light_path = output_dir / light_filename
        dark_path = output_dir / dark_filename

        # Check cache first
        light_data = None
        dark_data = None

        if cache_dir:
            cache_light = cache_dir / light_filename
            cache_dark = cache_dir / dark_filename
            if cache_light.exists() and cache_dark.exists():
                light_data = cache_light.read_bytes()
                dark_data = cache_dark.read_bytes()

        # Render if not cached
        if light_data is None or dark_data is None:
            print(f"   Rendering mermaid diagram {diagram_hash}...")
            light_data = render_mermaid_to_png(diagram_code, theme="default")
            dark_data = render_mermaid_to_png(diagram_code, theme="dark")

            # Save to cache
            if light_data and dark_data and cache_dir:
                (cache_dir / light_filename).write_bytes(light_data)
                (cache_dir / dark_filename).write_bytes(dark_data)

        if light_data and dark_data:
            # Save PNGs
            light_path.write_bytes(light_data)
            dark_path.write_bytes(dark_data)

            # Create HTML that switches based on theme
            # Uses CSS to show/hide based on .quarto-light / .quarto-dark
            replacement = f"""
::: {{.mermaid-diagram}}
![Diagram]({light_filename}){{.mermaid-light .light-mode-only}}

![Diagram]({dark_filename}){{.mermaid-dark .dark-mode-only}}
:::
"""
            content = content[:start] + replacement + content[end:]
        else:
            # Keep original block if rendering failed
            print("Warning: Keeping original mermaid block (rendering failed)")

    return content


def render_mermaid_string(diagram: str, output_path: Path) -> bool:
    """
    Render a single mermaid diagram string to an SVG file.

    Parameters
    ----------
    diagram
        The mermaid diagram code.
    output_path
        Path to save the SVG file.

    Returns
    -------
    bool
        True if rendering succeeded, False otherwise.
    """
    svg_content = render_mermaid_to_svg(diagram)
    if svg_content:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(svg_content, encoding="utf-8")
        return True
    return False
