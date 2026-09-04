from great_docs._apiref.inventory import write_inventory
from great_docs._sphinx_inventory import decode


def test_write_inventory_writes_an_objects_inv(tmp_path):
    """The inventory on disk is the format every consumer reads."""
    inv = {
        "project": "demo",
        "version": "1.2",
        "count": 1,
        "items": [
            {
                "name": "demo.Thing",
                "domain": "py",
                "role": "class",
                "priority": "1",
                "uri": "reference/Thing.html#demo.Thing",
                "dispname": "-",
            }
        ],
    }
    out = tmp_path / "objects.inv"

    write_inventory(inv, str(out))

    written = decode(out.read_bytes())
    assert written.project == "demo"
    assert written.version == "1.2"
    assert written.entries[0].name == "demo.Thing"
    assert written.entries[0].uri == "reference/Thing.html#demo.Thing"
    assert written.entries[0].priority == 1
