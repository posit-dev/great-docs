"""
Scoped extension registration and lifetime for one API-reference operation

Snapshot global hook templates without copying callback state. Configured setup
registers through the supplied owner and finishes before registration freezes.
"""

from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Callable, TypeVar, overload

from ..hooks._docstring_parsed import REGISTRY as PARSED_HOOKS
from ..hooks._docstring_parsed import DocstringParsedHook
from ..hooks._object_resolved import REGISTRY as OBJECT_HOOKS
from ..hooks._object_resolved import ObjectResolvedHook
from ..hooks._registry import HookRegistry
from ._extension_loading import _ExtensionSource, _ImportOwner
from ._rendering._renderers import Renderers

if TYPE_CHECKING:
    from ._settings import Settings

_Hook = TypeVar("_Hook", bound=Callable[..., object])


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
        return None

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
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
    Registrations, renderer choices and project cache for one API reference

    Setup may inspect `settings`, `source_root` and `config_root` and keep its
    own values in `cache`. Treat the settings and roots as read-only. Register
    handlers and dependencies only during setup. Each operation owns fresh state;
    callback objects inherited from global templates retain their own state.

    Attributes
    ----------
    settings
        The operation's semantic and presentation settings, read-only by contract.
    source_root
        The original documentation source directory, or `None` without project context.
    config_root
        The selected configuration file's directory, or `None` without project context.
    cache
        The extension's own values, shared by setup and its callbacks for one run.
    """

    def __init__(self, settings: Settings, source: _ExtensionSource | None = None) -> None:
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

    def _register(
        self, registry: HookRegistry[_Hook], callback: _Hook | None, priority: int
    ) -> _Hook | Callable[[_Hook], _Hook]:
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
        Register a current-object transform before constructor-aware parsing

        Return the object to retain, a replacement, or `None` to exclude it.
        Lower priorities run first; ties preserve registration order. Use this
        method directly or as a decorator during setup.
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
        Register a parsed-section transform for objects with docstrings

        Return the sections to retain or replace. Returning `None` is invalid.
        Lower priorities run first; ties preserve registration order. Use this
        method directly or as a decorator during setup.
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
        """
        self._check_registration()
        declared = Path(path)
        if not declared.is_absolute():
            if self._source is None:
                raise ValueError("Relative extension inputs require a configured entry file.")
            declared = self._source.entry_path.parent / declared
        self._declared_inputs.append(declared.resolve())

    def load(self) -> None:
        """Load configured setup once and freeze registration when it finishes"""
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

    def error_context(self, phase: str, subject: str | None = None) -> _ExtensionErrorContext:
        """Describe failures in one configured phase and release owned imports"""
        entry_path = self._source.entry_path if self._source is not None else None
        return _ExtensionErrorContext(entry_path, self.close, phase, subject)

    def close(self) -> None:
        """Release owned imports without loading an unused extension"""
        if self._closed:
            return
        self._closed = True
        self._registration_open = False
        if self._imports is not None:
            self._imports.close()
