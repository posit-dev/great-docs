"""
The renderer method for each docstring section type

The table covers Griffe's sections and the normalised Notes, Warnings and See Also
sections.
"""

from __future__ import annotations

import griffe as gf

from .._docstring_sections import (
    DCDocstringSectionInitParameters,
    DCDocstringSectionParameterAttributes,
    DocstringSectionNotes,
    DocstringSectionSeeAlso,
    DocstringSectionWarnings,
)

# Renderers look methods up by name, so a section reaches only the renderers that
# define its method; a module has no `render_parameters_section`, for example, and
# omits that section with a warning. The table keys on a section's exact type, so a
# subclass of a Griffe section type needs its own entry.
SECTION_METHOD: dict[type, str] = {
    # Any object
    gf.DocstringSectionText: "render_text_section",
    gf.DocstringSectionExamples: "render_examples_section",
    gf.DocstringSectionDeprecated: "render_deprecated_section",
    gf.DocstringSectionAdmonition: "render_admonition_section",
    DocstringSectionNotes: "render_notes_section",
    DocstringSectionSeeAlso: "render_see_also_section",
    DocstringSectionWarnings: "render_warnings_section",
    # Objects with members (classes and modules)
    gf.DocstringSectionAttributes: "render_attributes_section",
    # Generic objects (classes, functions, and type aliases)
    gf.DocstringSectionTypeParameters: "render_type_parameters_section",
    # Callables only
    gf.DocstringSectionParameters: "render_parameters_section",
    gf.DocstringSectionOtherParameters: "render_other_parameters_section",
    gf.DocstringSectionReturns: "render_returns_section",
    gf.DocstringSectionYields: "render_yields_section",
    gf.DocstringSectionReceives: "render_receives_section",
    gf.DocstringSectionRaises: "render_raises_section",
    gf.DocstringSectionWarns: "render_warns_section",
    DCDocstringSectionInitParameters: "render_init_parameters_section",
    DCDocstringSectionParameterAttributes: "render_parameter_attributes_section",
    # Each hand-written member summary has its own omission method, so overriding
    # one to keep it leaves the others omitted.
    gf.DocstringSectionFunctions: "render_functions_section",
    gf.DocstringSectionClasses: "render_classes_section",
    gf.DocstringSectionModules: "render_modules_section",
    gf.DocstringSectionTypeAliases: "render_type_aliases_section",
}
