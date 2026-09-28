import zlib

import pytest

from great_docs._interlinks.sphinx_inventory import (
    ROLE_SYNONYMS,
    Inventory,
    InventoryEntry,
    decode,
    encode,
    is_builtin_exception,
    role_for_kind,
)


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


def test_a_function_inside_a_class_is_a_method():
    assert role_for_kind("function", in_class=True) == "method"


def test_a_function_outside_a_class_stays_a_function():
    assert role_for_kind("function", in_class=False) == "function"


def test_an_attribute_inside_a_class_is_an_attribute():
    assert role_for_kind("attribute", in_class=True) == "attribute"


def test_an_attribute_outside_a_class_is_data():
    """Sphinx publishes a module-level name as py:data."""
    assert role_for_kind("attribute", in_class=False) == "data"


def test_a_type_alias_is_a_type():
    assert role_for_kind("type alias", in_class=False) == "type"


def test_a_class_keeps_its_kind():
    assert role_for_kind("class", in_class=False) == "class"


def test_an_exception_class_is_an_exception():
    """Sphinx publishes a class deriving from BaseException as py:exception."""
    assert role_for_kind("class", in_class=False, is_exception=True) == "exception"


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Exception", True),
        ("BaseException", True),
        ("ValueError", True),
        # A dotted base names its own last component.
        ("builtins.OSError", True),
        ("int", False),
        ("object", False),
        # A name Python does not ship says nothing about its ancestry here.
        ("MyError", False),
    ],
)
def test_pythons_own_exceptions_are_recognised_by_name(name, expected):
    assert is_builtin_exception(name) is expected


def test_the_generic_role_constrains_nothing():
    assert ROLE_SYNONYMS["obj"] == ""


def test_the_abbreviations_map_to_role_names():
    assert ROLE_SYNONYMS["func"] == "function"
    assert ROLE_SYNONYMS["meth"] == "method"
    assert ROLE_SYNONYMS["attr"] == "attribute"
    assert ROLE_SYNONYMS["mod"] == "module"
    assert ROLE_SYNONYMS["exc"] == "exception"


def test_encode_and_decode_round_trip_every_field_shorthand():
    """The two shorthands the format allows must survive a round trip."""
    entries = (
        InventoryEntry("mypkg.Thing", "py", "class", 1, "reference/Thing.html", "mypkg.Thing"),
        InventoryEntry("a name with spaces", "std", "label", -1, "guide.html", "Shown"),
        InventoryEntry("mypkg.empty", "py", "data", 1, "", "mypkg.empty"),
    )
    inv = Inventory(project="mypkg", version="1.0", entries=entries)

    result = decode(encode(inv))

    assert result.project == "mypkg"
    assert result.version == "1.0"
    assert result.entries == entries
