from great_docs._apiref.inventory import reference_uri, write_inventory
from great_docs._sphinx_inventory import Inventory, InventoryEntry, decode


def test_write_inventory_writes_an_objects_inv(tmp_path):
    """The inventory on disk is the format every consumer reads."""
    inv = Inventory(
        project="demo",
        version="1.2",
        entries=(
            InventoryEntry(
                name="demo.Thing",
                domain="py",
                role="class",
                priority=1,
                uri="reference/Thing.html#demo.Thing",
                dispname="demo.Thing",
            ),
        ),
    )
    out = tmp_path / "objects.inv"

    write_inventory(inv, str(out))

    written = decode(out.read_bytes())
    assert written.project == "demo"
    assert written.version == "1.2"
    assert written.entries[0].name == "demo.Thing"
    assert written.entries[0].uri == "reference/Thing.html#demo.Thing"
    assert written.entries[0].priority == 1


def test_reference_uri_joins_the_directory_and_the_stem():
    assert reference_uri("reference", "MyClass") == "reference/MyClass.html"


def test_reference_uri_appends_an_anchor():
    assert reference_uri("reference", "MyClass", "flush") == "reference/MyClass.html#flush"


def test_reference_uri_honours_a_configured_directory():
    assert reference_uri("api", "MyClass") == "api/MyClass.html"
