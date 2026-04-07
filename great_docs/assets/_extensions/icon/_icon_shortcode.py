"""Bridge script for the {{< icon >}} Quarto shortcode.

Called by icon.lua during ``quarto render``.  Imports
:func:`great_docs._icons.get_icon_svg` and prints the resulting
SVG markup to stdout.

Usage::

    python _icon_shortcode.py NAME [--size SIZE] [--class CSS_CLASS]
        [--label TEXT]

Examples::

    python _icon_shortcode.py heart
    python _icon_shortcode.py rocket --size 24 --class my-icon
    python _icon_shortcode.py check --label "Complete"
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


def _load_icons_module():
    """Load ``great_docs._icons`` without requiring great_docs to be installed.

    Walks up the directory tree from this script's location until it
    finds ``great_docs/_icons.py`` and imports it directly.  This avoids
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a Lucide icon as inline SVG.")
    parser.add_argument("name", help="Lucide icon name (e.g. 'heart', 'rocket')")
    parser.add_argument("--size", type=int, default=16, help="Icon size in pixels")
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

        svg = get_icon_svg(args.name, size=args.size, css_class=args.css_class)

        if not svg:
            print(
                f"<!-- icon shortcode error: unknown icon '{args.name}' -->",
                file=sys.stderr,
            )
            sys.exit(1)

        # If a label is provided, make the icon accessible
        if args.label:
            svg = svg.replace('aria-hidden="true"', f'aria-label="{args.label}" role="img"')

        print(svg, end="")
    except Exception as exc:
        print(
            f"<!-- icon shortcode error for '{args.name}': {exc} -->",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
