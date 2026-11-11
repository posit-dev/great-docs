"""Project-aware prompt and resource completions"""

from __future__ import annotations

from pathlib import Path

from mcp.types import (
    Completion,
    CompletionArgument,
    CompletionContext,
    PromptReference,
    ResourceTemplateReference,
)

from .._build.ownership import is_in_great_docs_build_dir
from .._project.layout import CONVENTIONAL_DOC_DIRS
from . import context as _context


async def handle_completion(
    ref: PromptReference | ResourceTemplateReference,
    argument: CompletionArgument,
    context: CompletionContext | None = None,
) -> Completion | None:
    """
    Suggest values for prompt and resource template arguments

    Parameters
    ----------
    ref
        The prompt or resource template to complete.
    argument
        The argument name and partial value to complete.
    context
        Previously supplied arguments, including any project and configuration
        selection. Omit to use the default project configuration discovery.

    Returns
    -------
    :
        Matching suggestions, or `None` for an unsupported completion or a
        handled project error.
    """
    value = argument.value or ""
    arguments = (context.arguments if context else None) or {}

    # Prompt argument completions
    if isinstance(ref, PromptReference):
        if ref.name == "write-user-guide" and argument.name == "audience":
            options = ["beginner", "intermediate", "advanced"]
            filtered = [o for o in options if o.startswith(value.lower())]
            return Completion(values=filtered)

        if ref.name == "write-user-guide" and argument.name == "topic":
            # Suggest common doc topics
            topics = [
                "getting-started",
                "installation",
                "configuration",
                "theming",
                "deployment",
                "custom-pages",
                "API reference",
                "CLI usage",
                "multi-version docs",
            ]
            filtered = [t for t in topics if value.lower() in t.lower()]
            return Completion(values=filtered[:10])

        if ref.name == "improve-docstrings" and argument.name == "style":
            options = ["numpy", "google", "sphinx"]
            filtered = [o for o in options if o.startswith(value.lower())]
            return Completion(values=filtered)

        if ref.name == "improve-docstrings" and argument.name == "symbol":
            # Complete with actual package symbols
            try:
                package_exports = _context.get_exports(
                    arguments.get("project_path"), arguments.get("config_path")
                )
                importable_name = package_exports.project.importable_name
                if not importable_name:
                    return Completion(values=[])
                exports = package_exports.names(importable_name)
                filtered = [e for e in exports if value.lower() in e.lower()]
                return Completion(values=filtered[:20], hasMore=len(filtered) > 20)
            except _context.REPORTED_ERRORS:
                return None

        if argument.name == "project_path":
            # Suggest current directory
            return Completion(values=[str(Path.cwd())])

        if argument.name == "config_path":
            root = _context.get_project_root(arguments.get("project_path"))
            paths = [root / "great-docs.yml"] + [
                root / name / "great-docs.yml" for name in CONVENTIONAL_DOC_DIRS
            ]
            return Completion(
                values=[str(path) for path in paths if path.is_file() and value in str(path)]
            )

    # Resource template completions
    if isinstance(ref, ResourceTemplateReference):
        if "reference" in str(ref.uri) and argument.name == "symbol":
            try:
                package_exports = _context.get_exports(
                    arguments.get("project_path"), arguments.get("config_path")
                )
                importable_name = package_exports.project.importable_name
                if not importable_name:
                    return Completion(values=[])
                exports = package_exports.names(importable_name)
                filtered = [e for e in exports if value.lower() in e.lower()]
                return Completion(values=filtered[:20], hasMore=len(filtered) > 20)
            except _context.REPORTED_ERRORS:
                return None

        if "page" in str(ref.uri) and argument.name == "path":
            # List source pages without their generated build copies.
            layout = _context.get_layout(arguments)
            root = layout.package_root
            rel_paths = (p.relative_to(root) for p in layout.source_dir.rglob("*.qmd"))
            qmd_files = sorted(
                str(rel)
                for rel in rel_paths
                if not is_in_great_docs_build_dir(rel.parts, root, layout)
            )
            filtered = [f for f in qmd_files if value.lower() in f.lower()]
            return Completion(values=filtered[:20], hasMore=len(filtered) > 20)

    return None
