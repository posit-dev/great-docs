"""
The extension that customises one API reference

An `Extension` holds one operation's registrations, renderer choices, `cache` and
declared inputs. It prepares each object's documentation once. Registration closes
when the extension file's `setup` returns, and closing the extension releases the
project modules it imported.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Callable, TypeVar, cast, overload

import griffe as gf

from ..hooks._docstring_parsed import REGISTRY as PARSED_HOOKS
from ..hooks._docstring_parsed import DocstringParsedHook
from ..hooks._object_resolved import REGISTRY as OBJECT_HOOKS
from ..hooks._object_resolved import ObjectResolvedHook
from ..hooks._registry import HookRegistry
from . import _extension_inputs
from ._extension_loading import _ExtensionSource, _ImportOwner
from ._rendering._renderers import Renderers

if TYPE_CHECKING:
    from griffe import DocstringOptions

    from ._settings import Settings

_Hook = TypeVar("_Hook", bound=Callable[..., object])


@dataclass(frozen=True)
class _PreparedObject:
    """A retained canonical identity and its prepared result or exclusion"""

    original: gf.Object
    result: gf.Object | None


class ExtensionError(RuntimeError):
    """An error in the API reference extension, naming its file and phase"""


class _ExtensionErrorContext:
    """The phase and optional object appearance of a configured operation"""

    def __init__(
        self,
        entry_path: Path | None,
        close: Callable[[], None],
        phase: str,
        subject: str | None = None,
    ) -> None:
        self.entry_path = entry_path
        self.close = close
        self.phase = phase
        self.subject = subject

    def __enter__(self) -> None:
        """Enter the diagnostic boundary without running configured code"""
        return None

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Release owned imports and preserve the original configured failure as its cause"""
        if error is None:
            return
        self.close()
        if (
            self.entry_path is None
            or not isinstance(error, Exception)
            or isinstance(error, ExtensionError)
        ):
            return
        subject = f" for {self.subject}" if self.subject else ""
        raise ExtensionError(
            f"API reference extension {self.entry_path}: {self.phase}{subject}: {error}"
        ) from error


class Extension:
    """
    The API reference extension that `setup(extension)` receives

    Setup may inspect `settings`, `source_root` and `config_root` and keep its own
    values in `cache`. Treat settings and roots as read-only. Register callbacks,
    renderer choices and dependencies only during setup. Each operation starts
    with fresh cache and canonical preparation state. Callbacks inherited from
    global templates retain their own state.

    During setup, register hooks, select renderers with `set_renderers` and declare
    inputs with `watch`. Registration closes when setup returns. Setup may read
    `settings`, `source_root`, `config_root` and `output_root` but must not change them.

    Object and docstring hooks change the documentation that every alias of an object
    shares, including whether the object is excluded. Keep their edits to the object's
    own docstring and metadata. Use a renderer to customise how an object appears
    on a page.

    Attributes
    ----------
    settings
        The parser, introspection and rendering settings. Read-only.
    source_root
        The project's documentation source directory, or `None` outside a project.
    config_root
        The directory of the selected configuration file, or `None` outside a project.
    cache
        The extension's own values, shared by setup and its callbacks for one run.
    """

    def __init__(self, settings: Settings, source: _ExtensionSource | None = None) -> None:
        """
        Copy the global hooks and start empty, without loading the extension file

        Parameters
        ----------
        settings
            The parser, introspection and rendering settings for this operation.
        source
            The extension file and the project's directories, or `None` when there is
            no extension file and only the global hooks apply.
        """
        self.settings = settings
        self.source_root = source.source_root if source else None
        self.config_root = source.config_root if source else None
        self.cache: dict[str, object] = {}
        self._source = source
        self._imports = _ImportOwner(source) if source is not None else None
        self._object_hooks = OBJECT_HOOKS.copy()
        self._parsed_hooks = PARSED_HOOKS.copy()
        self._renderers = Renderers()
        self._declared_inputs: list[Path] = []
        self._input_hashes: dict[Path, str] = {}
        self._prepared_objects: dict[int, _PreparedObject] = {}
        self._loaded = False
        self._closed = False
        self._registration_open = True

    @property
    def renderers(self) -> Renderers:
        """Validated renderer choices selected during setup"""
        return self._renderers

    @property
    def imported_paths(self) -> frozenset[Path]:
        """The project source files the extension imported, still available after `close`"""
        return self._imports.paths if self._imports is not None else frozenset()

    @property
    def declared_inputs(self) -> tuple[Path, ...]:
        """The absolute files, directories and globs passed to `watch`, in call order"""
        return tuple(self._declared_inputs)

    @property
    def watch_paths(self) -> tuple[Path, ...]:
        """
        The paths a preview watches, with globs unexpanded and the extension's directory

        Reading them never runs setup and still works after `close`. A preview chooses
        what to watch once, from the paths of its first build.
        """
        if self._source is None:
            return ()
        return _extension_inputs.watch_paths(
            self._source.entry_path, self.imported_paths, self.declared_inputs
        )

    def fingerprint(self) -> str | None:
        """
        Hash the extension file and every input it uses, once pages are collected

        The hash covers helpers imported during rendering, the inputs declared with
        `watch` and the files each declared glob currently matches. File digests are
        cached for this operation only.

        Returns
        -------
        :
            The hash, or `None` without an extension file, so that reference pages
            carry no fingerprint comment.
        """
        if self._source is None:
            return None
        with self.error_context("inputs"):
            return _extension_inputs.fingerprint(
                self._source.entry_path,
                self.imported_paths,
                self.declared_inputs,
                self._input_hashes,
            )

    def _register(
        self, registry: HookRegistry[_Hook], callback: _Hook | None, priority: int
    ) -> _Hook | Callable[[_Hook], _Hook]:
        """Register a callable while setup remains open, directly or through a decorator"""
        self._check_registration()

        def add(handler: _Hook) -> _Hook:
            self._check_registration()
            if not callable(handler):
                raise TypeError("An extension handler must be callable.")
            _ = registry.register(handler, priority=priority)
            return handler

        return add(callback) if callback is not None else add

    def _check_registration(self) -> None:
        """Reject changes after setup or cleanup"""
        if not self._registration_open or self._closed:
            raise RuntimeError("API reference extension registration is closed after setup.")

    @overload
    def on_object_resolved(
        self, callback: ObjectResolvedHook, priority: int = 0
    ) -> ObjectResolvedHook: ...

    @overload
    def on_object_resolved(
        self, callback: None = None, priority: int = 0
    ) -> Callable[[ObjectResolvedHook], ObjectResolvedHook]: ...

    def on_object_resolved(
        self, callback: ObjectResolvedHook | None = None, priority: int = 0
    ) -> ObjectResolvedHook | Callable[[ObjectResolvedHook], ObjectResolvedHook]:
        """
        Register an object hook, which runs on each object before its docstring is parsed

        A hook may edit the object's docstring or documentation metadata, or exclude
        the object. It must leave the object's members, bases and descendants as they
        are. Every alias of the object shares the result, including an exclusion. To
        change how the object looks in one place, use a renderer method or a body
        callback.

        Parameters
        ----------
        callback
            A callable that receives the Griffe object, never an alias. Return that
            object, a replacement, or `None` to exclude it. Omit `callback` to use this
            method as a decorator.
        priority
            The run order. Lower values run first, and equal values run in
            registration order, with global hooks before the ones registered here.

        Returns
        -------
        :
            `callback`, or a decorator that registers one when `callback` is omitted.

        Raises
        ------
        RuntimeError
            If setup has finished or the extension is closed.
        """
        return self._register(self._object_hooks, callback, priority)

    @overload
    def on_docstring_parsed(
        self, callback: DocstringParsedHook, priority: int = 0
    ) -> DocstringParsedHook: ...

    @overload
    def on_docstring_parsed(
        self, callback: None = None, priority: int = 0
    ) -> Callable[[DocstringParsedHook], DocstringParsedHook]: ...

    def on_docstring_parsed(
        self, callback: DocstringParsedHook | None = None, priority: int = 0
    ) -> DocstringParsedHook | Callable[[DocstringParsedHook], DocstringParsedHook]:
        """
        Register a docstring hook, which runs on each object's parsed docstring sections

        Docstring hooks run only for objects that have a docstring. Every alias,
        reference page, the text export and symbol queries use the sections they
        return. A hook may change the object's own sections but must leave its members
        and descendants as they are.

        Parameters
        ----------
        callback
            A callable that receives the prepared object and its list of parsed
            sections, and returns the sections to keep, which may include
            replacements. It must not return `None`. Omit `callback` to use this
            method as a decorator.
        priority
            The run order. Lower values run first, and equal values run in
            registration order, with global hooks before the ones registered here.

        Returns
        -------
        :
            `callback`, or a decorator that registers one when `callback` is omitted.

        Raises
        ------
        RuntimeError
            If setup has finished or the extension is closed.
        """
        return self._register(self._parsed_hooks, callback, priority)

    def set_renderers(self, renderers: Renderers) -> None:
        """
        Select the renderer classes; call this during setup

        Parameters
        ----------
        renderers
            The renderer choices. Kinds left out keep the default renderer.

        Raises
        ------
        RuntimeError
            If setup has finished or the extension is closed.
        TypeError
            If `renderers` is not a `Renderers` instance.
        """
        self._check_registration()
        if not isinstance(renderers, Renderers):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError("`renderers` must be a Renderers instance.")
        self._renderers = renderers

    def watch(self, path: str | Path) -> None:
        """
        Declare a file, directory or glob that the extension reads

        Resolve relative declarations against the configured entry file's
        directory. Absolute declarations also work without a configured source.
        Include these inputs in reference fingerprints and preview observation;
        declaring a dependency does not copy it into the generated project.

        Parameters
        ----------
        path
            A file, directory or glob, which need not exist yet. The final fingerprint
            covers a directory's entries and the files a glob matches. A running
            preview keeps watching the paths it started with, so restart it after
            declaring an input outside them.
        """
        self._check_registration()
        declared = Path(path)
        if not declared.is_absolute():
            if self._source is None:
                raise ValueError("Relative extension inputs require a configured entry file.")
            declared = self._source.entry_path.parent / declared
        self._declared_inputs.append(declared.resolve())

    def load(self) -> None:
        """
        Run configured entry and setup once, then freeze registration

        Load relative helpers from current source bytes and preserve installed-package
        caching. Restore global hook templates if configured code changes them and
        reject that registration path. Report load and setup failures in their actual
        phase, preserve their causes and release owned imports.
        """
        if self._closed:
            raise RuntimeError("The API reference extension is closed.")
        if self._loaded:
            return
        if self._imports is not None:
            object_snapshot = OBJECT_HOOKS.snapshot()
            parsed_snapshot = PARSED_HOOKS.snapshot()

            def check_templates() -> None:
                if (
                    OBJECT_HOOKS.snapshot() != object_snapshot
                    or PARSED_HOOKS.snapshot() != parsed_snapshot
                ):
                    raise RuntimeError(
                        "Configured extensions must register through the supplied extension, not global hooks."
                    )

            try:
                with self.error_context("load"):
                    module = self._imports.load()
                    check_templates()
                with self.error_context("setup"):
                    setup = getattr(module, "setup", None)
                    if not callable(setup):
                        raise TypeError(
                            "The extension entry must define callable setup(extension)."
                        )
                    _ = setup(self)
                    check_templates()
            finally:
                OBJECT_HOOKS.restore(object_snapshot)
                PARSED_HOOKS.restore(parsed_snapshot)
        self._registration_open = False
        self._loaded = True

    def is_prepared(self, obj: gf.Object | gf.Alias) -> bool:
        """Check whether a canonical object's documentation has been prepared"""
        try:
            target = obj.final_target if isinstance(obj, gf.Alias) else obj
        except (gf.AliasResolutionError, gf.CyclicAliasError):
            return False
        return id(target) in self._prepared_objects

    def prepare(
        self,
        obj: gf.Object | gf.Alias,
        *,
        get_object: Callable[..., gf.Object | gf.Alias] | None = None,
    ) -> gf.Object | gf.Alias | None:
        """
        Prepare an object's documentation once for this operation

        Run the object hooks, parse the docstring against the class constructor where
        one applies, and run the docstring hooks, all before documentation nodes are
        built. Every authored alias of the object shares the result, including an
        exclusion. The extension keeps a strong reference to each original object, so a
        temporary snippet that reuses a name is prepared on its own.

        Parameters
        ----------
        obj
            The loaded object, or an authored alias.
        get_object
            The loader for alias targets that are not loaded yet, or `None` to require
            targets that are already in the model.

        Returns
        -------
        :
            The prepared object, the authored alias wrapping it, or `None` when an
            object hook excludes the alias's target.
        """
        from ._constructor import parse_class_docstring
        from ._parameter_docs import prepare_parameter_docs
        from .introspect import get_parser_defaults, resolve_alias
        from .resolve import resolution_lang

        self.load()
        original = resolve_alias(obj, get_object)
        cached = self._prepared_objects.get(id(original))
        if cached is not None:
            return self._appearance(obj, original, cached.result)

        result: gf.Object | None = original
        canonical_objects = [original]
        token = resolution_lang.set(self.settings.lang)
        try:
            prepared_replacement: _PreparedObject | None = None
            with self.error_context("object_resolved", original.path):
                for callback in self._object_hooks:
                    transformed = cast("object", callback(result))
                    if transformed is None:
                        result = None
                        break
                    if not isinstance(transformed, (gf.Object, gf.Alias)):
                        raise TypeError("An object handler must return an object or None.")
                    result = resolve_alias(transformed, get_object)
                    if not any(candidate is result for candidate in canonical_objects):
                        canonical_objects.append(result)
                    prepared_replacement = self._prepared_objects.get(id(result))
                    if prepared_replacement is not None:
                        result = prepared_replacement.result
                        break
                if prepared_replacement is None and result is not None:
                    prepare_parameter_docs(result)
                    if result.docstring is not None:
                        result.docstring.parent = result
                        result.docstring.parser = gf.Parser(self.settings.parser)
                        result.docstring.parser_options = cast(
                            "DocstringOptions", get_parser_defaults(self.settings.parser)
                        )
                        result.docstring.__dict__.pop("parsed", None)
            if prepared_replacement is None and result is not None and result.docstring is not None:
                with self.error_context("docstring_parsed", original.path):
                    if result.is_class:
                        parse_class_docstring(cast("gf.Class", result))
                    sections = result.docstring.parsed
                    for callback in self._parsed_hooks:
                        transformed_sections = cast(
                            "list[gf.DocstringSection] | None", callback(result, sections)
                        )
                        if transformed_sections is None:
                            raise TypeError(
                                "A parsed-section handler must return sections, not None."
                            )
                        sections = transformed_sections
                    result.docstring.__dict__["parsed"] = sections
        finally:
            resolution_lang.reset(token)
        for canonical in canonical_objects:
            self._prepared_objects[id(canonical)] = _PreparedObject(canonical, result)
        return self._appearance(obj, original, result)

    @staticmethod
    def _appearance(
        obj: gf.Object | gf.Alias, original: gf.Object, result: gf.Object | None
    ) -> gf.Object | gf.Alias | None:
        """Give the prepared result an authored alias's name without copying its documentation"""
        if result is None or not isinstance(obj, gf.Alias):
            return result
        if result is original:
            return obj
        return gf.Alias(
            obj.name,
            result,
            parent=obj.parent,
            lineno=obj.lineno,
            endlineno=obj.endlineno,
            runtime=obj.runtime,
            inherited=obj.inherited,
        )

    def error_context(self, phase: str, subject: str | None = None) -> _ExtensionErrorContext:
        """Describe failures in one configured phase and release owned imports"""
        entry_path = self._source.entry_path if self._source is not None else None
        return _ExtensionErrorContext(entry_path, self.close, phase, subject)

    def close(self) -> None:
        """
        Release the project modules the extension imported, without loading an unused extension

        Calling `close` again does nothing. The imported paths stay available through
        `imported_paths` and `watch_paths`.
        """
        if self._closed:
            return
        self._closed = True
        self._registration_open = False
        if self._imports is not None:
            self._imports.close()
