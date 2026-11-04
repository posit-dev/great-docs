"""Tests for blocked external access and permitted loopback connections"""

import socket

import pytest


def test_refuses_lookup_of_outside_host():
    with pytest.raises(pytest.fail.Exception, match="'example.com'"):
        socket.getaddrinfo("example.com", 443)


def test_refuses_connection_to_outside_address():
    # Use a documentation address to avoid targeting a public service.
    with socket.socket() as sock:
        with pytest.raises(pytest.fail.Exception, match="'192.0.2.1'"):
            sock.connect(("192.0.2.1", 80))


def test_permits_loopback_connection():
    with socket.create_server(("127.0.0.1", 0)) as server:
        with socket.create_connection(server.getsockname()[:2], timeout=5):
            pass
