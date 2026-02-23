"""Tests config combo: display_name + authors + funding + github_style: icon + source.placement: title."""

SPEC = {
    "name": "gdtest_config_combo_a",
    "description": (
        "Config combo: display_name, authors, funding, github_style=icon, "
        "source.placement=title. Tests cosmetic and metadata options together."
    ),
    "dimensions": ["K1", "K4", "K12", "K13", "K14"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-config-combo-a",
            "version": "0.1.0",
            "description": "Test package for config combo A.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "display_name": "Combo A Toolkit",
        "authors": [
            {"name": "Alice Smith", "url": "https://example.com/alice"},
            {"name": "Bob Jones", "url": "https://example.com/bob"},
        ],
        "funding": {
            "text": "Supported by Example Foundation",
            "url": "https://example.com/funding",
        },
        "github_style": "icon",
        "source": {
            "enabled": True,
            "placement": "title",
        },
    },
    "files": {
        "gdtest_config_combo_a/__init__.py": '"""Combo A Toolkit."""\n',
        "gdtest_config_combo_a/core.py": '''
            """CRUD operations for items."""


            def create(name: str) -> dict:
                """Create a new item with the given name.

                Parameters
                ----------
                name : str
                    The name for the new item.

                Returns
                -------
                dict
                    The newly created item as a dictionary with 'name' and 'id' keys.

                Examples
                --------
                >>> create("widget")
                {'name': 'widget', 'id': 1}
                """
                return {"name": name, "id": 1}


            def update(item: dict) -> dict:
                """Update an existing item.

                Parameters
                ----------
                item : dict
                    The item to update. Must contain an 'id' key.

                Returns
                -------
                dict
                    The updated item dictionary.

                Examples
                --------
                >>> update({"id": 1, "name": "updated_widget"})
                {'id': 1, 'name': 'updated_widget'}
                """
                return item


            def delete(item_id: str) -> bool:
                """Delete an item by its ID.

                Parameters
                ----------
                item_id : str
                    The unique identifier of the item to delete.

                Returns
                -------
                bool
                    True if the item was successfully deleted, False otherwise.

                Examples
                --------
                >>> delete("abc123")
                True
                """
                return True
        ''',
    },
    "expected": {
        "build_succeeds": True,
        "files_exist": [
            "great-docs/reference/index.html",
            "great-docs/reference/create.html",
            "great-docs/reference/update.html",
            "great-docs/reference/delete.html",
        ],
        "files_contain": {
            "great-docs/index.html": ["Combo A Toolkit"],
        },
    },
}
