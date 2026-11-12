"""Parameter exclusions for callable documentation"""

from __future__ import annotations

import keyword
import re
from copy import copy
from dataclasses import dataclass
from typing import cast

import griffe as gf

from great_docs._source_refs import fenced_lines

from ._constructor import class_constructor, without_receiver

_DIRECTIVE = re.compile(r"^[ \t]*%nodoc_param\b(.*)$")
_METADATA_KEY = "nodoc_params"


class ParameterDirectiveError(ValueError):
    """An invalid parameter exclusion in a callable's documentation"""

    def __init__(self, symbol: str, reason: str) -> None:
        self.symbol = symbol
        super().__init__(f"{symbol}: %nodoc_param {reason}")


def _declarations(obj: gf.Object | gf.Alias) -> tuple[str | None, frozenset[str]]:
    """Extract exclusions while preserving fenced directive examples"""
    obj = obj.final_target if isinstance(obj, gf.Alias) else obj
    saved = cast("frozenset[str]", obj.extra.get("great_docs", {}).get(_METADATA_KEY, frozenset()))
    docstring = obj.docstring
    if docstring is None:
        return None, saved
    text = docstring.value
    if "%nodoc_param" not in text:
        return text, saved
    lines, fenced = fenced_lines(text)
    cleaned: list[str] = []
    names = set(saved)
    for line, protected in zip(lines, fenced):
        match = None if protected else _DIRECTIVE.fullmatch(line)
        if match is None:
            cleaned.append(line)
            continue
        name = (match.group(1) or "").strip()
        if not name.isidentifier() or keyword.iskeyword(name):
            raise ParameterDirectiveError(obj.path, "requires one bare Python parameter name")
        names.add(name)
    return "\n".join(cleaned).strip(), frozenset(names)


@dataclass(frozen=True)
class CallableDocumentation:
    """A callable's documented parameters with its source signature preserved"""

    parameters: gf.Parameters
    overloads: list[gf.Function]
    excluded_names: frozenset[str]
    original_parameters: gf.Parameters

    @classmethod
    def make(cls, obj: gf.Object | gf.Alias) -> CallableDocumentation:
        """Build the effective parameter view for a function or selected constructor"""
        _, names = _declarations(obj)
        parameters = gf.Parameters()
        overloads: list[gf.Function] = []
        if obj.is_class:
            constructor = class_constructor(cast("gf.Class | gf.Alias", obj))
            parameters = constructor.parameters
            overloads = constructor.overloads
            try:
                member = obj.all_members.get(constructor.name)
            except (gf.AliasResolutionError, gf.CyclicAliasError):
                member = obj.members.get(constructor.name)
            if member is not None and member.is_function:
                _, inherited = _declarations(member)
                names |= inherited
        elif obj.is_function:
            function = cast("gf.Function", obj)
            parameters = function.parameters
            overloads = list(function.overloads or [])

        if not names:
            return cls(parameters, overloads, names, parameters)

        applicable = [parameters, *(overload.parameters for overload in overloads)]
        is_method = obj.is_class or (
            obj.parent is not None and obj.parent.is_class and "staticmethod" not in obj.labels
        )
        known = {
            p.name
            for params in applicable
            for p in (without_receiver(params) if is_method else params)
        }
        unknown = names - known
        if unknown:
            raise ParameterDirectiveError(
                obj.path, f"names unknown parameter(s): {', '.join(sorted(unknown))}"
            )

        def retained(params: gf.Parameters) -> gf.Parameters:
            return gf.Parameters(*(p for p in params if p.name not in names))

        variants: list[gf.Function] = []
        for overload in overloads:
            variant = copy(overload)
            variant.parameters = retained(overload.parameters)
            variants.append(variant)
        return cls(retained(parameters), variants, names, parameters)


def prepare_parameter_docs(obj: gf.Object | gf.Alias) -> None:
    """Validate exclusions and strip their declarations before docstring parsing"""
    # Constructor declarations also apply when only their class is documented.
    _ = CallableDocumentation.make(obj)
    text, names = _declarations(obj)
    if not names:
        return
    target = obj.final_target if isinstance(obj, gf.Alias) else obj
    target.extra.setdefault("great_docs", {})[_METADATA_KEY] = names
    if obj.docstring is not None and text is not None:
        obj.docstring.value = text


def filter_parameter_sections(
    sections: list[gf.DocstringSection], names: frozenset[str]
) -> list[gf.DocstringSection]:
    """Remove excluded descriptions without modifying the input sections"""
    if not names:
        return sections
    result: list[gf.DocstringSection] = []
    for section in sections:
        if not isinstance(
            section, (gf.DocstringSectionParameters, gf.DocstringSectionOtherParameters)
        ):
            result.append(section)
            continue
        entries: list[gf.DocstringParameter] = []
        for item in section.value:
            original = [name.strip() for name in item.name.split(",")]
            retained = [name for name in original if name.lstrip("*") not in names]
            if not retained:
                continue
            if retained != original:
                item = copy(item)
                item.name = ", ".join(retained)
            entries.append(item)
        if entries:
            filtered = copy(section)
            filtered.value = entries
            result.append(filtered)
    return result
