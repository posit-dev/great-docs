"""Parser-neutral doctest normalization"""

from __future__ import annotations

import griffe as gf

from great_docs.hooks import on_object_resolved


@on_object_resolved(priority=100)  # pyright: ignore[reportArgumentType]
def normalize_doctests(obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias:
    """
    Fence unfenced doctest prompts as static Python examples

    Parameters
    ----------
    obj
        The resolved object.

    Returns
    -------
    :
        The object with unfenced doctest groups converted to Python code fences.
    """
    docstring = obj.docstring
    if docstring is not None:
        docstring.value = _fence_doctest_blocks(docstring.value)
    return obj


def _fence_doctest_blocks(text: str) -> str:
    """
    Wrap each unfenced doctest example in a prompt-aligned static Python fence

    Include each prompt and its expected output until a blank line or dedent
    ends the example. This matches the span recognised by `doctest`.

    Parameters
    ----------
    text
        Docstring source that may contain doctest prompts.

    Returns
    -------
    :
        The source with each unfenced example enclosed in a Python code fence.
    """
    lines = text.split("\n")
    result: list[str] = []
    example: list[str] = []
    indent = ""
    in_fence = False

    def flush() -> None:
        """Append the pending example in a static Python fence"""
        if example:
            result.extend([f"{indent}```python", *example, f"{indent}```"])
            example.clear()

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("```"):
            flush()
            in_fence = not in_fence
            result.append(line)
        elif in_fence:
            result.append(line)
        elif example:
            # Keep each fence at the prompt indentation. A nonblank,
            # less-indented line belongs to the surrounding structure.
            if stripped and len(line) - len(stripped) >= len(indent):
                example.append(line)
            else:
                flush()
                result.append(line)
        elif _is_prompt(stripped):
            indent = line[: len(line) - len(stripped)]
            example.append(line)
        else:
            result.append(line)

    flush()
    return "\n".join(result)


def _is_prompt(stripped: str) -> bool:
    """
    Return whether a stripped line opens or continues a doctest prompt

    Parameters
    ----------
    stripped
        A docstring line with its leading whitespace removed.

    Returns
    -------
    :
        True when the line is a `>>>` prompt or a `...` continuation.
    """
    return stripped.startswith(">>> ") or stripped == ">>>" or stripped.startswith("... ")
