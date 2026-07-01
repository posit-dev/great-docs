import marimo
app = marimo.App(width="medium")

@app.cell
def _():
    import marimo as mo
    return (mo,)

@app.cell
def _(mo):
    mo.md("# Great Tables in a notebook")
    return

@app.cell
def _(mo):
    mo.md("Compute a summary, then style it:")
    return

@app.cell
def _():
    rows = [("Chicago", 2746), ("Toronto", 2794), ("Zurich", 402)]
    total = sum(pop for _, pop in rows)
    total
    return (rows, total)

if __name__ == "__main__":
    app.run()
