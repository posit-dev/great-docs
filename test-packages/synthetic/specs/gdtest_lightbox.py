"""
gdtest_lightbox — Showcase the gd-lightbox extension.

Dimensions: A1, B1, C1, D1, E6, F1, G1, H7
Focus: Demonstrate lightbox with multiple modes: explicit class, auto mode,
       dark-mode variants, galleries, captions, credits, grouped images,
       and the .nolightbox opt-out. Includes a user guide page exercising
       every combination.
"""

# ── Helper: generate placeholder SVG images ──────────────────────────────────


def _svg(width, height, bg, label, text_color="white"):
    """Generate a simple labeled SVG as a string."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
        f'<rect width="{width}" height="{height}" fill="{bg}" rx="8"/>'
        f'<text x="{width // 2}" y="{height // 2 + 6}" text-anchor="middle" '
        f'fill="{text_color}" font-size="16" font-family="sans-serif">{label}</text>'
        f"</svg>\n"
    )


# Generate a set of test images
_IMAGES = {
    # Basic images for lightbox testing (at package root for README)
    "images/screenshot.svg": _svg(600, 400, "#4a90d9", "App Screenshot"),
    "images/diagram.svg": _svg(800, 500, "#2c3e50", "Architecture Diagram"),
}

# Images co-located with user guide pages (these get copied alongside .qmd files)
_UG_IMAGES = {
    "user_guide/images/screenshot.svg": _svg(600, 400, "#4a90d9", "App Screenshot"),
    "user_guide/images/diagram.svg": _svg(800, 500, "#2c3e50", "Architecture Diagram"),
    "user_guide/images/chart.svg": _svg(500, 350, "#8e44ad", "Revenue Chart"),
    # Dark-mode variant pair (naming convention: .light. / .dark.)
    "user_guide/images/dashboard.light.svg": _svg(700, 450, "#f8f9fa", "Dashboard (Light)", "#333"),
    "user_guide/images/dashboard.dark.svg": _svg(700, 450, "#1a1a2e", "Dashboard (Dark)"),
    # Explicit dark variant (non-convention naming)
    "user_guide/images/ui-preview.svg": _svg(600, 380, "#ffffff", "UI Preview (Light)", "#333"),
    "user_guide/images/ui-preview-night.svg": _svg(600, 380, "#16213e", "UI Preview (Dark)"),
    # Gallery images (steps in a tutorial)
    "user_guide/images/step1.svg": _svg(500, 320, "#e74c3c", "Step 1: Install"),
    "user_guide/images/step2.svg": _svg(500, 320, "#f39c12", "Step 2: Configure"),
    "user_guide/images/step3.svg": _svg(500, 320, "#27ae60", "Step 3: Build"),
    "user_guide/images/step4.svg": _svg(500, 320, "#3498db", "Step 4: Deploy"),
    # Before/after pair for comparison demo
    "user_guide/images/before.svg": _svg(600, 400, "#bdc3c7", "Before (v0.8)", "#333"),
    "user_guide/images/after.svg": _svg(600, 400, "#2ecc71", "After (v0.9)"),
    # Mosaic gallery images (varying dimensions)
    "user_guide/images/mosaic-a.svg": _svg(400, 300, "#1abc9c", "Gallery A"),
    "user_guide/images/mosaic-b.svg": _svg(400, 500, "#e67e22", "Gallery B (Tall)"),
    "user_guide/images/mosaic-c.svg": _svg(600, 300, "#9b59b6", "Gallery C (Wide)"),
    "user_guide/images/mosaic-d.svg": _svg(400, 400, "#34495e", "Gallery D"),
    # Large image for zoom-target testing
    "user_guide/images/full-page.svg": _svg(1200, 800, "#2c3e50", "Full Page Screenshot"),
    # Small inline image (should NOT get lightbox in auto mode)
    "user_guide/images/icon-small.svg": _svg(24, 24, "#666", "•"),
}


SPEC = {
    "name": "gdtest_lightbox",
    "description": "Lightbox extension showcase with all feature combinations",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F1", "G1", "H7"],
    # ── Project metadata ─────────────────────────────────────────────
    "pyproject_toml": {
        "project": {
            "name": "gdtest-lightbox",
            "version": "1.0.0",
            "description": "Synthetic package to test the gd-lightbox extension",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    # ── Config ────────────────────────────────────────────────────────
    "config": {
        "display_name": "Lightbox Demo",
    },
    # ── Source files ──────────────────────────────────────────────────
    "files": {
        # Minimal Python module (needed for great-docs to detect a package)
        "gdtest_lightbox/__init__.py": '''\
            """A test package for the gd-lightbox extension."""

            __version__ = "1.0.0"
            __all__ = ["create_figure"]


            def create_figure(title: str, width: int = 600, height: int = 400) -> str:
                """
                Create a placeholder figure.

                Parameters
                ----------
                title
                    The title text to render on the figure.
                width
                    Figure width in pixels.
                height
                    Figure height in pixels.

                Returns
                -------
                str
                    SVG markup for the figure.
                """
                return f"<svg>{title}</svg>"
        ''',
        # README with some lightbox images
        "README.md": """\
            # gdtest-lightbox

            A synthetic package showcasing the **gd-lightbox** extension for Great Docs.

            ## Overview

            This site demonstrates all lightbox features:

            - Click-to-zoom with origin animation
            - Dark-mode image variants
            - Gallery with filmstrip navigation
            - Copy/download toolbar
            - Deep-linking

            ![App Screenshot](images/screenshot.svg){.lightbox}

            ## Architecture

            ![Architecture Diagram](images/diagram.svg){.lightbox caption="System architecture overview" credit="Engineering Team"}
        """,
        # ── User Guide: Lightbox Features ────────────────────────────
        "user_guide/01-basic-lightbox.qmd": """\
            ---
            title: "Basic Lightbox"
            ---

            ## Explicit Lightbox Class

            Add `{.lightbox}` to any image to enable click-to-zoom:

            ![App Screenshot](images/screenshot.svg){.lightbox}

            ## With Caption and Credit

            ![Revenue Chart](images/chart.svg){.lightbox caption="Q4 2024 revenue growth across all segments" credit="Data Analytics Team"}

            ## No Lightbox (opt-out)

            This image explicitly opts out with `{.nolightbox}`:

            ![Small diagram](images/diagram.svg){.nolightbox}

            ## Inline image (should not get lightbox in auto mode)

            Here is an inline icon ![icon](images/icon-small.svg) within text.
        """,
        "user_guide/02-auto-mode.qmd": """\
            ---
            title: "Auto Mode"
            lightbox: true
            ---

            ## Auto Lightbox Mode

            When `lightbox: true` is set in the page YAML, all block-level images
            automatically get lightbox treatment. No `{.lightbox}` class needed.

            ![Architecture Diagram](images/diagram.svg)

            ![Revenue Chart](images/chart.svg)

            ## Inline images are skipped

            This inline icon ![icon](images/icon-small.svg) should not get
            the lightbox treatment because it's inline with text.

            ## Explicit opt-out still works

            ![This image is excluded](images/screenshot.svg){.nolightbox}
        """,
        "user_guide/03-dark-mode.qmd": """\
            ---
            title: "Dark Mode Variants"
            ---

            ## Auto-Detected Dark Variants

            Images using the `.light.ext` / `.dark.ext` naming convention are
            automatically swapped when the user toggles dark mode:

            ![Dashboard](images/dashboard.light.svg){.lightbox}

            Toggle between light and dark mode to see the image change.

            ## Explicit Dark Variant

            Use the `dark="..."` attribute to specify a non-conventionally named
            dark variant:

            ![UI Preview](images/ui-preview.svg){.lightbox dark="images/ui-preview-night.svg"}
        """,
        "user_guide/04-galleries.qmd": """\
            ---
            title: "Galleries"
            ---

            ## Grouped Gallery

            Images with the same `group` attribute form a gallery. Click any image,
            then use arrows or the filmstrip to navigate between them:

            ![Step 1: Install](images/step1.svg){.lightbox group="tutorial"}

            ![Step 2: Configure](images/step2.svg){.lightbox group="tutorial"}

            ![Step 3: Build](images/step3.svg){.lightbox group="tutorial"}

            ![Step 4: Deploy](images/step4.svg){.lightbox group="tutorial"}

            ## Separate Gallery (Different Group)

            These images are in a different group and form their own gallery:

            ![Gallery A](images/mosaic-a.svg){.lightbox group="mosaic"}

            ![Gallery B](images/mosaic-b.svg){.lightbox group="mosaic"}

            ![Gallery C](images/mosaic-c.svg){.lightbox group="mosaic"}

            ![Gallery D](images/mosaic-d.svg){.lightbox group="mosaic"}

            ## Single Image (No Gallery)

            A standalone lightbox image without a group:

            ![Full Page](images/full-page.svg){.lightbox}
        """,
        "user_guide/05-all-features.qmd": """\
            ---
            title: "All Features Combined"
            lightbox: true
            ---

            ## Combined Demo

            This page uses `lightbox: true` (auto mode) and shows multiple features
            working together.

            ### Auto lightbox with caption

            ![Dashboard overview with all metrics visible](images/dashboard.light.svg)

            ### Gallery with dark variants

            These images form a gallery AND have dark-mode variants:

            ![Dashboard](images/dashboard.light.svg){group="dark-gallery" dark="images/dashboard.dark.svg"}

            ![UI Preview](images/ui-preview.svg){group="dark-gallery" dark="images/ui-preview-night.svg"}

            ### Deep-link test

            Navigate to this page with `#lightbox=gd-lb-1` appended to the URL
            to auto-open the first image's lightbox.

            ### Large image (tests scroll/zoom)

            ![Full application screenshot showing all panels](images/full-page.svg){caption="The full application with sidebar, main content, and inspector panel"}
        """,
        # ── Images ────────────────────────────────────────────────────
        **_IMAGES,
        **_UG_IMAGES,
    },
    # ── Expected outcomes ─────────────────────────────────────────────
    "expected": {
        "detected_name": "gdtest-lightbox",
        "detected_module": "gdtest_lightbox",
        "detected_parser": "numpy",
        "export_names": ["create_figure"],
        "num_exports": 1,
        "has_user_guide": True,
        "has_license_page": False,
        "has_citation_page": False,
        "coverage_exclude": ["nodoc", "bigcl", "supp"],
    },
}
