"""
Prepare rendered citation fixtures and block external network access

A fresh checkout has no rendered Gauntlet sites. Build the citation fixtures
before collection so the rendered-HTML assertions run without a complete
`make hub-build`.

Tests without the `network` marker fail on lookups or socket connections to
non-local hosts. The guard applies only to the test process; subprocesses can
still access the network.
"""

from __future__ import annotations

import ipaddress
import socket
import warnings
from collections.abc import Iterator
from typing import Any, NoReturn

import pytest

from tests.gauntlet_sites import RENDERED_DIR


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
