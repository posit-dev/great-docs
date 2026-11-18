"""
The extension that customises one API reference

An `Extension` holds one operation's registrations, renderer choices, `cache` and
declared inputs. It prepares each object's documentation once. Registration closes
when the extension file's `setup` returns, and closing the extension releases the
project modules it imported.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
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
    from collections.abc import Generator

    from griffe import DocstringOptions

    from ._settings import Settings

_Hook = TypeVar("_Hook", bound=Callable[..., object])


class ExtensionError(Exception):
    """An error in the API reference extension, naming its file and phase"""


class Extension:
    """
    The API reference extension that `setup(extension)` receives

    Great Docs creates a new `Extension` each time it generates the API reference, so
    `cache` starts empty and every object is prepared afresh. Hooks registered
    globally through `great_docs.hooks` are shared by every run and keep their own
    state.

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
    output_root
        The directory the documentation is generated into, or `None` when nothing is
        written.
    cache
        The extension's own values, shared by setup and its callbacks for one run.
    """

    def __init__(
        self,
        settings: Settings,
        source: _ExtensionSource | None = None,
        *,
        output_root: Path | None = None,
    ) -> None:
        """
        Copy the global hooks and start empty, without loading the extension file

        Parameters
        ----------
        settings
            The parser, introspection and rendering settings for this operation.
        source
            The extension file and the project's directories, or `None` when there is
            no extension file and only the global hooks apply.
        output_root
            The directory the documentation is generated into, or `None` when nothing
            is written.
        """
        self.settings = settings
        self.source_root = source.source_root if source else None
        self.config_root = source.config_root if source else None
        self.output_root = output_root
        self.cache: dict[str, object] = {}
        self._source = source
        self._imports = _ImportOwner(source) if source is not None else None
        self._object_hooks = OBJECT_HOOKS.copy()
        self._parsed_hooks = PARSED_HOOKS.copy()
        self._renderers = Renderers()
        self._declared_inputs: list[Path] = []
        self._input_hashes: dict[Path, str] = {}
        self._prepared: dict[gf.Object, gf.Object | None] = {}
        self._loaded = False
        self._closed = False
        self._registration_open = True

    @property
    def renderers(self) -> Renderers:
        """The renderer choices from setup, which the first read runs"""
        self.load()
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
        """
        Register a callable while setup remains open, directly or through a decorator

        Parameters
        ----------
        registry
            The registry of this extension's handlers for one hook.
        callback
            The handler to register, or `None` to return a decorator that registers one.
        priority
            The run order. Lower values run first.

        Returns
        -------
        :
            `callback`, or a decorator that registers one when `callback` is `None`.

        Raises
        ------
        RuntimeError
            If setup has finished or the extension is closed.
        """
        self._check_registration()

        def add(handler: _Hook) -> _Hook:
            """
            Register a handler with the captured registry and priority

            Parameters
            ----------
            handler
                The callable to register.

            Returns
            -------
            :
                `handler`, unchanged, so that `add` works as a decorator.

            Raises
            ------
            RuntimeError
                If setup has finished or the extension is closed.
            TypeError
                If `handler` is not callable.
            """
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

        A relative path resolves against the extension file's directory. Declared
        inputs count towards the reference fingerprint and preview watches them, but
        Great Docs does not copy them into the generated project.

        Parameters
        ----------
        path
            A file, directory or glob, which need not exist yet. The final fingerprint
            covers a directory's entries and the files a glob matches. A running
            preview keeps watching the paths it started with, so restart it after
            declaring an input outside them.

        Raises
        ------
        RuntimeError
            If setup has finished or the extension is closed.
        ValueError
            If there is no extension file.
        """
        self._check_registration()
        if self._source is None:
            raise ValueError("Extension inputs require a configured entry file.")
        self._declared_inputs.append((self._source.entry_path.parent / path).resolve())

    def load(self) -> None:
        """
        Import the extension file and run its `setup` once, then close registration

        The extension file and the helpers it imports relatively load from their current
        source, while installed packages keep their usual import cache. Extension code
        that registers hooks globally, instead of through the extension, fails, and the
        global hooks are restored. A failure while loading or in setup raises
        `ExtensionError` naming that phase, chained to the original error. It also
        closes the extension, which releases the imported project modules and stops a
        failed setup from running again.
        """
        if self._closed:
            raise RuntimeError("The API reference extension is closed.")
        if self._loaded:
            return
        # Setup may read `renderers`, which loads, so mark the extension loaded before
        # setup runs. A failed load closes the extension, so it cannot be retried.
        self._loaded = True
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
            except BaseException:
                self.close()
                raise
            finally:
                OBJECT_HOOKS.restore(object_snapshot)
                PARSED_HOOKS.restore(parsed_snapshot)
        self._registration_open = False

    def is_prepared(self, obj: gf.Object | gf.Alias) -> bool:
        """
        Check whether a canonical object's documentation has been prepared

        Parameters
        ----------
        obj
            The loaded object, or an alias to it.

        Returns
        -------
        :
            Whether this extension has prepared the alias's final target or the object,
            including preparation that excluded it. `False` for an alias that does not
            resolve.
        """
        try:
            target = obj.final_target if isinstance(obj, gf.Alias) else obj
        except (gf.AliasResolutionError, gf.CyclicAliasError):
            return False
        return target in self._prepared

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
        from .introspect import resolve_alias
        from .resolve import resolution_lang

        self.load()
        original = resolve_alias(obj, get_object)
        if original in self._prepared:
            return self._appearance(obj, original, self._prepared[original])

        seen = {original}
        token = resolution_lang.set(self.settings.lang)
        try:
            with self.error_context("object_resolved", original.path):
                result = self._apply_object_resolved_hooks(original, seen, get_object)
            # Every recorded result is also a key, so a result that is a key was parsed by
            # an earlier preparation.
            if result is not None and result not in self._prepared:
                self._parse_docstring(result, original.path)
        finally:
            resolution_lang.reset(token)
        self._prepared.update(dict.fromkeys(seen, result))
        return self._appearance(obj, original, result)

    def _apply_object_resolved_hooks(
        self,
        obj: gf.Object,
        seen: set[gf.Object],
        get_object: Callable[..., gf.Object | gf.Alias] | None,
    ) -> gf.Object | None:
        """
        Run the object hooks until they finish, exclude the object or reach a prepared one

        Parameters
        ----------
        obj
            The canonical object that the first hook receives.
        seen
            The canonical objects met so far. Each hook's resolved result is added, so
            all of them share the final result.
        get_object
            The loader for alias targets that are not loaded yet, or `None` to require
            targets that are already in the model.

        Returns
        -------
        :
            The final object, `None` for an exclusion, or the recorded result of the
            first already prepared object that a hook returns.
        """
        from .introspect import resolve_alias

        for callback in self._object_hooks:
            transformed = cast("object", callback(obj))
            if transformed is None:
                return None
            if not isinstance(transformed, (gf.Object, gf.Alias)):
                raise TypeError("An object handler must return an object or None.")
            obj = resolve_alias(transformed, get_object)
            seen.add(obj)
            if obj in self._prepared:
                return self._prepared[obj]
        return obj

    def _parse_docstring(self, obj: gf.Object, subject: str) -> None:
        """
        Parse an object's docstring with the reference's parser, then run the docstring hooks

        Parameters
        ----------
        obj
            The last object hook's result, which no earlier preparation has parsed.
        subject
            The original object's path, which error messages name.
        """
        from ._constructor import parse_class_docstring
        from ._parameter_docs import prepare_parameter_docs
        from .introspect import get_parser_defaults

        with self.error_context("object_resolved", subject):
            prepare_parameter_docs(obj)
            if obj.docstring is not None:
                obj.docstring.parent = obj
                obj.docstring.parser = gf.Parser(self.settings.parser)
                obj.docstring.parser_options = cast(
                    "DocstringOptions", get_parser_defaults(self.settings.parser)
                )
                obj.docstring.__dict__.pop("parsed", None)
        if obj.docstring is None:
            return
        with self.error_context("docstring_parsed", subject):
            if obj.is_class:
                parse_class_docstring(cast("gf.Class", obj))
            sections = obj.docstring.parsed
            obj.docstring.__dict__["parsed"] = self._apply_docstring_parsed_hooks(obj, sections)

    def _apply_docstring_parsed_hooks(
        self, obj: gf.Object, sections: list[gf.DocstringSection]
    ) -> list[gf.DocstringSection]:
        """
        Pass each docstring hook's sections to the next and return the last result

        Parameters
        ----------
        obj
            The object whose docstring was parsed.
        sections
            The parsed docstring sections.

        Returns
        -------
        :
            The sections that the last hook returned, or `sections` when there are no
            hooks.

        Raises
        ------
        TypeError
            If a hook returns `None`.
        """
        for callback in self._parsed_hooks:
            transformed = cast("list[gf.DocstringSection] | None", callback(obj, sections))
            if transformed is None:
                raise TypeError("A parsed-section handler must return sections, not None.")
            sections = transformed
        return sections

    @staticmethod
    def _appearance(
        obj: gf.Object | gf.Alias, original: gf.Object, result: gf.Object | None
    ) -> gf.Object | gf.Alias | None:
        """
        Give the prepared result an authored alias's name without copying its documentation

        Parameters
        ----------
        obj
            The object or authored alias that was asked for.
        original
            The canonical object that was prepared.
        result
            The prepared object, or `None` when preparation excluded it.

        Returns
        -------
        :
            `result` for a canonical object or an exclusion, `obj` when preparation kept
            the original object, or a new alias with `obj`'s name and placement that
            targets `result`.
        """
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

    @contextmanager
    def error_context(self, phase: str, subject: str | None = None) -> Generator[None]:
        """
        Re-raise an error from extension code as an `ExtensionError` naming the phase

        With an extension file, an `Exception` raised in the block becomes an
        `ExtensionError` chained to it. Three kinds of error pass through unchanged: an
        existing `ExtensionError`, any error when there is no extension file, and an
        error such as `KeyboardInterrupt` that is not an `Exception`. The imported
        project modules stay loaded until the extension closes.

        Parameters
        ----------
        phase
            The phase that the error message names, such as `setup`.
        subject
            The object or appearance being processed, or `None` for the whole phase.
        """
        try:
            yield
        except BaseException as error:
            if (
                self._source is None
                or not isinstance(error, Exception)
                or isinstance(error, ExtensionError)
            ):
                raise
            described = f" for {subject}" if subject else ""
            raise ExtensionError(
                f"API reference extension {self._source.entry_path}: {phase}{described}: {error}"
            ) from error

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
