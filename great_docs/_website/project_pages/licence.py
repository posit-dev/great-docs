"""
A page showing the project's `LICENSE` file
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..._license import BADGE_TOOLTIP_KEYS, build_license_features_html, get_license_info
from ..._translations import get_translation
from .. import page_dates

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from ...config import Config

__all__ = ["FILENAME", "write_page"]

FILENAME = "license.qmd"


def write_page(
    config: Config,
    package_root: Path,
    build_dir: Path,
    licence_id: str,
    authors: list[dict[str, Any]],
    *,
    report: Callable[[str], None],
) -> Path | None:
    """
    Write the licence page from the project's `LICENSE` file

    The page shows the file's text verbatim. For a known SPDX licence, a section listing
    its permissions, conditions and limitations precedes the text.

    Parameters
    ----------
    config
        The Great Docs configuration.
    package_root
        The project directory holding `LICENSE`.
    build_dir
        The Quarto project directory to write the page into.
    licence_id
        The project's licence identifier, or `""` if it declares none.
    authors
        The configured authors, with local portrait paths replaced by site URLs.
    report
        A callback that receives the line announcing the written page.

    Returns
    -------
    :
        The path of the written page, or `None` if the project has no `LICENSE` file.
    """
    source = package_root / "LICENSE"
    if not source.exists():
        return None

    licence_text = source.read_text(encoding="utf-8")

    features_block = ""
    licence_info = get_license_info(licence_id) if licence_id else None
    if licence_info is not None:
        lang = config.lang
        features_html = build_license_features_html(
            licence_info,
            features_label=get_translation("license_features", lang),
            permissions_label=get_translation("license_permissions", lang),
            conditions_label=get_translation("license_conditions", lang),
            limitations_label=get_translation("license_limitations", lang),
            tooltips={
                label: get_translation(key, lang) for label, key in BADGE_TOOLTIP_KEYS.items()
            },
        )
        # Raw blocks make Quarto pass the HTML through unchanged
        if features_html:
            features_block = "```{=html}\n" + features_html + "\n```\n\n"

    content = f"""---
title: "License"
toc: false
sidebar: false
page-layout: full
body-classes: "gd-license-page"
anchor-sections: false
---

{features_block}```{{=html}}
<pre class="gd-skills-raw">
```

````markdown
{licence_text}
````

```{{=html}}
</pre>
```
"""
    path = build_dir / FILENAME
    _ = path.write_text(page_dates.add_to_page(content, source, config, authors), encoding="utf-8")
    report(f"Created {path}")
    return path
