"""
gdtest_mermaid — Verify Mermaid diagram layout, with and without captions.

Focus: `{mermaid}` cells in user-guide pages, rendered client-side by Quarto.
       Covers a wide diagram with a cross-referenceable `fig-cap` (wrapped by
       Quarto in a `.quarto-float` div), a small diagram with an unlabeled
       `fig-cap` (wrapped in `.quarto-figure-default`), and a diagram with no
       caption.

Regression target (issue #361): a captioned Mermaid figure must stack its
caption *under* the diagram and let a wide diagram use the full text column,
rather than placing the caption to the right of a shrunken SVG.
"""

SPEC = {
    "name": "gdtest_mermaid",
    "description": "Mermaid diagrams with and without figure captions",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F1", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-mermaid",
            "version": "1.0.0",
            "description": "A package demonstrating Mermaid diagrams",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        # ── Python module (minimal, one documented function) ─────────────
        "gdtest_mermaid/__init__.py": (
            '"""Mermaid diagrams demo package."""\n'
            "\n"
            '__version__ = "1.0.0"\n'
            '__all__ = ["greet"]\n'
            "\n"
            "\n"
            "def greet(name: str) -> str:\n"
            '    """Return a friendly greeting.\n'
            "\n"
            "    Parameters\n"
            "    ----------\n"
            "    name\n"
            "        Who to greet.\n"
            "\n"
            "    Returns\n"
            "    -------\n"
            "    str\n"
            "        The greeting.\n"
            '    """\n'
            '    return f"Hello, {name}!"\n'
        ),
        # ── User guide: captioned and uncaptioned diagrams ───────────────
        "docs/user_guide/01-captions.qmd": (
            "---\n"
            "title: Captions\n"
            "---\n"
            "\n"
            "# Mermaid Captions\n"
            "\n"
            "A wide pipeline flowchart with a cross-referenceable caption\n"
            "(see @fig-pipeline). It should span the text column, with the caption\n"
            "underneath.\n"
            "\n"
            "```{mermaid}\n"
            "%%| label: fig-pipeline\n"
            '%%| fig-cap: "The model-fitting pipeline, from raw data to a report."\n'
            "flowchart LR\n"
            "  A[Load data] --> B[Validate] --> C[Fit model] --> D[Evaluate] --> E[Report]\n"
            "  C --> F[Diagnostics] --> D\n"
            "```\n"
            "\n"
            "A small diagram with an unlabeled caption keeps its natural size:\n"
            "\n"
            "```{mermaid}\n"
            '%%| fig-cap: "A tiny two-node diagram."\n'
            "flowchart LR\n"
            "  A --> B\n"
            "```\n"
            "\n"
            "A diagram with no caption at all:\n"
            "\n"
            "```{mermaid}\n"
            "flowchart TD\n"
            "  Start --> Decision{OK?}\n"
            "  Decision -->|Yes| Done\n"
            "  Decision -->|No| Start\n"
            "```\n"
        ),
    },
    "config": {
        "dark_mode": True,
    },
    "expected": {
        "files_exist": [
            "reference/index.html",
            "reference/greet.html",
            "user-guide/captions.html",
        ],
        "files_contain": {
            "user-guide/captions.html": [
                "fig-pipeline",
                "The model-fitting pipeline",
                "A tiny two-node diagram.",
                "mermaid",
            ],
        },
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
            "sbsec",
            "hdg",
        ],
    },
}
