from __future__ import annotations

import griffe as gf

from .._docstring_sections import (
    DCDocstringSectionInitParameters,
    DCDocstringSectionParameterAttributes,
    DocstringSectionNotes,
    DocstringSectionSeeAlso,
    DocstringSectionWarnings,
)

# Which method renders which docstring section.
#
# Lookup is `getattr(self, SECTION_METHOD[type(el)], None)`, so a class that
# does not define the method has no renderer for that section. That is how a
# section is confined to the objects it can describe: `render_parameters_section`
# lives on the call mixin, so a module or a type alias cannot reach it.
#
# The method lookup follows the MRO (a subclass inherits what its parent
# defines), but the table lookup above it does not: it keys on `type(el)`
# exactly, so a subclass of a griffe section type will not be found.
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
    # Hand-written member summaries that great-docs generates from the real
    # members. Dropped on purpose and silently — they are common in valid
    # numpydoc, so warning about them would be noise. Each gets its own
    # method (sharing only the private `_suppress_section` helper) so
    # overriding how one is dropped cannot affect the others.
    gf.DocstringSectionFunctions: "render_functions_section",
    gf.DocstringSectionClasses: "render_classes_section",
    gf.DocstringSectionModules: "render_modules_section",
    gf.DocstringSectionTypeAliases: "render_type_aliases_section",
}
