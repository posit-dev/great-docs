"""The built-in `%nodoc_param` parameter exclusion directive"""

from __future__ import annotations

import griffe as gf

from great_docs._apiref._parameter_docs import (
    CallableDocumentation,
    filter_parameter_sections,
    prepare_parameter_docs,
)
from great_docs.hooks import on_docstring_parsed, on_object_resolved


@on_object_resolved(priority=-90)  # pyright: ignore[reportArgumentType]
def exclude_parameters(obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias:
    """Prepare parameter exclusions while retaining the complete source signature"""
    prepare_parameter_docs(obj)
    return obj


@on_docstring_parsed
def exclude_parameter_descriptions(
    obj: gf.Object | gf.Alias, sections: list[gf.DocstringSection]
) -> list[gf.DocstringSection]:
    """Omit descriptions of parameters excluded from the callable's documentation"""
    return filter_parameter_sections(sections, CallableDocumentation.make(obj).excluded_names)
