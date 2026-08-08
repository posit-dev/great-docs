# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     # great-tables >= 0.22 depends on multimark, a compiled package with no
#     # pure-Python / WASM wheel, so it can't install under Pyodide. Pin to the
#     # last pure-Python release (0.21.x) so the notebook runs in the browser.
#     "great-tables<0.22",
#     "polars",
# ]
# ///

import marimo

app = marimo.App()


@app.cell
def __():
    return


@app.cell
async def __():
    import sys

    if "pyodide" in sys.modules:
        import micropip

        await micropip.install(["great-tables<0.22", "polars"])

    import great_tables as _gt
    import polars as _pl

    # Monthly sales data
    sales = _pl.DataFrame(
        {
            "month": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
            "revenue": [12400, 15800, 14200, 18900, 21300, 19700],
            "growth": [None, 0.274, -0.101, 0.331, 0.127, -0.075],
        }
    )

    (
        _gt.GT(sales)
        .tab_header(
            title="Monthly Revenue",
            subtitle="H1 2026 Performance",
        )
        .cols_label(
            month="Month",
            revenue="Revenue",
            growth="Growth",
        )
        .fmt_currency(columns="revenue", decimals=0)
        .fmt_percent(columns="growth", decimals=1)
        .data_color(
            columns="revenue",
            palette=["#f0f9e8", "#0868ac"],
        )
        .sub_missing(missing_text="—")
    )
    return


if __name__ == "__main__":
    app.run()
