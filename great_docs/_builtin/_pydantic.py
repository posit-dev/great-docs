"""Field documentation from Pydantic model declarations"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import griffe as gf

from great_docs.hooks import on_object_resolved

if TYPE_CHECKING:
    from collections.abc import Sequence


_BASE_MODEL_PATHS = {"pydantic.BaseModel", "pydantic.main.BaseModel"}
_FIELD_PATHS = {"pydantic.Field", "pydantic.fields.Field"}
_ANNOTATED_PATHS = {"typing.Annotated", "typing_extensions.Annotated"}
_CLASS_VAR_PATHS = {"typing.ClassVar", "typing_extensions.ClassVar"}


# Supply the docstring before `%nodoc` checks it.
@on_object_resolved(priority=-110)  # pyright: ignore[reportArgumentType]
def add_pydantic_field_docstring(obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias:
    """
    Document a Pydantic field from its literal description

    Keep an existing docstring. For other fields, prefer a `Field` description
    supplied on the assignment, then one in `Annotated`, then a single string
    in the annotation's metadata.
    """
    if (
        not isinstance(obj, gf.Attribute)
        or obj.docstring is not None
        or obj.name.startswith("_")
        or obj.annotation is None
        or "instance-attribute" not in obj.labels
    ):
        return obj

    cls = obj.parent
    if isinstance(cls, gf.Class) and not _in_constructor(obj, cls):
        if description := _model_field_description(obj, cls):
            obj.docstring = gf.Docstring(description, parent=obj)
    return obj


def _inherits_base_model(cls: gf.Class) -> bool:
    """Recognise Pydantic ancestry from the class and its loaded bases"""
    try:
        ancestors = cls.mro()
    except ValueError:
        ancestors = []
    return any(
        (base if isinstance(base, str) else base.canonical_path) in _BASE_MODEL_PATHS
        for ancestor in (cls, *ancestors)
        for base in ancestor.bases
    )


def _in_constructor(attribute: gf.Attribute, cls: gf.Class) -> bool:
    """Distinguish `self` assignments from declarations in the class body"""
    constructor = cls.members.get("__init__")
    return (
        isinstance(constructor, gf.Function)
        and constructor.lineno is not None
        and constructor.endlineno is not None
        and attribute.lineno is not None
        and constructor.lineno <= attribute.lineno <= constructor.endlineno
    )


def _annotated_elements(annotation: str | gf.Expr | None) -> Sequence[str | gf.Expr]:
    """Read the type and metadata of an outer `Annotated` expression"""
    if (
        isinstance(annotation, gf.ExprSubscript)
        and annotation.canonical_path in _ANNOTATED_PATHS
        and isinstance(annotation.slice, gf.ExprTuple)
    ):
        return annotation.slice.elements
    return ()


def _annotated_elements_from_source(
    attribute: gf.Attribute, cls: gf.Class
) -> Sequence[str | gf.Expr]:
    """
    Recover literal metadata from an `Annotated` declaration

    Griffe can interpret a metadata string as a type expression when the
    module uses eager annotations. Read the collected source with that
    interpretation disabled for strings.
    """
    try:
        lines = attribute.lines
    except ValueError:
        return ()
    if not lines:
        return ()

    source = "\n".join(lines)
    # Preserve the indentation of multiline strings and continuation lines.
    if lines[0][:1].isspace():
        source = f"if True:\n{source}"
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ()

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == attribute.name
        ):
            annotation = gf.safe_get_expression(node.annotation, cls, parse_strings=False)
            return _annotated_elements(annotation)
    return ()


def _string_literal(expression: str | gf.Expr | None) -> str | None:
    """Decode a non-blank string literal"""
    if not isinstance(expression, str) or not expression.startswith(("'", '"')):
        return None
    try:
        text: object = ast.literal_eval(expression)
    except (SyntaxError, ValueError):
        return None
    return text if isinstance(text, str) and text.strip() else None


def _field_call_description(expression: str | gf.Expr | None) -> str | None:
    """Read the literal `description` argument of a Pydantic `Field` call"""
    if isinstance(expression, gf.ExprCall) and expression.function.canonical_path in _FIELD_PATHS:
        for argument in expression.arguments:
            if isinstance(argument, gf.ExprKeyword) and argument.name == "description":
                return _string_literal(argument.value)
    return None


def _is_class_var(annotation: str | gf.Expr | None, cls: gf.Class) -> bool:
    """Recognise `ClassVar` with annotation wrappers or forward references"""
    while True:
        if elements := _annotated_elements(annotation):
            annotation = elements[0]
        elif source := _string_literal(annotation):
            try:
                expression = ast.parse(source, mode="eval").body
            except SyntaxError:
                return False
            annotation = gf.safe_get_expression(expression, cls, parse_strings=False)
        else:
            return isinstance(annotation, gf.Expr) and annotation.canonical_path in _CLASS_VAR_PATHS


def _model_field_description(attribute: gf.Attribute, cls: gf.Class) -> str | None:
    """Read prose from a Pydantic model field's assignment or annotation"""
    elements = _annotated_elements(attribute.annotation)
    assigned = _field_call_description(attribute.value)
    if not (elements or assigned) or not _inherits_base_model(cls):
        return None
    if _is_class_var(attribute.annotation, cls):
        return None
    if assigned:
        return assigned

    _, *metadata = _annotated_elements_from_source(attribute, cls) or elements
    for item in reversed(metadata):
        if description := _field_call_description(item):
            return description
    strings = [text for item in metadata if (text := _string_literal(item)) is not None]
    return strings[0] if len(strings) == 1 else None
