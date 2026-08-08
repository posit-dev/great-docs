"""
gdtest_marimo — Verify the marimo notebook integration (islands).

Focus: The `{{< marimo >}}` shortcode + `marimo: true` config. Exercises the
       build-time island generation (MarimoIslandGenerator) and the browser-side
       @marimo-team/islands runtime.

Uses a lightweight, dependency-free notebook (marimo only, no micropip installs)
so the WASM kernel boots fast and reliably during iteration — this isolates the
island *rendering mechanics* from package-install concerns.
"""

# A minimal reactive marimo notebook: a slider whose value drives a dependent
# markdown cell. Demonstrates island rendering + reactivity with no external deps.
_DEMO_NOTEBOOK = '''# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
# ]
# ///

import marimo

app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return (mo,)


@app.cell
def __(mo):
    mo.md(
        """
        # Interactive Demo

        Drag the slider below — the output updates reactively.
        """
    )
    return


@app.cell
def __(mo):
    n = mo.ui.slider(1, 20, value=5, label="How many?")
    n
    return (n,)


@app.cell
def __(mo, n):
    mo.md(f"You chose **{n.value}**. Its square is **{n.value ** 2}**.")
    return


if __name__ == "__main__":
    app.run()
'''

SPEC = {
    "name": "gdtest_marimo",
    "description": "Interactive marimo notebook islands via the {{< marimo >}} shortcode",
    "dimensions": ["A1", "B1", "C4", "D2", "E6", "F1", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-marimo",
            "version": "1.0.0",
            "description": "A package demonstrating embedded marimo notebooks",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        # ── Python module (minimal) ──────────────────────────────────────
        "gdtest_marimo/__init__.py": (
            '"""Marimo islands demo package."""\n'
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
        # ── The marimo notebook the shortcode embeds ─────────────────────
        "notebooks/demo.py": _DEMO_NOTEBOOK,
        # ── User guide: island mode (default) ────────────────────────────
        "user_guide/01-islands.qmd": (
            "---\n"
            "title: Marimo Islands\n"
            "---\n"
            "\n"
            "# Interactive Notebook (Island Mode)\n"
            "\n"
            "The notebook below is embedded with the default island mode. Its cells\n"
            "run in the browser via WebAssembly (Pyodide).\n"
            "\n"
            '{{< marimo file="notebooks/demo.py" >}}\n'
        ),
        # ── User guide: hide code (outputs only) ─────────────────────────
        "user_guide/02-nocode.qmd": (
            "---\n"
            "title: Outputs Only\n"
            "---\n"
            "\n"
            "# Outputs Only (show-code=false)\n"
            "\n"
            "The same notebook, rendered with the source hidden — useful for\n"
            "dashboard-style presentations.\n"
            "\n"
            '{{< marimo file="notebooks/demo.py" show-code="false" >}}\n'
        ),
        # ── User guide: iframe mode (full notebook, self-hosted WASM) ─────
        "user_guide/03-iframe.qmd": (
            "---\n"
            "title: Iframe Mode\n"
            "---\n"
            "\n"
            "# Full Notebook (Iframe Mode)\n"
            "\n"
            "The same notebook embedded as a full Marimo app in a sandboxed iframe,\n"
            "served from a self-hosted WASM export.\n"
            "\n"
            '{{< marimo file="notebooks/demo.py" mode="iframe" height="600px" >}}\n'
        ),
    },
    "config": {
        "marimo": True,
        "dark_mode": True,
    },
    "expected": {
        "files_exist": [
            "reference/index.html",
            "reference/greet.html",
            "user-guide/islands.html",
            "user-guide/nocode.html",
            "user-guide/iframe.html",
            "notebooks/demo/index.html",
        ],
        "files_contain": {
            "user-guide/islands.html": [
                "marimo-island",
                "gd-marimo-island-group",
                "gd-marimo-copy-btn",
            ],
            "user-guide/nocode.html": [
                "gd-marimo-nocode",
            ],
            "user-guide/iframe.html": [
                "gd-marimo-iframe",
                "notebooks/demo/index.html",
            ],
        },
        "coverage_exclude": ['ref', 'nodoc', 'bigcl', 'ug', 'supp', 'title', 'badge', 'sig', 'desc', 'param', 'pmatch', 'ret', 'refidx', 'sechdg', 'sbsec', 'hdg'],
    },
}
