"""Preserve source formatting while rebasing recognised documentation inputs"""

from __future__ import annotations

import copy
import io
import json
import os
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlsplit, urlunsplit

import yaml
from yaml.events import AliasEvent
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode
from yaml12 import read_yaml

from great_docs._content_naming import strip_numeric_prefix
from great_docs._source_refs import fenced_code_spans, inline_code_spans, source_reference_spans

from .model import MigrationError, Move, Note, absolute_path, check_symlinks, moved_path

ConfigPath = tuple[str | int, ...]


@dataclass(frozen=True)
class ContentDirectory:
    """A recognised content root and how the build renames it for publishing"""

    source: Path
    output_name: str
    strip_prefix: bool


def _denormalize(
    target: Path, content_directories: tuple[ContentDirectory, ...], moves: tuple[Move, ...]
) -> tuple[Path, Path] | None:
    """
    Resolve a target through the build's own directory rename and prefix rule

    Return both the real, on-disk source file (to fingerprint and validate
    against) and the target's republished path: the same renamed/stripped
    shape the reference was written in, relocated only by however much its
    content directory itself moves. The build reapplies that rename and
    prefix strip regardless of where the source directory lives, so
    rewriting through the real, still-prefixed filename would silently
    reinstate or remove a transform the reference never asked for.

    Parameters
    ----------
    target
        A path that does not exist literally on disk.
    content_directories
        Recognised content roots, in the shape `analyse()` builds them.
    moves
        The migration's directory moves, used to relocate the republished path.

    Returns
    -------
    tuple[Path, Path] | None
        `(real_source_file, republished_path)`, or `None` if `target` doesn't
        match any recognised content directory.
    """
    for directory in content_directories:
        root = directory.source.parent
        renamed = root / directory.output_name
        if target.is_relative_to(renamed):
            relative = target.relative_to(renamed)
            republished_root = moved_path(directory.source, moves).parent / directory.output_name
        elif target.is_relative_to(directory.source):
            relative = target.relative_to(directory.source)
            republished_root = moved_path(directory.source, moves)
        else:
            continue
        if not relative.parts:
            return None
        republished = republished_root / relative
        if not directory.strip_prefix:
            candidate = directory.source / relative
            return (candidate, republished) if candidate.is_file() else None
        current = directory.source
        for part in relative.parts[:-1]:
            if not current.is_dir():
                return None
            matches = [
                child
                for child in current.iterdir()
                if child.is_dir() and strip_numeric_prefix(child.name) == part
            ]
            if len(matches) != 1:
                return None
            current = matches[0]
        if not current.is_dir():
            return None
        last = relative.parts[-1]
        stems = {last, Path(last).with_suffix(".qmd").name, Path(last).with_suffix(".md").name}
        matches = [
            child
            for child in current.iterdir()
            if child.is_file() and strip_numeric_prefix(child.name) in stems
        ]
        return (matches[0], republished) if len(matches) == 1 else None
    return None


_GENERATED_REFERENCE = re.compile(
    r"(?:\.\.?/)*(?:reference/[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\.(?:html|qmd)|llms(?:-full)?\.txt)\Z"
)
_PATH_FIELDS = (
    ("user_guide",),
    ("sections", "*", "dir"),
    ("custom_pages",),
    ("custom_pages", "dir"),
    ("custom_pages", "*"),
    ("custom_pages", "*", "dir"),
    ("bibliography",),
    ("bibliography", "*"),
    ("csl",),
    ("site", "css"),
    ("site", "css", "*"),
    ("pre_render",),
    ("pre_render", "*"),
    ("freeze", "pre_render"),
    ("freeze", "pre_render", "*"),
    ("logo",),
    ("logo", "light"),
    ("logo", "dark"),
    ("hero", "logo"),
    ("hero", "logo", "light"),
    ("hero", "logo", "dark"),
    ("favicon",),
    ("favicon", "icon"),
    ("favicon", "apple_touch"),
    ("favicon", "og_image"),
    ("include_in_header", "*", "file"),
    ("skill", "file"),
    ("skill", "extra_body"),
    ("skill", "skills", "*", "file"),
    ("social_cards", "image"),
    ("authors", "*", "image"),
    ("team_author", "image"),
)


def read_config(text: str) -> dict[str, Any]:
    """Read the unmerged configuration with the project's YAML 1.2 semantics"""
    try:
        value = read_yaml(io.StringIO(text))
    except (ValueError, TypeError, RecursionError) as error:
        raise MigrationError(f"Cannot read configuration: {error}") from error
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise MigrationError("The configuration must contain a mapping of options")
    return value


def config_paths(config: dict[str, Any]) -> Iterator[tuple[ConfigPath, str]]:
    """Yield documented source-path scalars without treating ordering entries as paths"""

    def descend(
        value: Any, pattern: tuple[str, ...], path: ConfigPath
    ) -> Iterator[tuple[ConfigPath, str]]:
        if not pattern:
            if isinstance(value, str) and value:
                yield path, value
            return
        key, *tail = pattern
        if key == "*" and isinstance(value, list):
            for index, item in enumerate(value):
                yield from descend(item, tuple(tail), (*path, index))
        elif isinstance(value, dict) and key in value:
            yield from descend(value[key], tuple(tail), (*path, key))

    for pattern in _PATH_FIELDS:
        yield from descend(config, pattern, ())


def local_path(value: str, source_dir: Path) -> Path | None:
    """Resolve literal configuration paths while leaving URLs outside migration"""
    url = urlsplit(value)
    if url.scheme or url.netloc or not url.path:
        return None
    return absolute_path(source_dir / value)


def _nodes(text: str) -> tuple[dict[ConfigPath, Node], set[int]]:
    try:
        root = yaml.compose(text, Loader=yaml.BaseLoader)
        events = list(yaml.parse(text, Loader=yaml.BaseLoader))
    except yaml.YAMLError as error:
        raise MigrationError(f"Cannot locate configuration source spans: {error}") from error
    unsafe = {
        event.start_mark.index
        for event in events
        if isinstance(event, AliasEvent)
        or getattr(event, "anchor", None)
        or getattr(event, "tag", None)
    }
    nodes: dict[ConfigPath, Node] = {}

    def visit(node: Node, path: ConfigPath, ancestors: frozenset[int]) -> None:
        if id(node) in ancestors:
            raise MigrationError("Recursive YAML aliases cannot be migrated")
        nodes[path] = node
        if isinstance(node, MappingNode):
            keys: set[str] = set()
            for key, value in node.value:
                if not isinstance(key, ScalarNode):
                    raise MigrationError("Complex YAML mapping keys cannot be migrated")
                if key.value in keys:
                    raise MigrationError(f"Duplicate YAML key: {key.value}")
                keys.add(key.value)
                visit(value, (*path, key.value), ancestors | {id(node)})
        elif isinstance(node, SequenceNode):
            for index, value in enumerate(node.value):
                visit(value, (*path, index), ancestors | {id(node)})

    if root is not None:
        visit(root, (), frozenset())
    return nodes, unsafe


def _check_span(path: ConfigPath, nodes: dict[ConfigPath, Node], unsafe: set[int]) -> None:
    for length in range(len(path) + 1):
        node = nodes.get(path[:length])
        if node is not None and node.start_mark.index in unsafe:
            raise MigrationError(
                f"Cannot independently edit an anchored, aliased, or tagged option: {path}"
            )
    node = nodes.get(path)
    if isinstance(node, ScalarNode) and node.style in {"|", ">"}:
        raise MigrationError(f"Cannot independently edit a block scalar: {path}")


def _scalar(value: str, node: ScalarNode) -> str:
    if node.style == "'":
        return "'" + value.replace("'", "''") + "'"
    if node.style == '"':
        return json.dumps(value, ensure_ascii=False)
    if (
        not value
        or value != value.strip()
        or value[0] in "-?:,[]{}#&*!|>'\"%@`"
        or any(char in value for char in (": ", " #", "\n", "\r", ",", "[", "]", "{", "}"))
    ):
        return json.dumps(value, ensure_ascii=False)
    try:
        parsed = read_config("value: " + value)["value"]
    except MigrationError:
        return json.dumps(value, ensure_ascii=False)
    return (
        value
        if isinstance(parsed, str) and parsed == value
        else json.dumps(value, ensure_ascii=False)
    )


def _set(config: dict[str, Any], path: ConfigPath, value: Any) -> None:
    parent: Any = config
    for key in path[:-1]:
        if not isinstance(parent.get(key), dict):
            parent[key] = {}
        parent = parent[key]
    parent[path[-1]] = value


def rewrite_config(text: str, moves: tuple[Move, ...], source_dir: Path, destination: Path) -> str:
    """
    Rebase documented path scalars while preserving all surrounding YAML bytes

    Keep URLs, absolute paths, and guide-relative ordering unchanged. Validate
    the complete result with YAML 1.2 against an independently updated mapping.
    Reject spans shared by aliases, explicit tags, or block scalars.
    """
    config = read_config(text)
    expected = copy.deepcopy(config)
    nodes, unsafe = _nodes(text)
    replacements: list[tuple[int, int, str]] = []
    for path, value in config_paths(config):
        target = local_path(value, source_dir)
        if target is None or Path(value).is_absolute():
            continue
        check_symlinks(source_dir / value)
        target = moved_path(target, moves)
        replacement = Path(os.path.relpath(target, destination)).as_posix()
        if replacement == value:
            continue
        node = nodes.get(path)
        if not isinstance(node, ScalarNode):
            raise MigrationError(f"Cannot locate a scalar source span: {path}")
        _check_span(path, nodes, unsafe)
        replacements.append(
            (node.start_mark.index, node.end_mark.index, _scalar(replacement, node))
        )
        parent: Any = expected
        for key in path[:-1]:
            parent = parent[key]
        parent[path[-1]] = replacement
    for start, end, replacement in sorted(replacements, reverse=True):
        text = text[:start] + replacement + text[end:]
    if read_config(text) != expected:
        raise MigrationError("Rebasing paths changed unrelated configuration values")
    return text


def set_config_values(text: str, updates: dict[ConfigPath, Any]) -> str:
    """Materialise discovered inputs without serialising existing configuration"""
    expected = read_config(text)
    for path, value in updates.items():
        nodes, unsafe = _nodes(text)
        _check_span(path, nodes, unsafe)
        _set(expected, path, value)
        node = nodes.get(path)
        if node is not None:
            text = (
                text[: node.start_mark.index]
                + json.dumps(value, ensure_ascii=False)
                + text[node.end_mark.index :]
            )
            continue
        parent_path = path[:-1]
        parent = nodes.get(parent_path)
        if parent is not None and not isinstance(parent, MappingNode):
            nested: Any = {path[-1]: value}
            text = (
                text[: parent.start_mark.index]
                + json.dumps(nested, ensure_ascii=False)
                + text[parent.end_mark.index :]
            )
        elif parent is None and parent_path:
            nested = value
            ancestor = path
            while ancestor not in nodes and len(ancestor) > 1:
                nested = {ancestor[-1]: nested}
                ancestor = ancestor[:-1]
            text = set_config_values(text, {ancestor: nested})
        else:
            entry = f"{path[-1]}: {json.dumps(value, ensure_ascii=False)}"
            newline = "\r\n" if "\r\n" in text else "\n"
            if isinstance(parent, MappingNode) and parent.flow_style:
                index = parent.end_mark.index - 1
                insertion = (", " if parent.value else "") + entry
            else:
                index = parent.end_mark.index if parent is not None else len(text)
                indent = parent.start_mark.column if parent is not None else 0
                insertion = (
                    (newline if index and text[index - 1] != "\n" else "")
                    + " " * indent
                    + entry
                    + newline
                )
            text = text[:index] + insertion + text[index:]
    if read_config(text) != expected:
        raise MigrationError("Materialising inputs changed unrelated configuration values")
    return text


def _locate(text: str, offset: int) -> tuple[int, str]:
    """Find the line number and text containing an offset into a document"""
    line = text.count("\n", 0, offset) + 1
    start = text.rfind("\n", 0, offset) + 1
    end = text.find("\n", offset)
    return line, text[start : end if end != -1 else len(text)]


_SHORTCODE = re.compile(r"\{\{<\s*([\w-]+)\s+([^>]+?)\s*>}}")
_SHORTCODE_FILE_ARGUMENT = re.compile(
    r"[/\\]|\.(?:qmd|ipynb|py|r|jl|md|mp4|webm|mov|m4v|mp3|wav|ogg|pdf"
    r"|png|jpe?g|gif|svg|webp|csv|json|ya?ml)\b",
    re.IGNORECASE,
)


def rewrite_document(
    text: str,
    source: Path,
    moves: tuple[Move, ...],
    *,
    generated_homepage: Path | None = None,
    content_directories: tuple[ContentDirectory, ...] = (),
) -> tuple[str, tuple[Path, ...], tuple[Note, ...], tuple[Note, ...]]:
    """
    Rebase static document destinations against their original source targets

    Return edited text, source inputs, manual follow-up, and blocking references.
    The build stages source-correct references into its own output coordinates.
    Preserve surrounding Markdown, HTML, examples, URL queries, and fragments.
    """
    inputs: set[Path] = set()
    follow_up: list[Note] = []
    blockers: list[Note] = []
    relocated = moved_path(source, moves)
    spans = source_reference_spans(text, html=source.suffix.lower() in {".html", ".htm"})
    for start, end in reversed(spans):
        value = text[start:end]
        if any(token in value for token in ("{{", "${", "<%")):
            line, snippet = _locate(text, start)
            follow_up.append(
                Note(
                    f"Review dynamic reference in {source}: {value}",
                    category="Dynamic References to Review",
                    path=source,
                    line=line,
                    snippet=snippet,
                )
            )
            continue
        url = urlsplit(value)
        if url.scheme or url.netloc or not url.path or value.startswith("/"):
            continue
        target = absolute_path(source.parent / unquote(url.path))
        input_target = target
        republished: Path | None = None
        try:
            check_symlinks(source.parent / unquote(url.path))
            check_symlinks(target)
            if (
                generated_homepage is not None
                and target in {generated_homepage, generated_homepage.with_suffix(".html")}
                and not target.exists()
            ):
                # The README-backed homepage keeps its published identity after relocation.
                continue
            if not target.exists() and target.suffix.lower() == ".html":
                candidates = [target.with_suffix(suffix) for suffix in (".qmd", ".md")]
                matches = [candidate for candidate in candidates if candidate.is_file()]
                if matches:
                    if len(matches) == 1:
                        input_target = matches[0]
                        check_symlinks(input_target)
                    else:
                        raise MigrationError(
                            f"Cannot resolve rendered page reference in {source}: {value}"
                        )
                else:
                    resolved = {
                        found[0]: found[1]
                        for candidate in candidates
                        if (found := _denormalize(candidate, content_directories, moves))
                        is not None
                    }
                    if len(resolved) == 1:
                        input_target, republished = next(iter(resolved.items()))
                        republished = republished.with_suffix(target.suffix)
                        check_symlinks(input_target)
                    elif not resolved and _GENERATED_REFERENCE.fullmatch(unquote(url.path)):
                        continue
                    else:
                        raise MigrationError(
                            f"Cannot resolve rendered page reference in {source}: {value}"
                        )
            if not input_target.exists():
                denormalized = _denormalize(input_target, content_directories, moves)
                if denormalized is not None:
                    input_target, republished = denormalized
                    check_symlinks(input_target)
                elif _GENERATED_REFERENCE.fullmatch(unquote(url.path)):
                    # Generated API pages have published identities but no repository source.
                    continue
                else:
                    raise MigrationError(f"Broken reference in {source}: {value}")
        except (OSError, MigrationError) as error:
            line, snippet = _locate(text, start)
            blockers.append(
                Note(
                    str(error),
                    category="Broken References to Fix",
                    path=source,
                    line=line,
                    snippet=snippet,
                )
            )
            continue
        inputs.add(input_target)
        if republished is not None:
            moved = republished
        else:
            moved = moved_path(input_target, moves)
            if input_target != target:
                moved = moved.with_suffix(target.suffix)
        candidate = absolute_path(relocated.parent / unquote(url.path))
        if candidate == moved:
            continue
        path = Path(os.path.relpath(moved, relocated.parent)).as_posix()
        safe = "/ " if " " in url.path else "/"
        replacement = urlunsplit(("", "", quote(path, safe=safe), url.query, url.fragment))
        text = text[:start] + replacement + text[end:]
    if relocated != source:
        code_match = re.search(r"(?:`{3,}|~{3,})\s*\{(?:python|r|julia|ojs|bash|sh)\b", text)
        if code_match:
            line, snippet = _locate(text, code_match.start())
            follow_up.append(
                Note(
                    f"Review dynamic code and working-directory assumptions in {source}",
                    category="Code Blocks to Verify",
                    path=source,
                    line=line,
                    snippet=snippet,
                )
            )
        if "{{<" in text:
            protected = fenced_code_spans(text) + inline_code_spans(text)
            flagged = next(
                (
                    shortcode
                    for shortcode in _SHORTCODE.finditer(text)
                    if shortcode[1] not in {"include", "code-include"}
                    and _SHORTCODE_FILE_ARGUMENT.search(shortcode[2])
                    and not any(start <= shortcode.start() < end for start, end in protected)
                ),
                None,
            )
            if flagged is not None:
                line, snippet = _locate(text, flagged.start())
                follow_up.append(
                    Note(
                        f"Review Quarto shortcode inputs in {source}",
                        category="Shortcodes to Check",
                        path=source,
                        line=line,
                        snippet=snippet,
                    )
                )
            matches = [
                match
                for match in re.finditer(r"\{\{<\s*(?:include|code-include)\s+([^>]+?)\s*>}}", text)
                if not any(start <= match.start() < end for start, end in protected)
            ]
            for match in reversed(matches):
                raw = match[1]
                reference = raw.strip().strip("\"'")
                target = local_path(reference, source.parent)
                if target is None:
                    continue
                inputs.add(target)
                if not target.exists():
                    line, snippet = _locate(text, match.start(1))
                    blockers.append(
                        Note(
                            f"Cannot preserve include reference in {source}: {reference}",
                            category="Includes That Can't Be Auto-Updated",
                            path=source,
                            line=line,
                            snippet=snippet,
                        )
                    )
                    continue
                moved = moved_path(target, moves)
                if absolute_path(relocated.parent / reference) == moved:
                    continue
                if raw.strip() != reference or " " in reference:
                    line, snippet = _locate(text, match.start(1))
                    blockers.append(
                        Note(
                            f"Cannot preserve include reference in {source}: {reference}",
                            category="Includes That Can't Be Auto-Updated",
                            path=source,
                            line=line,
                            snippet=snippet,
                        )
                    )
                    continue
                new_reference = Path(os.path.relpath(moved, relocated.parent)).as_posix()
                start, end = match.span(1)
                text = text[:start] + new_reference + text[end:]
        html_match = re.search(r"\b(?:srcset|data-src)\s*=", text) or re.search(
            r"""\bstyle\s*=\s*["'][^"']*\burl\(""", text
        )
        if html_match:
            line, snippet = _locate(text, html_match.start())
            follow_up.append(
                Note(
                    f"Review unsupported HTML file references in {source}",
                    category="HTML Attributes to Update Manually",
                    path=source,
                    line=line,
                    snippet=snippet,
                )
            )
        frontmatter = re.match(r"\A---\s*\n(.*?)\n---\s*(?:\n|$)", text, re.DOTALL)
        if frontmatter:
            field_match = re.search(
                r"(?m)^\s*(?:image|bibliography|csl|resources|include-in-header|include-before-body|include-after-body)\s*:",
                frontmatter[1],
            )
            if field_match:
                line, snippet = _locate(text, frontmatter.start(1) + field_match.start())
                blockers.append(
                    Note(
                        f"Review and manually update frontmatter file references in {source}",
                        category="Frontmatter Fields to Update Manually",
                        path=source,
                        line=line,
                        snippet=snippet,
                    )
                )
    return text, tuple(sorted(inputs)), tuple(follow_up), tuple(blockers)
