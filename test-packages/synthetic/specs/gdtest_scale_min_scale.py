"""
gdtest_scale_min_scale — Minimum-scale thresholds for scale-to-fit.

Dimensions: G7, M4, N1
Focus: Exercises every variant of ``scale_to_fit_min_scale``:

       1. **Global keyword** (``scale_to_fit_min_scale: "desktop"``):
          On viewports ≤ 992 px the element scrolls instead of scaling.
       2. **Page keyword override** — each keyword tested on its own page:
          - ``mobile``  (≤ 576 px)
          - ``tablet``  (≤ 768 px)
          - ``desktop`` (≤ 992 px)
       3. **Page float override** — ``scale-to-fit-min-scale: 0.35``
          overrides the global keyword with a fractional threshold.
       4. **No override page** — inherits the global ``"desktop"`` keyword.

       All pages share the same wide GT table (id ``#stf_wide``) so the
       only variable is the min-scale setting.

       Verification targets:
       - ``data-min-scale`` attribute on global ``gd-scale-to-fit`` meta
       - ``data-min-scale`` attribute on page-level ``gd-scale-to-fit-page``
       - keyword values preserved verbatim (``mobile``, ``tablet``, ``desktop``)
       - float value preserved (``0.35``)
       - pages without frontmatter override have no ``gd-scale-to-fit-page``
"""

SPEC = {
    "name": "gdtest_scale_min_scale",
    "description": "Minimum-scale keyword and float thresholds for scale-to-fit",
    "dimensions": ["G7", "M4", "N1"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-scale-min-scale",
            "version": "0.1.0",
            "description": "Test min-scale thresholds for scale-to-fit",
            "dependencies": ["great_tables"],
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "scale_to_fit": ["#stf_wide", "#stf_styled", "#summary_card"],
        "scale_to_fit_min_scale": "desktop",
    },
    "files": {
        # ── Project root ──────────────────────────────────────────────────
        "README.md": (
            "# gdtest-scale-min-scale\n\n"
            "Test min-scale keyword and float thresholds for scale-to-fit.\n"
        ),
        # ── Package source ────────────────────────────────────────────────
        "gdtest_scale_min_scale/__init__.py": '''\
            """A test package for scale-to-fit min-scale thresholds."""

            __version__ = "0.1.0"
            __all__ = [
                "make_wide_table",
                "make_narrow_table",
                "make_styled_table",
                "SummaryCard",
            ]


            def make_wide_table():
                """
                Create a wide GT table with 14 columns.

                Returns
                -------
                GT
                    A GT table that overflows most containers.

                Examples
                --------
                ```{python}
                from gdtest_scale_min_scale import make_wide_table
                make_wide_table()
                ```
                """
                from great_tables import GT
                import pandas as pd

                df = pd.DataFrame({
                    f"V{i:02d}": [f"r{r}c{i}" for r in range(4)]
                    for i in range(1, 15)
                })
                return (
                    GT(df, id="stf_wide")
                    .tab_header(title="Wide Table (14 cols)")
                    .cols_width(**{f"V{i:02d}": "100px" for i in range(1, 15)})
                    .tab_options(quarto_disable_processing=True)
                )


            def make_narrow_table():
                """
                Create a narrow 3-column GT table (always fits).

                Returns
                -------
                GT
                    A small table.
                """
                from great_tables import GT
                import pandas as pd

                df = pd.DataFrame({
                    "A": ["x", "y"],
                    "B": [1, 2],
                    "C": ["ok", "ok"],
                })
                return (
                    GT(df, id="stf_narrow")
                    .tab_header(title="Narrow Table")
                    .tab_options(quarto_disable_processing=True)
                )


            def make_styled_table():
                """
                Create a styled GT table with 10 columns and color formatting.

                Returns
                -------
                GT
                    A moderately wide GT table with styled cells.
                """
                from great_tables import GT, style, loc
                import pandas as pd

                df = pd.DataFrame({
                    f"S{i:02d}": [round(i * 3.7 + r * 1.1, 1) for r in range(5)]
                    for i in range(1, 11)
                })
                return (
                    GT(df, id="stf_styled")
                    .tab_header(
                        title="Styled Table (10 cols)",
                        subtitle="With cell highlighting",
                    )
                    .cols_width(**{f"S{i:02d}": "110px" for i in range(1, 11)})
                    .tab_style(
                        style=style.fill(color="#e8f5e9"),
                        locations=loc.body(columns="S01"),
                    )
                    .tab_options(quarto_disable_processing=True)
                )


            class SummaryCard:
                """
                A wide HTML summary card with ``_repr_html_``.

                Renders a fixed-width HTML block useful for testing
                scale-to-fit on non-GT ``_repr_html_`` objects.

                Parameters
                ----------
                card_id
                    HTML ``id`` attribute.
                width
                    CSS width (e.g., ``"1400px"``).
                """

                def __init__(self, card_id: str = "summary_card", width: str = "1400px"):
                    self.card_id = card_id
                    self.width = width

                def _repr_html_(self) -> str:
                    """Render as a wide HTML card."""
                    return (
                        f'<div id="{self.card_id}" '
                        f'style="width:{self.width};background:linear-gradient(135deg,#e3f2fd,#f3e5f5);'
                        f'border:2px solid #7e57c2;border-radius:8px;padding:20px;'
                        f'font-family:system-ui;">'
                        f'<strong>SummaryCard</strong> &mdash; '
                        f'id: {self.card_id}, width: {self.width}'
                        f'</div>'
                    )
        ''',
        # ── Page 1: No override (inherits global "desktop") ──────────────
        "user_guide/01-no-override.qmd": (
            "---\n"
            "title: No Override (Global Desktop)\n"
            "---\n"
            "\n"
            'This page inherits the global `scale_to_fit_min_scale: "desktop"`\n'
            "setting. On viewports ≤ 992 px, the table scrolls.\n"
            "\n"
            "## Wide GT Table\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from gdtest_scale_min_scale import make_wide_table\n"
            "make_wide_table()\n"
            "```\n"
            "\n"
            "## Styled GT Table\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from gdtest_scale_min_scale import make_styled_table\n"
            "make_styled_table()\n"
            "```\n"
            "\n"
            "## Narrow GT Table (not targeted)\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from gdtest_scale_min_scale import make_narrow_table\n"
            "make_narrow_table()\n"
            "```\n"
        ),
        # ── Page 2: mobile keyword ───────────────────────────────────────
        "user_guide/02-mobile.qmd": (
            "---\n"
            "title: Mobile Keyword\n"
            "scale-to-fit:\n"
            '  - "#stf_wide"\n'
            '  - "#summary_card"\n'
            "scale-to-fit-min-scale: mobile\n"
            "---\n"
            "\n"
            "This page overrides with `scale-to-fit-min-scale: mobile`.\n"
            "Scrolls only on viewports ≤ 576 px.\n"
            "\n"
            "## Wide GT Table\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from gdtest_scale_min_scale import make_wide_table\n"
            "make_wide_table()\n"
            "```\n"
            "\n"
            "## Summary Card (non-GT)\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from gdtest_scale_min_scale import SummaryCard\n"
            "SummaryCard(card_id='summary_card', width='1400px')\n"
            "```\n"
        ),
        # ── Page 3: tablet keyword ───────────────────────────────────────
        "user_guide/03-tablet.qmd": (
            "---\n"
            "title: Tablet Keyword\n"
            "scale-to-fit:\n"
            '  - "#stf_wide"\n'
            '  - "#stf_styled"\n'
            "scale-to-fit-min-scale: tablet\n"
            "---\n"
            "\n"
            "This page overrides with `scale-to-fit-min-scale: tablet`.\n"
            "Scrolls on viewports ≤ 768 px.\n"
            "\n"
            "## Wide GT Table\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from gdtest_scale_min_scale import make_wide_table\n"
            "make_wide_table()\n"
            "```\n"
            "\n"
            "## Styled GT Table\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from gdtest_scale_min_scale import make_styled_table\n"
            "make_styled_table()\n"
            "```\n"
        ),
        # ── Page 4: desktop keyword ──────────────────────────────────────
        "user_guide/04-desktop.qmd": (
            "---\n"
            "title: Desktop Keyword\n"
            "scale-to-fit:\n"
            '  - "#stf_wide"\n'
            "scale-to-fit-min-scale: desktop\n"
            "---\n"
            "\n"
            "This page explicitly sets `scale-to-fit-min-scale: desktop`\n"
            "(same as the global default, but declared per-page).\n"
            "Scrolls on viewports ≤ 992 px.\n"
            "\n"
            "## Wide GT Table\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from gdtest_scale_min_scale import make_wide_table\n"
            "make_wide_table()\n"
            "```\n"
        ),
        # ── Page 5: float override ───────────────────────────────────────
        "user_guide/05-float-override.qmd": (
            "---\n"
            "title: Float Override\n"
            "scale-to-fit:\n"
            '  - "#stf_wide"\n'
            '  - "#stf_styled"\n'
            '  - "#summary_card"\n'
            "scale-to-fit-min-scale: 0.35\n"
            "---\n"
            "\n"
            "This page overrides with a numeric value: `0.35`.\n"
            "If the computed scale drops below 35%, the table scrolls.\n"
            "\n"
            "## Wide GT Table\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from gdtest_scale_min_scale import make_wide_table\n"
            "make_wide_table()\n"
            "```\n"
            "\n"
            "## Styled GT Table\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from gdtest_scale_min_scale import make_styled_table\n"
            "make_styled_table()\n"
            "```\n"
            "\n"
            "## Summary Card (non-GT)\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from gdtest_scale_min_scale import SummaryCard\n"
            "SummaryCard(card_id='summary_card', width='1400px')\n"
            "```\n"
        ),
    },
    "expected": {
        "user_guide_pages": [
            "no-override.html",
            "mobile.html",
            "tablet.html",
            "desktop.html",
            "float-override.html",
        ],
        "reference_pages": [
            "make_wide_table.html",
            "make_narrow_table.html",
            "make_styled_table.html",
            "SummaryCard.html",
        ],
        "exports": [
            "make_wide_table",
            "make_narrow_table",
            "make_styled_table",
            "SummaryCard",
        ],
        # ── Min-scale verification keys ───────────────────────────────────
        # Global keyword (all pages get this on gd-scale-to-fit)
        "global_min_scale": "desktop",
        # Per-page overrides (only these pages have gd-scale-to-fit-page)
        "page_min_scales": {
            "mobile.html": "mobile",
            "tablet.html": "tablet",
            "desktop.html": "desktop",
            "float-override.html": "0.35",
        },
        # Pages that should NOT have gd-scale-to-fit-page
        "no_page_override": ["no-override.html"],
    },
}
