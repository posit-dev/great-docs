"""
gdtest_lightbox — Showcase the gd-lightbox extension.

Dimensions: A1, B1, C1, D1, E6, F1, G1, H7
Focus: Demonstrate lightbox with multiple modes: explicit class, auto mode,
       dark-mode variants, galleries, captions, credits, grouped images,
       comparison slider, annotations, toolbar actions, deep-linking,
       responsive srcset, and the .nolightbox opt-out.
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


def _svg_gradient(width, height, color1, color2, label, text_color="white"):
    """Generate an SVG with a linear gradient background."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
        f'<defs><linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">'
        f'<stop offset="0%" stop-color="{color1}"/>'
        f'<stop offset="100%" stop-color="{color2}"/>'
        f"</linearGradient></defs>"
        f'<rect width="{width}" height="{height}" fill="url(#g)" rx="8"/>'
        f'<text x="{width // 2}" y="{height // 2 + 6}" text-anchor="middle" '
        f'fill="{text_color}" font-size="16" font-family="sans-serif">{label}</text>'
        f"</svg>\n"
    )


def _svg_panels(width, height, panels, label):
    """Generate an SVG with multiple colored panels (simulates a complex UI)."""
    panel_w = width // len(panels)
    rects = "".join(
        f'<rect x="{i * panel_w}" width="{panel_w}" height="{height}" fill="{c}"/>'
        for i, c in enumerate(panels)
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
        f"{rects}"
        f'<text x="{width // 2}" y="{height // 2 + 6}" text-anchor="middle" '
        f'fill="white" font-size="16" font-family="sans-serif">{label}</text>'
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
    # Responsive srcset variants (simulate different resolutions)
    "user_guide/images/chart-400.svg": _svg(400, 280, "#8e44ad", "Chart 400w"),
    "user_guide/images/chart-800.svg": _svg(800, 560, "#8e44ad", "Chart 800w"),
    "user_guide/images/chart-1600.svg": _svg(1600, 1120, "#8e44ad", "Chart 1600w (Full)"),
    "user_guide/images/diagram-2400.svg": _svg(2400, 1500, "#2c3e50", "Diagram 2400w (Full Res)"),
    # Multi-panel UI screenshots (for annotation demos)
    "user_guide/images/app-layout.svg": _svg_panels(
        900, 500, ["#2c3e50", "#34495e", "#3d566e", "#ecf0f1"], "App Layout"
    ),
    "user_guide/images/app-layout.dark.svg": _svg_panels(
        900, 500, ["#1a1a2e", "#16213e", "#0f3460", "#1a1a2e"], "App Layout (Dark)"
    ),
    # Gradient images for visual variety
    "user_guide/images/hero-gradient.svg": _svg_gradient(
        800, 400, "#667eea", "#764ba2", "Hero Section"
    ),
    "user_guide/images/hero-gradient.dark.svg": _svg_gradient(
        800, 400, "#2d1b69", "#1a0533", "Hero Section (Dark)"
    ),
    # Version comparison images (more realistic before/after)
    "user_guide/images/v1-table.svg": _svg(600, 350, "#95a5a6", "Table v1 — Plain", "#fff"),
    "user_guide/images/v2-table.svg": _svg_gradient(
        600, 350, "#3498db", "#2980b9", "Table v2 — Styled"
    ),
    "user_guide/images/v1-sidebar.svg": _svg(300, 500, "#bdc3c7", "Sidebar v1", "#333"),
    "user_guide/images/v2-sidebar.svg": _svg_gradient(300, 500, "#2ecc71", "#27ae60", "Sidebar v2"),
    # Pipeline/flow diagram for multi-annotation demo
    "user_guide/images/pipeline.svg": _svg(
        1000, 300, "#2c3e50", "Data Pipeline: Ingest → Process → Store → Serve"
    ),
    # Toolbar demo images (named clearly for the toolbar page)
    "user_guide/images/api-reference.svg": _svg(700, 450, "#1e3a5f", "API Reference Page"),
    "user_guide/images/config-panel.svg": _svg(600, 400, "#4a1e5f", "Configuration Panel"),
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

            ## Gallery with Loop Disabled

            This gallery stops at the first and last image (no wrap-around):

            ![Step 1](images/step1.svg){.lightbox group="no-loop" loop="false"}

            ![Step 2](images/step2.svg){.lightbox group="no-loop" loop="false"}

            ![Step 3](images/step3.svg){.lightbox group="no-loop" loop="false"}

            ## Auto-Advancing Gallery

            This gallery auto-advances every 3 seconds (with loop):

            ![Step 1](images/step1.svg){.lightbox group="autoplay" autoplay="3s"}

            ![Step 2](images/step2.svg){.lightbox group="autoplay" autoplay="3s"}

            ![Step 3](images/step3.svg){.lightbox group="autoplay" autoplay="3s"}

            ![Step 4](images/step4.svg){.lightbox group="autoplay" autoplay="3s"}

            ## Auto-Advancing Without Loop

            Auto-advances every 2 seconds and stops at the last image:

            ![Gallery A](images/mosaic-a.svg){.lightbox group="autoplay-nol" autoplay="2s" loop="false"}

            ![Gallery B](images/mosaic-b.svg){.lightbox group="autoplay-nol" autoplay="2s" loop="false"}

            ![Gallery C](images/mosaic-c.svg){.lightbox group="autoplay-nol" autoplay="2s" loop="false"}

            ## Single Image (No Gallery)

            A standalone lightbox image without a group:

            ![Full Page](images/full-page.svg){.lightbox}
        """,
        "user_guide/05-responsive-srcset.qmd": """\
            ---
            title: "Responsive Images"
            ---

            ## Responsive srcset

            The thumbnail uses a responsive `srcset` so the browser picks the best
            size for the viewport. When clicked, the lightbox loads the highest-
            resolution source automatically.

            ![Revenue Chart](images/chart-400.svg){.lightbox srcset="images/chart-400.svg 400w, images/chart-800.svg 800w, images/chart-1600.svg 1600w" sizes="(max-width: 600px) 400px, 800px"}

            ## Explicit full-src Override

            Use `full-src` to point the lightbox at a specific high-res file
            regardless of what `srcset` contains:

            ![Architecture Diagram](images/diagram.svg){.lightbox full-src="images/diagram-2400.svg"}

            ## Srcset with Dark Mode

            Responsive images can also combine with dark-mode variants. The lightbox
            will prefer the dark variant when in dark mode:

            ![Dashboard](images/dashboard.light.svg){.lightbox srcset="images/dashboard.light.svg 700w" dark="images/dashboard.dark.svg"}
        """,
        "user_guide/06-comparison.qmd": """\
            ---
            title: "Image Comparison"
            ---

            ## Shortcode Syntax

            Use the `{{< compare >}}` shortcode for a quick before/after slider:

            {{< compare before="images/before.svg" after="images/after.svg" >}}

            ## Custom Labels

            {{< compare before="images/before.svg" after="images/after.svg" label-before="v0.8" label-after="v0.9" >}}

            ## Custom Start Position

            Start the divider at 30% (showing mostly the "after" image):

            {{< compare before="images/before.svg" after="images/after.svg" start="30" >}}

            ## Vertical Split

            {{< compare before="images/before.svg" after="images/after.svg" direction="vertical" >}}

            ## Fenced Div Syntax

            The fenced div syntax offers more control:

            ::: {.lightbox-compare}
            ![Before](images/before.svg)
            ![After](images/after.svg)
            :::

            ## Fenced Div with Options

            ::: {.lightbox-compare direction="vertical" start="70"}
            ![Old Design](images/mosaic-a.svg)
            ![New Design](images/mosaic-c.svg)
            :::
        """,
        "user_guide/07-annotations.qmd": """\
            ---
            title: "Image Annotations"
            ---

            ## Basic Annotations

            Numbered markers are positioned over the image using percentage
            coordinates. Hover or click a marker to see its description:

            ![Architecture Diagram](images/full-page.svg){.lightbox annotations='[{"x": 15, "y": 20, "label": "1", "text": "Navigation sidebar with collapsible sections"}, {"x": 50, "y": 35, "label": "2", "text": "Main content area with rendered documentation"}, {"x": 85, "y": 50, "label": "3", "text": "Table of contents for the current page"}]'}

            ## Custom Labels

            Annotations can use any short label text (letters, symbols):

            ![Dashboard](images/dashboard.light.svg){.lightbox annotations='[{"x": 25, "y": 30, "label": "A", "text": "Revenue metrics widget"}, {"x": 75, "y": 30, "label": "B", "text": "User growth chart"}, {"x": 50, "y": 70, "label": "C", "text": "Recent activity feed"}]'}

            ## Custom Marker Colors

            Individual markers can have custom colors for categorization:

            ![Step Diagram](images/diagram.svg){.lightbox annotations='[{"x": 20, "y": 50, "label": "1", "text": "Input stage", "color": "#e74c3c"}, {"x": 50, "y": 50, "label": "2", "text": "Processing stage", "color": "#f39c12"}, {"x": 80, "y": 50, "label": "3", "text": "Output stage", "color": "#27ae60"}]'}

            ## Multi-Panel Layout Annotations

            A complex UI with annotations pointing to specific panels:

            ![App Layout](images/app-layout.svg){.lightbox dark="images/app-layout.dark.svg" annotations='[{"x": 12, "y": 50, "label": "1", "text": "Sidebar navigation — collapsible tree of pages", "color": "#3498db"}, {"x": 38, "y": 30, "label": "2", "text": "Document body — rendered Markdown content", "color": "#2ecc71"}, {"x": 62, "y": 50, "label": "3", "text": "Code panel — interactive examples", "color": "#e67e22"}, {"x": 88, "y": 30, "label": "4", "text": "On This Page — auto-generated TOC", "color": "#9b59b6"}]'}

            ## Pipeline Diagram

            Annotations along a horizontal data flow:

            ![Data Pipeline](images/pipeline.svg){.lightbox annotations='[{"x": 12, "y": 50, "label": "①", "text": "Ingest: raw data arrives via API or file upload"}, {"x": 37, "y": 50, "label": "②", "text": "Process: validation, transformation, enrichment"}, {"x": 62, "y": 50, "label": "③", "text": "Store: write to database and search index"}, {"x": 87, "y": 50, "label": "④", "text": "Serve: API and documentation site consume data"}]'}

            ## Annotations with Dark Mode

            Annotations work with dark-mode variant images. The markers adjust
            their appearance automatically:

            ![UI Preview](images/ui-preview.svg){.lightbox dark="images/ui-preview-night.svg" annotations='[{"x": 50, "y": 25, "label": "H", "text": "Header with navigation"}, {"x": 50, "y": 75, "label": "F", "text": "Footer with links"}]'}
        """,
        "user_guide/08-toolbar-links.qmd": """\
            ---
            title: "Toolbar & Deep Links"
            ---

            ## Toolbar Actions

            When the lightbox is open, a toolbar provides quick actions. Hover over
            the lightbox image to reveal it (auto-hides after 3 seconds).

            ### Copy to Clipboard

            Click the **copy** button (clipboard icon) to copy the full-resolution
            image directly to your clipboard — paste it into Slack, a bug report,
            or a presentation:

            ![API Reference Page](images/api-reference.svg){.lightbox caption="Copy this image to share the API reference layout"}

            ### Download

            Click the **download** button (arrow icon) to save the full-resolution
            image with a meaningful filename derived from the alt text:

            ![Configuration Panel](images/config-panel.svg){.lightbox caption="Download this image for your slide deck"}

            ### Copy Link

            Click the **link** button (chain icon) to copy a URL that opens this
            page with the lightbox already open at this exact image:

            ![Full Application](images/full-page.svg){.lightbox caption="Share this deep link with your team"}

            ## Deep Linking

            ### How It Works

            Each lightbox image gets a unique ID (e.g., `gd-lb-1`). The URL
            fragment `#lightbox=gd-lb-N` opens the lightbox at that image on
            page load.

            Try these links (they point to images on this page):

            - [Open the API Reference image](#lightbox=gd-lb-1)
            - [Open the Configuration Panel](#lightbox=gd-lb-2)
            - [Open the Full Application image](#lightbox=gd-lb-3)

            ### Gallery Deep Links

            Deep links also work within galleries. Click the link below to open
            the gallery at a specific image:

            ![Step 1](images/step1.svg){.lightbox group="deep-demo"}

            ![Step 2](images/step2.svg){.lightbox group="deep-demo"}

            ![Step 3](images/step3.svg){.lightbox group="deep-demo"}

            ![Step 4](images/step4.svg){.lightbox group="deep-demo"}

            - [Open gallery at Step 3](#lightbox=gd-lb-7)
        """,
        "user_guide/09-showcase.qmd": """\
            ---
            title: "Full Showcase"
            lightbox: true
            ---

            ## Complete Feature Showcase

            This page demonstrates all gd-lightbox capabilities working together.
            `lightbox: true` is set in the page YAML so all block images are
            automatically enhanced.

            ---

            ### Auto Mode + Captions

            All block-level images get lightbox treatment automatically. Captions
            and credits appear in the lightbox overlay:

            ![Hero section with gradient background](images/hero-gradient.svg){caption="The hero section uses a vibrant gradient that adapts to dark mode" credit="Design Team"}

            ---

            ### Dark-Mode Variants in Auto Mode

            These images swap automatically when the user toggles the theme:

            ![App Layout](images/app-layout.svg){dark="images/app-layout.dark.svg" caption="Multi-panel application interface"}

            ![Hero Gradient](images/hero-gradient.svg){dark="images/hero-gradient.dark.svg"}

            ---

            ### Gallery + Dark Variants + Autoplay

            A gallery where each image has a dark variant, auto-advancing every
            4 seconds:

            ![Dashboard](images/dashboard.light.svg){group="showcase-gallery" dark="images/dashboard.dark.svg" autoplay="4s" caption="Dashboard metrics"}

            ![App Layout](images/app-layout.svg){group="showcase-gallery" dark="images/app-layout.dark.svg" autoplay="4s" caption="Application layout"}

            ![Hero Section](images/hero-gradient.svg){group="showcase-gallery" dark="images/hero-gradient.dark.svg" autoplay="4s" caption="Landing page hero"}

            ---

            ### Annotated Gallery

            A gallery where each image also has annotations. Click any image,
            then explore the markers:

            ![App Layout](images/app-layout.svg){group="annotated" annotations='[{"x": 12, "y": 50, "label": "1", "text": "Sidebar"}, {"x": 50, "y": 50, "label": "2", "text": "Content"}, {"x": 88, "y": 50, "label": "3", "text": "TOC"}]'}

            ![Pipeline](images/pipeline.svg){group="annotated" annotations='[{"x": 25, "y": 50, "label": "A", "text": "Input"}, {"x": 75, "y": 50, "label": "B", "text": "Output"}]'}

            ---

            ### Before/After Comparisons

            #### Table Redesign

            {{< compare before="images/v1-table.svg" after="images/v2-table.svg" label-before="v1 Plain" label-after="v2 Styled" >}}

            #### Sidebar Update

            {{< compare before="images/v1-sidebar.svg" after="images/v2-sidebar.svg" label-before="Old" label-after="New" direction="vertical" >}}

            ---

            ### Responsive Image + Annotations

            High-res source loaded in the lightbox, with annotations visible
            on the thumbnail:

            ![Revenue Chart](images/chart-400.svg){srcset="images/chart-400.svg 400w, images/chart-800.svg 800w, images/chart-1600.svg 1600w" sizes="(max-width: 600px) 400px, 800px" annotations='[{"x": 30, "y": 50, "label": "Q3", "text": "Revenue dipped in Q3 due to seasonal factors", "color": "#e74c3c"}, {"x": 70, "y": 30, "label": "Q4", "text": "Strong recovery in Q4 with 42% growth", "color": "#27ae60"}]'}

            ---

            ### Multiple Comparison Styles

            ::: {.lightbox-compare start="25"}
            ![Light App](images/app-layout.svg)
            ![Dark App](images/app-layout.dark.svg)
            :::

            ---

            ### Deep Link Test

            Navigate to this page with `#lightbox=gd-lb-1` appended to the URL
            to auto-open the hero section image.

            ### Large Image with Annotations + Caption

            ![Full application screenshot](images/full-page.svg){caption="Complete application with all panels visible — use the annotation markers to explore each section" credit="Engineering Team" annotations='[{"x": 20, "y": 25, "label": "①", "text": "File tree and navigation", "color": "#3498db"}, {"x": 50, "y": 50, "label": "②", "text": "Main editing area", "color": "#e74c3c"}, {"x": 80, "y": 75, "label": "③", "text": "Terminal and output panel", "color": "#f39c12"}]'}
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
