"""
Generate a synthetic package for benchmarking `great-docs build` render times

The package has many functions and classes (one reference page each) plus a
User Guide with a mix of prose-only and executable pages, roughly the shape
of a library with a large API and extensive docs.

Usage:

    python scripts/make_render_bench_pkg.py /tmp/gd-bench --functions 600 --classes 150 \
        --guides 40 --exec-guides 8
    cd /tmp/gd-bench && great-docs init && great-docs build
"""

from __future__ import annotations

import argparse
import shutil
import textwrap
from pathlib import Path

_FUNC = '''
def {name}(data: list[float], scale: float = 1.0, *, label: str | None = None) -> list[float]:
    """
    Transform the data with variant {i} of the scaling rule

    This function applies a scaling transformation to `data`. See also
    [](`~{pkg}.{other}`) for a related operation. The longer description is
    here to give the page some body text, the way a real reference page has.

    Parameters
    ----------
    data
        The values to transform.
    scale
        Multiplier applied to each value.
    label
        An optional label recorded with the result.

    Returns
    -------
    list[float]
        The transformed values.

    Examples
    --------
    ```python
    {name}([1.0, 2.0, 3.0], scale=2.0)
    ```
    """
    return [x * scale + {i} for x in data]
'''

_CLASS = '''
class {name}:
    """
    A widget of kind {i}

    Widgets hold a value and offer a handful of methods to work with it. See
    [](`~{pkg}.{other}`) for a related function.

    Parameters
    ----------
    value
        The initial value.
    name
        A display name.
    """

    def __init__(self, value: float = 0.0, name: str = "w{i}") -> None:
        self.value = value
        self.name = name
{methods}
'''

_METHOD = '''
    def {meth}(self, amount: float = 1.0) -> "{cls}":
        """
        Apply operation `{meth}` to the widget

        Parameters
        ----------
        amount
            How much to apply.

        Returns
        -------
        {cls}
            The widget, for chaining.
        """
        self.value += amount
        return self
'''

_GUIDE = """\
---
title: "Guide page {i}"
---

## Overview

This is page {i} of the User Guide. It talks about `{pkg}` in some depth so that
the page has a realistic amount of prose, a few lists, and a table.

- First point about the topic of page {i}
- Second point, which links to [the reference](../reference/index.qmd)
- Third point

| Column A | Column B | Column C |
|----------|----------|----------|
| 1        | 2        | 3        |
| 4        | 5        | 6        |

## Details

{body}
"""

_EXEC = """
## Running code

```{{python}}
import {pkg}
{pkg}.func_{j:04d}([1.0, 2.0, 3.0], scale={i})
```

```{{python}}
w = {pkg}.Widget{j:04d}(1.5)
w.op_0(2.0).value
```
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("dest", type=Path)
    parser.add_argument("--functions", type=int, default=600)
    parser.add_argument("--classes", type=int, default=150)
    parser.add_argument("--methods", type=int, default=5)
    parser.add_argument("--guides", type=int, default=40)
    parser.add_argument("--exec-guides", type=int, default=8)
    parser.add_argument("--name", default="gdbench")
    args = parser.parse_args()

    pkg = args.name
    dest: Path = args.dest
    if dest.exists():
        shutil.rmtree(dest)
    src = dest / pkg
    src.mkdir(parents=True)

    funcs = [f"func_{i:04d}" for i in range(args.functions)]
    classes = [f"Widget{i:04d}" for i in range(args.classes)]
    names = funcs + classes

    parts = ['"""Synthetic benchmark package"""\n\n__version__ = "0.1.0"\n']
    parts.append("__all__ = [\n" + "".join(f'    "{n}",\n' for n in names) + "]\n")
    for i, name in enumerate(funcs):
        other = funcs[(i + 1) % len(funcs)]
        parts.append(_FUNC.format(name=name, i=i, pkg=pkg, other=other))
    for i, name in enumerate(classes):
        methods = "".join(_METHOD.format(meth=f"op_{m}", cls=name) for m in range(args.methods))
        parts.append(
            _CLASS.format(name=name, i=i, pkg=pkg, other=funcs[i % len(funcs)], methods=methods)
        )
    (src / "__init__.py").write_text("\n".join(parts), encoding="utf-8")

    (dest / "pyproject.toml").write_text(
        textwrap.dedent(f"""\
            [project]
            name = "{pkg}"
            version = "0.1.0"
            description = "Synthetic package for render benchmarks"
            requires-python = ">=3.10"

            [build-system]
            requires = ["setuptools"]
            build-backend = "setuptools.build_meta"
            """),
        encoding="utf-8",
    )
    (dest / "README.md").write_text(f"# {pkg}\n\nA synthetic benchmark package.\n")

    guide_dir = dest / "user_guide"
    guide_dir.mkdir()
    body = "\n\n".join(
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod "
        "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam."
        for _ in range(6)
    )
    exec_every = max(1, args.guides // args.exec_guides) if args.exec_guides else 0
    n_exec = 0
    for i in range(args.guides):
        text = _GUIDE.format(i=i, pkg=pkg, body=body)
        if exec_every and i % exec_every == 0 and n_exec < args.exec_guides:
            text += _EXEC.format(pkg=pkg, i=i + 1, j=i % max(1, min(len(funcs), len(classes))))
            n_exec += 1
        (guide_dir / f"{i:02d}-guide-{i}.qmd").write_text(text, encoding="utf-8")

    print(f"Wrote {dest} ({len(names)} exports, {args.guides} guide pages, {n_exec} executable)")


if __name__ == "__main__":
    main()
