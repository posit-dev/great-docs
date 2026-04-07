from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


def _load_icons_module():
    """Load `great_docs._icons` without requiring great_docs to be installed.

    Walks up the directory tree from this script's location until it
    finds `great_docs/_icons.py` and imports it directly.  This avoids
    requiring the full great_docs package (and its dependencies) to be
    installed in whatever Python interpreter Quarto happens to use.
    """
    # Fast path: great_docs is installed
    try:
        from great_docs._icons import get_icon_svg

        return get_icon_svg
    except Exception:
        pass

    # Walk ancestors to find the _icons.py source file
    cur = Path(__file__).resolve().parent
    for ancestor in cur.parents:
        icons_path = ancestor / "great_docs" / "_icons.py"
        if icons_path.exists():
            spec = importlib.util.spec_from_file_location("_icons", icons_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod.get_icon_svg

    raise ImportError("Cannot locate great_docs/_icons.py")


def _apply_inline_text_style(svg: str, size_px: int | None) -> str:
    """Replace pixel width/height with em-based inline styles.

    Follows this approach:

    - height/width in `em` so the icon scales with surrounding text
    - `vertical-align: -0.125em` to sit on the text baseline
    - `font-size: inherit` to pick up the parent element's size
    - `overflow: visible` to prevent clipping
    - `position: relative` for correct stacking context

    When the caller specifies a custom pixel size, it is converted to
    `em` relative to a 16 px base (e.g. 24 px -> 1.5em).
    """
    if size_px is None or size_px == 16:
        em = "1em"
    else:
        em = f"{round(size_px / 16, 3)}em"

    style = (
        f"height:{em};"
        f"width:{em};"
        "vertical-align:-0.125em;"
        "font-size:inherit;"
        "overflow:visible;"
        "position:relative;"
    )

    # Strip the old pixel width="N" height="N" attributes
    svg = re.sub(r'\s*width="\d+"', "", svg)
    svg = re.sub(r'\s*height="\d+"', "", svg)

    # Inject the style attribute into the opening <svg> tag
    svg = svg.replace("<svg ", f'<svg style="{style}" ', 1)
    return svg


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a Lucide icon as inline SVG.")
    parser.add_argument("name", help="Lucide icon name (e.g. 'heart', 'rocket')")
    parser.add_argument("--size", type=int, default=None, help="Icon size in pixels")
    parser.add_argument(
        "--class", dest="css_class", default="gd-icon", help="CSS class for the SVG"
    )
    parser.add_argument(
        "--label",
        default=None,
        help="Accessible label (sets aria-label instead of aria-hidden)",
    )

    args = parser.parse_args()

    try:
        get_icon_svg = _load_icons_module()

        # get_icon_svg needs a pixel size; default to 16 (will be replaced by em)
        px_size = args.size if args.size is not None else 16
        svg = get_icon_svg(args.name, size=px_size, css_class=args.css_class)

        if not svg:
            print(
                f"<!-- icon shortcode error: unknown icon '{args.name}' -->",
                file=sys.stderr,
            )
            sys.exit(1)

        # Replace pixel sizing with em-based inline styles
        svg = _apply_inline_text_style(svg, args.size)

        # If a label is provided, make the icon accessible
        if args.label:
            svg = svg.replace(
                'aria-hidden="true"',
                f'aria-label="{args.label}" role="img"',
            )

        print(svg, end="")
    except Exception as exc:
        print(
            f"<!-- icon shortcode error for '{args.name}': {exc} -->",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
