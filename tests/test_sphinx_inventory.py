import zlib

import pytest

from great_docs._sphinx_inventory import Inventory, InventoryEntry, decode, encode


def _bytes(*lines: str) -> bytes:
    """Build a version 2 inventory from record lines."""
    header = (
        b"# Sphinx inventory version 2\n"
        b"# Project: demo\n"
        b"# Version: 1.2\n"
        b"# The remainder of this file is compressed using zlib.\n"
    )
    body = "".join(f"{line}\n" for line in lines).encode("utf-8")
    return header + zlib.compress(body, 9)


def test_decode_reads_an_inventory():
    """Header fields and a record, as another project writes them."""
    inv = decode(_bytes("demo.Thing py:class 1 api/thing.html#demo.Thing -"))
    assert inv.project == "demo"
    assert inv.version == "1.2"
    assert inv.entries == (
        InventoryEntry(
            name="demo.Thing",
            domain="py",
            role="class",
            priority=1,
            uri="api/thing.html#demo.Thing",
            dispname="demo.Thing",
        ),
    )


def test_decode_expands_the_shorthands():
    """A uri ending in `$` takes an anchor equal to the name."""
    inv = decode(_bytes("demo.Thing py:class -1 api/thing.html#$ Thing"))
    assert inv.entries[0].uri == "api/thing.html#demo.Thing"
    assert inv.entries[0].dispname == "Thing"
    assert inv.entries[0].priority == -1


def test_decode_rejects_another_format():
    with pytest.raises(ValueError):
        decode(b"# Sphinx inventory version 1\nnot really\n")


def test_encode_round_trips():
    inv = Inventory(
        project="demo",
        version="1.2",
        entries=(
            InventoryEntry(
                "demo.Thing", "py", "class", 1, "api/thing.html#demo.Thing", "demo.Thing"
            ),
            InventoryEntry("demo.go", "py", "function", -1, "api/go.html#demo.go", "Go"),
        ),
    )
    assert decode(encode(inv)) == inv


def test_encode_compresses_the_records():
    """Everything after the four header lines is a zlib stream."""
    inv = Inventory("demo", "1.2", (InventoryEntry("a.B", "py", "class", 1, "b.html", "a.B"),))
    data = encode(inv)
    body = data.split(b"\n", 4)[4]
    assert zlib.decompress(body).decode() == "a.B py:class 1 b.html -\n"
