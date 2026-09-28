# /// script
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
        # A Reactive Notebook

        marimo notebooks are **reactive**: change a value and every cell that
        depends on it re-runs on its own — no "Run" button, no page reload.
        Drag the sliders below and watch the summary, chart, and table update
        together. (This notebook uses only marimo, so it boots instantly.)
        """
    )
    return


@app.cell
def __(mo):
    bars = mo.ui.slider(1, 12, value=5, label="Number of bars")
    peak = mo.ui.slider(20, 100, value=70, label="Tallest bar (px)")
    mo.hstack([bars, peak], justify="start", gap=2)
    return bars, peak


@app.cell
def __(bars, mo, peak):
    mo.md(
        f"You asked for **{bars.value}** bars with a peak height of "
        f"**{peak.value}px**. Everything below recomputes from those two values."
    )
    return


@app.cell
def __(bars, peak):
    # Deterministic pseudo-data so the demo is stable but varied.
    values = [((i * 37 + 13) % 100) + 1 for i in range(bars.value)]
    return (values,)


@app.cell
def __(mo, peak, values):
    # A dependency-free bar chart, drawn as inline SVG straight from Python.
    width, gap = 30, 10
    top = peak.value
    rects = "".join(
        f'<rect x="{i * (width + gap)}" y="{top - round(top * v / 100)}" '
        f'width="{width}" height="{round(top * v / 100)}" rx="4" '
        f'fill="hsl({205 + i * 14} 72% 56%)"/>'
        for i, v in enumerate(values)
    )
    svg = (
        f'<svg width="{len(values) * (width + gap)}" height="{top}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="Reactive bar chart">{rects}</svg>'
    )
    mo.Html(svg)
    return


@app.cell
def __(mo, values):
    mo.ui.table(
        [{"bar": i + 1, "value": v} for i, v in enumerate(values)],
        selection=None,
    )
    return


@app.cell
def __(mo):
    mo.md(
        """
        Notice you never touched the chart or table cells — they depend on the
        sliders, so marimo re-ran them for you. In **iframe mode** you can go a
        step further and edit this code yourself.
        """
    )
    return


if __name__ == "__main__":
    app.run()
