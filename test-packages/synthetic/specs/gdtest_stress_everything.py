"""
gdtest_stress_everything — The ULTIMATE stress test combining EVERYTHING.

Dimensions: K1, K4, K12, K13, K14, L1, L3, L10, L15, M2, M3, N1, N2, P1, Q1
Focus: All config options, rich NumPy docstrings with directives and Sphinx roles,
       a big class with 6 methods, user guide with sections, custom sections,
       explicit reference groups, badges in README, and cosmo theme.
"""

SPEC = {
    "name": "gdtest_stress_everything",
    "description": "The ULTIMATE stress test combining EVERYTHING.",
    "dimensions": [
        "K1",
        "K4",
        "K12",
        "K13",
        "K14",
        "L1",
        "L3",
        "L10",
        "L15",
        "M2",
        "M3",
        "N1",
        "N2",
        "P1",
        "Q1",
    ],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-stress-everything",
            "version": "0.1.0",
            "description": "The ultimate stress test combining everything.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "display_name": "Everything Stress Test",
        "parser": "numpy",
        "github_style": "icon",
        "source": {"enabled": True, "placement": "title"},
        "dark_mode_toggle": True,
        "authors": [
            {
                "name": "Omni Author",
                "email": "omni@test.com",
                "role": "Architect",
                "github": "omni",
            },
        ],
        "funding": {
            "name": "Universal Fund",
            "roles": ["Sponsor"],
            "homepage": "https://example.com",
        },
        "site": {"theme": "cosmo", "toc-depth": 3, "toc-title": "Navigation"},
        "sections": [
            {"title": "Examples", "dir": "examples"},
            {"title": "Tutorials", "dir": "tutorials"},
        ],
        "reference": [
            {
                "title": "Core API",
                "desc": "Main functions",
                "contents": [
                    {"name": "create_resource"},
                    {"name": "ResourceManager", "members": True},
                ],
            },
            {
                "title": "Utilities",
                "desc": "Helpers",
                "contents": [
                    {"name": "format_output"},
                    {"name": "validate_input"},
                ],
            },
        ],
    },
    "files": {
        "gdtest_stress_everything/__init__.py": '''\
            """Package for the ultimate stress test combining everything."""

            __all__ = [
                "create_resource",
                "ResourceManager",
                "format_output",
                "validate_input",
            ]
        ''',
        "gdtest_stress_everything/core.py": '''
            """Core API: create_resource and ResourceManager."""


            def create_resource(name: str, kind: str = "default") -> dict:
                """Create a new resource with the given name and kind.

                Initializes a resource and registers it in the internal
                registry. Uses :py:func:`validate_input` to check the
                name and :py:class:`ResourceManager` for lifecycle management.

                .. versionadded:: 2.0

                .. note:: This replaces the deprecated ``make_resource`` function.

                Parameters
                ----------
                name : str
                    The name of the resource. Must be non-empty and contain
                    only alphanumeric characters and hyphens.
                kind : str, optional
                    The type of resource to create. One of ``"default"``,
                    ``"premium"``, or ``"ephemeral"``. Defaults to ``"default"``.

                Returns
                -------
                dict
                    A dictionary with the following keys:

                    - ``"name"`` — the resource name (str).
                    - ``"kind"`` — the resource kind (str).
                    - ``"id"`` — the assigned resource ID (int).

                Raises
                ------
                ValueError
                    If ``name`` is empty or ``kind`` is not recognized.

                Notes
                -----
                Resources created with ``kind="ephemeral"`` are automatically
                garbage-collected after 24 hours. The cleanup runs on a
                background timer managed by :py:class:`ResourceManager`.

                The resource ID is assigned sequentially using an atomic
                counter, so IDs are guaranteed to be unique within a
                single process.

                See Also
                --------
                ResourceManager : Manages resource lifecycle.
                validate_input : Validates resource names.

                Examples
                --------
                Create a default resource:

                >>> res = create_resource("my-item")
                >>> res["kind"]
                'default'

                Create a premium resource:

                >>> res = create_resource("premium-item", kind="premium")
                >>> res["name"]
                'premium-item'
                """
                if not name:
                    raise ValueError("name must not be empty")
                if kind not in ("default", "premium", "ephemeral"):
                    raise ValueError(f"Unknown kind: {kind}")
                return {"name": name, "kind": kind, "id": 1}


            class ResourceManager:
                """Manages the lifecycle of resources.

                Provides methods for creating, reading, updating, deleting,
                listing, and reporting on resources.

                Parameters
                ----------
                namespace : str
                    The namespace for this manager instance.

                Examples
                --------
                >>> mgr = ResourceManager("production")
                >>> mgr.list_resources()
                []
                """

                def __init__(self, namespace: str):
                    """Initialize the ResourceManager.

                    Parameters
                    ----------
                    namespace : str
                        The namespace for this manager.
                    """
                    self.namespace = namespace
                    self._resources: dict = {}
                    self._counter = 0

                def add(self, name: str) -> dict:
                    """Add a new resource.

                    Parameters
                    ----------
                    name : str
                        The name of the resource to add.

                    Returns
                    -------
                    dict
                        The added resource.

                    Examples
                    --------
                    >>> mgr = ResourceManager("test")
                    >>> mgr.add("item-1")
                    {'name': 'item-1', 'id': 1}
                    """
                    self._counter += 1
                    resource = {"name": name, "id": self._counter}
                    self._resources[self._counter] = resource
                    return resource

                def get(self, id: int) -> dict:
                    """Get a resource by ID.

                    Parameters
                    ----------
                    id : int
                        The resource identifier.

                    Returns
                    -------
                    dict
                        The resource data.
                    """
                    return self._resources.get(id, {})

                def remove(self, id: int) -> bool:
                    """Remove a resource by ID.

                    Parameters
                    ----------
                    id : int
                        The resource identifier to remove.

                    Returns
                    -------
                    bool
                        True if the resource was removed.
                    """
                    return self._resources.pop(id, None) is not None

                def list_resources(self) -> list:
                    """List all managed resources.

                    Returns
                    -------
                    list
                        A list of all resource dictionaries.

                    Examples
                    --------
                    >>> mgr = ResourceManager("test")
                    >>> mgr.list_resources()
                    []
                    """
                    return list(self._resources.values())

                def count(self) -> int:
                    """Return the number of managed resources.

                    Returns
                    -------
                    int
                        The total count of resources.
                    """
                    return len(self._resources)

                def report(self) -> dict:
                    """Generate a status report.

                    Returns
                    -------
                    dict
                        A report with namespace and resource count.

                    Examples
                    --------
                    >>> mgr = ResourceManager("prod")
                    >>> mgr.report()
                    {'namespace': 'prod', 'count': 0}
                    """
                    return {"namespace": self.namespace, "count": len(self._resources)}
        ''',
        "gdtest_stress_everything/utils.py": '''
            """Utility functions: format_output and validate_input."""


            def format_output(result: dict) -> str:
                """Format a result dictionary as a readable string.

                Parameters
                ----------
                result : dict
                    The result dictionary to format.

                Returns
                -------
                str
                    A formatted string representation.

                See Also
                --------
                validate_input : Validates input before processing.

                Examples
                --------
                >>> format_output({"name": "test", "id": 1})
                'name=test, id=1'
                """
                return ", ".join(f"{k}={v}" for k, v in result.items())


            def validate_input(name: str) -> bool:
                """Validate a resource name.

                Parameters
                ----------
                name : str
                    The resource name to validate.

                Returns
                -------
                bool
                    True if the name is valid.

                Raises
                ------
                ValueError
                    If the name is empty or contains invalid characters.

                Examples
                --------
                >>> validate_input("my-resource")
                True

                >>> validate_input("")
                Traceback (most recent call last):
                    ...
                ValueError: name must not be empty
                """
                if not name:
                    raise ValueError("name must not be empty")
                return True
        ''',
        "user_guide/01-intro.qmd": (
            "---\n"
            "title: Introduction\n"
            "guide-section: Basics\n"
            "---\n"
            "\n"
            "# Introduction\n"
            "\n"
            "Welcome to the Everything Stress Test package.\n"
        ),
        "user_guide/02-install.qmd": (
            "---\n"
            "title: Installation\n"
            "guide-section: Basics\n"
            "---\n"
            "\n"
            "# Installation\n"
            "\n"
            "Install the package using pip.\n"
        ),
        "user_guide/03-advanced.qmd": (
            "---\n"
            "title: Advanced Usage\n"
            "guide-section: Advanced\n"
            "---\n"
            "\n"
            "# Advanced Usage\n"
            "\n"
            "Advanced topics for power users.\n"
        ),
        "examples/basic.qmd": (
            "---\n"
            "title: Basic Example\n"
            "---\n"
            "\n"
            "# Basic Example\n"
            "\n"
            "A basic example showing core functionality.\n"
        ),
        "tutorials/getting-started.qmd": (
            "---\n"
            "title: Getting Started\n"
            "---\n"
            "\n"
            "# Getting Started\n"
            "\n"
            "A step-by-step tutorial for new users.\n"
        ),
        "README.md": (
            "# gdtest-v2-stress-everything\n"
            "\n"
            "![Version](https://img.shields.io/badge/version-0.1.0-blue)\n"
            "![Python](https://img.shields.io/badge/python-3.9+-green)\n"
            "![License](https://img.shields.io/badge/license-MIT-orange)\n"
            "\n"
            "The ultimate stress test combining everything.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-v2-stress-everything",
        "detected_module": "gdtest_stress_everything",
        "detected_parser": "numpy",
        "export_names": [
            "ResourceManager",
            "create_resource",
            "format_output",
            "validate_input",
        ],
        "num_exports": 4,
    },
}
