"""
Prepare shared fixtures and block external network access

A fresh checkout has no rendered Gauntlet sites. Build the citation fixtures
before collection so the rendered-HTML assertions run without a complete
`make hub-build`.

Tests without the `network` marker fail on lookups or socket connections to
non-local hosts. The guard applies only to the test process; subprocesses can
still access the network.

`write_extension` writes extension entry files. `make_reference` configures API
references and closes each one when the test ends, even when the test fails.
"""

from __future__ import annotations

import ipaddress
import socket
import sys
import warnings
from collections.abc import Iterator, Mapping
from contextlib import ExitStack
from pathlib import Path
from textwrap import dedent
from typing import Any, NoReturn

import pytest

from great_docs._apiref._extension_loading import _ExtensionSource
from great_docs._apiref.api_reference import APIReference
from tests.gauntlet_sites import RENDERED_DIR
from tests.support import MakeReference, WriteExtension, reference_from_options


def _is_local(host: str | bytes | None) -> bool:
    """
    Recognise `localhost`, loopback addresses and wildcard addresses

    Parameters
    ----------
    host
        The host supplied to a socket lookup or connection. `None` and an
        empty string represent wildcard addresses.

    Returns
    -------
    :
        `True` for `localhost` and for loopback and wildcard addresses.
    """
    if isinstance(host, bytes):
        host = host.decode()
    if not host or host == "localhost":
        return True
    try:
        # An IPv6 scope identifier such as `%lo0` does not affect locality.
        address = ipaddress.ip_address(host.partition("%")[0])
    except ValueError:
        return False
    return address.is_loopback or address.is_unspecified


@pytest.fixture(autouse=True)
def refuse_network(request: pytest.FixtureRequest) -> Iterator[None]:
    """
    Block external host lookups and socket connections for unmarked tests

    The failure names the host. `pytest.fail` raises an exception that handlers
    for `OSError` or `requests.RequestException` do not catch. Tests marked
    `network` bypass the guard.

    Parameters
    ----------
    request
        The test whose `network` marker controls access.

    Yields
    ------
    :
        Nothing; the guard remains active until test teardown.
    """
    if request.node.get_closest_marker("network"):
        yield
        return

    getaddrinfo = socket.getaddrinfo
    connect = socket.socket.connect
    connect_ex = socket.socket.connect_ex

    def refuse(host: object) -> NoReturn:
        pytest.fail(
            f"{request.node.nodeid} tried to reach {host!r} over the network. "
            "Give the code under test a fake, such as `StubRemote`, "
            "or mark the test `network`."
        )

    def guarded_getaddrinfo(host: str | bytes | None, *args: Any, **kwargs: Any) -> Any:
        if not _is_local(host):
            refuse(host)
        return getaddrinfo(host, *args, **kwargs)

    def check_address(sock: socket.socket, address: Any) -> None:
        # Unix domain sockets stay local and do not use IP address tuples.
        if sock.family in (socket.AF_INET, socket.AF_INET6) and not _is_local(address[0]):
            refuse(address[0])

    def guarded_connect(sock: socket.socket, address: Any) -> None:
        check_address(sock, address)
        connect(sock, address)

    def guarded_connect_ex(sock: socket.socket, address: Any) -> int:
        check_address(sock, address)
        return connect_ex(sock, address)

    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
        patcher.setattr(socket.socket, "connect", guarded_connect)
        patcher.setattr(socket.socket, "connect_ex", guarded_connect_ex)
        yield


@pytest.fixture
def write_extension(tmp_path: Path) -> WriteExtension:
    """
    Provide a factory that writes `extension.py` and returns its extension source

    Parameters
    ----------
    tmp_path
        The default directory for `extension.py`.

    Returns
    -------
    :
        The factory. A later call with the same directory replaces the file.
    """

    def write(
        setup: str, *, config_root: Path | None = None, source_root: Path | None = None
    ) -> _ExtensionSource:
        root = config_root or tmp_path
        root.mkdir(parents=True, exist_ok=True)
        entry = root / "extension.py"
        entry.write_text(dedent(setup), encoding="utf-8")
        return _ExtensionSource(entry, root, source_root or root)

    return write


def _forget_package(name: str) -> None:
    """
    Remove a package and its submodules from `sys.modules`

    Parameters
    ----------
    name
        The importable name of the package.
    """
    for module in [key for key in sys.modules if key == name or key.startswith(f"{name}.")]:
        del sys.modules[module]


@pytest.fixture
def make_reference(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[MakeReference]:
    """
    Provide a factory for API references that close when the test ends

    Parameters
    ----------
    tmp_path
        The directory that receives the packages the factory writes.
    monkeypatch
        The patcher that changes `sys.path` and the working directory and restores
        both after the test.

    Yields
    ------
    :
        The factory. Teardown closes every reference it built, even after a failed
        test, and removes the modules of the packages it wrote.
    """
    with ExitStack() as cleanup:

        def make(
            block: Mapping[str, object],
            source: _ExtensionSource | None = None,
            *,
            package_files: Mapping[str, str] | None = None,
            output_root: Path | None = None,
        ) -> APIReference:
            if package_files is not None:
                name = str(block["package"])
                for path, code in package_files.items():
                    target = tmp_path / name / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(dedent(code), encoding="utf-8")
                monkeypatch.syspath_prepend(str(tmp_path))
                # A module left by an earlier test with the same package name would
                # shadow the files just written.
                _forget_package(name)
                cleanup.callback(_forget_package, name)
            if output_root is not None:
                output_root.mkdir(parents=True, exist_ok=True)
                monkeypatch.chdir(output_root)
            reference = reference_from_options(
                block, extension_source=source, output_root=output_root
            )
            cleanup.callback(reference.close)
            return reference

        yield make


def pytest_configure(config: pytest.Config) -> None:
    """
    Prepare the citation Gauntlet sites before collection

    The rendered-output tests determine their parameters during import, before
    a fixture could build the required sites. Existing sites remain unchanged.

    Environmental failures warn and leave the affected sites unavailable, so
    their rendered-output tests skip. These failures include unavailable
    imports, invalid Gauntlet specifications, and filesystem errors while
    managing the sentinel lock. The site builder handles render failures for
    each package. Other exceptions abort the session because they indicate a
    defect in the fixture builder.

    Parameters
    ----------
    config
        The pytest config object. Unused.

    """
    try:
        from tests import gauntlet_sites

        if not gauntlet_sites.quarto_available():
            return
        gauntlet_sites.ensure_sites(RENDERED_DIR, gauntlet_sites.CITATION_SITES)
    except (OSError, ImportError, ValueError, KeyError) as exc:
        # Preserve the rest of the test session when the optional rendered
        # fixtures are unavailable. Unexpected builder defects still propagate.
        warnings.warn(f"could not prepare Gauntlet citation sites: {exc}", stacklevel=2)
