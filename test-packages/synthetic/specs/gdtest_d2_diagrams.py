"""
gdtest_d2_diagrams — Verify the build-time D2 diagram rendering.

Focus: `{d2}` (and plain ```d2) fenced blocks in user-guide pages. Exercises
       the build-time renderer (`great_docs._d2`) that shells out to the `d2`
       CLI, producing a *separate* light-theme and dark-theme SVG per diagram
       and swapping them via the site's `.light-mode-only` / `.dark-mode-only`
       classes.

Unlike Mermaid (rendered client-side by Quarto), D2 is pre-rendered before
Quarto sees the page, so the output is a `.d2-diagram` container wrapping two
`<img>` elements that reference generated `d2-<hash>-{light,dark}.svg` files.

Requires the `d2` binary on PATH; when it is missing the build degrades to the
original code block (so this site's dedicated tests skip rather than fail).
"""

SPEC = {
    "name": "gdtest_d2_diagrams",
    "description": "Build-time D2 diagrams with separate light/dark SVGs",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F1", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-d2-diagrams",
            "version": "1.0.0",
            "description": "A package demonstrating build-time D2 diagrams",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        # ── Python module (minimal, one documented function) ─────────────
        "gdtest_d2_diagrams/__init__.py": (
            '"""D2 diagrams demo package."""\n'
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
        # ── User guide: basic flowchart via the {d2} fence ───────────────
        "docs/user_guide/01-basic.qmd": (
            "---\n"
            "title: Basic Diagram\n"
            "---\n"
            "\n"
            "# Basic D2 Flowchart\n"
            "\n"
            "A simple decision flow, pre-rendered to light and dark SVGs at build time.\n"
            "\n"
            "```{d2}\n"
            "Start -> Decision\n"
            "Decision -> Action: Yes\n"
            "Decision -> End: No\n"
            "```\n"
        ),
        # ── User guide: options (#| directives) + a sketch look ──────────
        "docs/user_guide/02-options.qmd": (
            "---\n"
            "title: Diagram Options\n"
            "---\n"
            "\n"
            "# D2 Options\n"
            "\n"
            "A hand-drawn (sketch) diagram using the ELK layout engine, configured with\n"
            "`#|` option lines that are stripped before rendering.\n"
            "\n"
            "```{d2}\n"
            "#| sketch: true\n"
            "#| layout: elk\n"
            "#| pad: 40\n"
            "Idea -> Draft -> Review -> Publish\n"
            "```\n"
        ),
        # ── User guide: a sequence diagram + a plain ```d2 fence ─────────
        "docs/user_guide/03-sequence.qmd": (
            "---\n"
            "title: Sequence Diagram\n"
            "---\n"
            "\n"
            "# D2 Sequence Diagram\n"
            "\n"
            "Sequence diagrams use the same syntax with `shape: sequence_diagram`.\n"
            "\n"
            "```{d2}\n"
            "shape: sequence_diagram\n"
            "User -> CLI: great-docs build\n"
            "CLI -> Core: build()\n"
            "Core -> User: site ready\n"
            "```\n"
            "\n"
            "The plain ```` ```d2 ```` fence (no braces) is also recognized:\n"
            "\n"
            "```d2\n"
            "x -> y -> z\n"
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
            "user-guide/basic.html",
            "user-guide/options.html",
            "user-guide/sequence.html",
        ],
        "files_contain": {
            "user-guide/basic.html": [
                "d2-diagram",
                "light-mode-only",
                "dark-mode-only",
                "-light.svg",
                "-dark.svg",
            ],
            "user-guide/sequence.html": [
                "d2-diagram",
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
