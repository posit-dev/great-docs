"""
PEP 695 type parameter lists, with bounds, constraints and defaults

Render the bracketed list of a generic class, function or alias. Variadic
parameters keep their `*` or `**` prefix, and an object without type parameters
gets no list.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import griffe as gf

# `*Ts` for a TypeVarTuple, `**P` for a ParamSpec, nothing for a plain TypeVar
_KIND_PREFIX = {
    "type-var": "",
    "type-var-tuple": "*",
    "param-spec": "**",
}


def render_type_parameters(type_parameters: gf.TypeParameters | None) -> str:
    """
    Render a PEP 695 type parameter list, brackets included

    Returns an empty string when there are no type parameters, so callers can
    concatenate the result unconditionally.
    """
    if not type_parameters:
        return ""

    rendered = ", ".join(_render_type_parameter(tp) for tp in type_parameters)
    return f"[{rendered}]"


def _render_type_parameter(tp: gf.TypeParameter) -> str:
    """
    Render one type parameter with its bound or constraints and any default

    A constrained parameter (`S: (str, bytes)`) carries no bound, so the two
    are alternatives rather than a bound with extra detail.
    """
    out = f"{_KIND_PREFIX.get(tp.kind.value, '')}{tp.name}"

    if tp.bound is not None:
        out += f": {tp.bound}"
    elif tp.constraints:
        constraints = ", ".join(str(c) for c in tp.constraints)
        out += f": ({constraints})"

    if tp.default is not None:
        out += f" = {tp.default}"

    return out
