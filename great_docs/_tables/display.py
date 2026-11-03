from __future__ import annotations

from typing import Any


def enable_tbl_preview(**kwargs: Any) -> None:
    """Register `tbl_preview()` as the default DataFrame display formatter.

    After calling this, any Polars or Pandas DataFrame that is the last expression in a cell (or
    passed to `display()`) will be rendered as a `tbl_preview()` table instead of the library's
    default HTML.

    Parameters
    ----------
    **kwargs
        Keyword arguments forwarded to `tbl_preview()` (e.g., `n_head=10`, `show_all=True`,
        `show_dimensions=False`).

    Returns
    -------
    None
        The formatter is registered as a side effect. IPython suppresses `None` output, so
        nothing is printed in the cell.

    Examples
    --------
    ```{python}
    import pandas as pd
    import great_docs as gd

    df = pd.DataFrame({"name": ["Alice", "Bob", "Carol"], "score": [92, 87, 95]})
    ```

    Before enabling, the DataFrame renders with default Pandas HTML:

    ```{python}
    df
    ```

    After enabling, the same DataFrame renders as a `tbl_preview()` table:

    ```{python}
    gd.enable_tbl_preview(n_head=3)
    df
    ```

    From this point on, all DataFrames (Pandas, Polars, or otherwise) will render using
    `tbl_preview()` until `disable_tbl_preview()` is called.

    See Also
    --------
    disable_tbl_preview : Remove the formatter and restore default display.
    tbl_preview : Generate a preview table for a single DataFrame.
    """
    try:
        ip = _get_ipython()
    except RuntimeError:
        return

    from .preview import _is_pandas, _is_polars, tbl_preview

    def _tbl_preview_formatter(obj: Any) -> str | None:
        if _is_polars(obj) or _is_pandas(obj):
            return tbl_preview(obj, **kwargs).as_html()
        return None

    html_formatter = ip.display_formatter.formatters["text/html"]  # type: ignore[union-attr]

    # Register for known DataFrame types (if available)
    try:
        import polars as pl

        html_formatter.for_type(pl.DataFrame, _tbl_preview_formatter)
    except ImportError:
        pass

    try:
        import pandas as pd

        html_formatter.for_type(pd.DataFrame, _tbl_preview_formatter)
    except ImportError:
        pass


def disable_tbl_preview() -> None:
    """Remove the `tbl_preview()` display formatter and restore defaults.

    After calling this, any Polars or Pandas DataFrame will revert to using the library's default
    HTML representation instead of `tbl_preview()`. This undoes the effect of
    `enable_tbl_preview()`.

    Returns
    -------
    None
        The formatter is removed as a side effect. IPython suppresses `None` output, so
        nothing is printed in the cell.

    Examples
    --------
    ```{python}
    import pandas as pd
    import great_docs as gd

    df = pd.DataFrame({"name": ["Alice", "Bob", "Carol"], "score": [92, 87, 95]})
    gd.enable_tbl_preview(n_head=3)
    ```

    With the preview formatter active, the DataFrame renders as a `tbl_preview()` table:

    ```{python}
    df
    ```

    After disabling, the DataFrame reverts to the default Pandas HTML:

    ```{python}
    gd.disable_tbl_preview()
    df
    ```

    From this point on, all DataFrames (Pandas, Polars, or otherwise) will render using their
    native styling until `enable_tbl_preview()` is called again.

    See Also
    --------
    enable_tbl_preview : Register `tbl_preview()` as the default DataFrame display formatter.
    tbl_preview : Generate a preview table for a single DataFrame.
    """
    try:
        ip = _get_ipython()
    except RuntimeError:
        return

    html_formatter = ip.display_formatter.formatters["text/html"]  # type: ignore[union-attr]

    try:
        import polars as pl

        html_formatter.pop(pl.DataFrame, None)
    except ImportError:
        pass

    try:
        import pandas as pd

        html_formatter.pop(pd.DataFrame, None)
    except ImportError:
        pass


def _get_ipython() -> Any:
    """Get the active IPython instance or raise RuntimeError."""
    try:
        from IPython import get_ipython

        ip = get_ipython()
        if ip is None:
            raise RuntimeError("No active IPython session.")
        return ip
    except ImportError:
        raise RuntimeError("IPython is not installed.")
