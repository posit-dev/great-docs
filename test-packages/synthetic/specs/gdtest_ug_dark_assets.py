"""
gdtest_ug_dark_assets — Dark-mode image assets in user guide subdirectories.

Dimensions: M1
Focus: Verify that dark-mode image siblings (both naming-convention and
explicit `dark=` attribute) are copied to `_site` when images live in
non-`images/` asset subdirectories within the user guide (e.g.,
`assets/`, `figures/`).
"""


def _svg(width, height, bg, label, text_color="white"):
    """Generate a simple labeled SVG as a string."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
        f'<rect width="{width}" height="{height}" fill="{bg}" rx="8"/>'
        f'<text x="{width // 2}" y="{height // 2 + 6}" text-anchor="middle" '
        f'fill="{text_color}" font-size="16" font-family="sans-serif">{label}</text>'
        f"</svg>\n"
    )


SPEC = {
    "name": "gdtest_ug_dark_assets",
    "description": "User guide with dark-mode image assets in non-images/ subdirectories.",
    "dimensions": ["M1"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-ug-dark-assets",
            "version": "0.1.0",
            "description": "Test dark-mode asset copying in user guide subdirectories.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_ug_dark_assets/__init__.py": ('"""Test package for dark-mode asset copying."""\n'),
        "gdtest_ug_dark_assets/core.py": '''\
            """Core module."""


            def process(data: str) -> str:
                """Process input data.

                Parameters
                ----------
                data : str
                    The input data to process.

                Returns
                -------
                str
                    The processed output.
                """
                return data
        ''',
        "README.md": "# gdtest-ug-dark-assets\n\nTest dark-mode asset copying.\n",
        # ── User guide pages ─────────────────────────────────────────
        "user_guide/01-naming-convention.qmd": """\
            ---
            title: "Naming Convention Dark Mode"
            ---

            ## Auto-Detected Dark Variants

            Images using the `.light.ext` / `.dark.ext` naming convention
            swap automatically when the reader toggles dark mode.

            ![Sweep generator](assets/orientation/sweep-generator.light.svg){.lightbox}

            The dark variant `sweep-generator.dark.svg` should load in dark mode.

            ## Second Example

            ![Dashboard overview](assets/charts/dashboard.light.svg){.lightbox}
        """,
        "user_guide/02-explicit-dark.qmd": """\
            ---
            title: "Explicit Dark Attribute"
            ---

            ## Explicit dark= Attribute

            Use `dark="..."` to point at a non-conventionally named dark variant:

            ![Component diagram](assets/diagrams/component-day.svg){.lightbox dark="assets/diagrams/component-night.svg"}

            ## Mixed: Convention + Explicit

            Convention-based (auto-detected):

            ![Flow chart](assets/diagrams/flow.light.svg){.lightbox}

            Explicit override on a convention-named file:

            ![Dashboard overview](assets/charts/dashboard.light.svg){.lightbox dark="assets/charts/dashboard-custom-dark.svg"}
        """,
        "user_guide/03-in-images-dir.qmd": """\
            ---
            title: "Images in Standard Directory"
            ---

            ## Standard images/ Directory

            Images in `images/` have always worked. This page confirms that:

            ![Status panel](images/status.light.svg){.lightbox}
        """,
        # ── Asset files: assets/orientation/ ──────────────────────────
        "user_guide/assets/orientation/sweep-generator.light.svg": _svg(
            600, 400, "#f0f4f8", "Sweep Generator (Light)", "#333"
        ),
        "user_guide/assets/orientation/sweep-generator.dark.svg": _svg(
            600, 400, "#1a1a2e", "Sweep Generator (Dark)"
        ),
        # ── Asset files: assets/charts/ ──────────────────────────────
        "user_guide/assets/charts/dashboard.light.svg": _svg(
            700, 450, "#ffffff", "Dashboard (Light)", "#333"
        ),
        "user_guide/assets/charts/dashboard.dark.svg": _svg(
            700, 450, "#16213e", "Dashboard (Dark)"
        ),
        "user_guide/assets/charts/dashboard-custom-dark.svg": _svg(
            700, 450, "#0d1117", "Dashboard (Custom Dark)"
        ),
        # ── Asset files: assets/diagrams/ ────────────────────────────
        "user_guide/assets/diagrams/component-day.svg": _svg(
            600, 380, "#fafafa", "Component Diagram (Day)", "#333"
        ),
        "user_guide/assets/diagrams/component-night.svg": _svg(
            600, 380, "#0f3460", "Component Diagram (Night)"
        ),
        "user_guide/assets/diagrams/flow.light.svg": _svg(
            500, 350, "#f5f5f5", "Flow Chart (Light)", "#333"
        ),
        "user_guide/assets/diagrams/flow.dark.svg": _svg(500, 350, "#1e1e2f", "Flow Chart (Dark)"),
        # ── Asset files: images/ (standard dir, for comparison) ──────
        "user_guide/images/status.light.svg": _svg(
            500, 300, "#e8f0fe", "Status Panel (Light)", "#333"
        ),
        "user_guide/images/status.dark.svg": _svg(500, 300, "#1a1a2e", "Status Panel (Dark)"),
    },
    "expected": {
        "detected_name": "gdtest-ug-dark-assets",
        "detected_module": "gdtest_ug_dark_assets",
        "detected_parser": "numpy",
        "has_user_guide": True,
        "files_exist": [
            # User guide pages rendered
            "great-docs/user-guide/naming-convention.html",
            "great-docs/user-guide/explicit-dark.html",
            "great-docs/user-guide/in-images-dir.html",
            # Light images must be in _site
            "great-docs/_site/user-guide/assets/orientation/sweep-generator.light.svg",
            "great-docs/_site/user-guide/assets/charts/dashboard.light.svg",
            "great-docs/_site/user-guide/assets/diagrams/component-day.svg",
            "great-docs/_site/user-guide/assets/diagrams/flow.light.svg",
            "great-docs/_site/user-guide/images/status.light.svg",
            # Dark siblings must ALSO be in _site (this is the bug fix)
            "great-docs/_site/user-guide/assets/orientation/sweep-generator.dark.svg",
            "great-docs/_site/user-guide/assets/charts/dashboard.dark.svg",
            "great-docs/_site/user-guide/assets/charts/dashboard-custom-dark.svg",
            "great-docs/_site/user-guide/assets/diagrams/component-night.svg",
            "great-docs/_site/user-guide/assets/diagrams/flow.dark.svg",
            "great-docs/_site/user-guide/images/status.dark.svg",
        ],
        "coverage_exclude": [
            "ref",
            "nodoc",
            "bigcl",
            "ug",
            "supp",
            "title",
            "badge",
            "sig",
            "desc",
            "param",
            "pmatch",
            "ret",
            "refidx",
            "sechdg",
            "sbar",
            "sbsec",
            "hdg",
        ],
    },
}
