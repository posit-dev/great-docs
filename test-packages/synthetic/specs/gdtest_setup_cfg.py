"""
gdtest_setup_cfg — Package using setup.cfg only (no pyproject.toml).

Dimensions: A7, B1, C1, D1, E6, F6, G1, H7
Focus: No pyproject.toml — only setup.cfg with [metadata] name.
       Tests _detect_package_name setup.cfg code path.
"""

SPEC = {
    "name": "gdtest_setup_cfg",
    "description": "setup.cfg only — no pyproject.toml",
    "dimensions": ["A7", "B1", "C1", "D1", "E6", "F6", "G1", "H7"],
    # No pyproject_toml — this package uses setup.cfg
    "setup_cfg": """\
[metadata]
name = gdtest-setup-cfg
version = 0.1.0
description = A synthetic test package using setup.cfg only

[options]
packages = find:
python_requires = >=3.9
""",
    "files": {
        "gdtest_setup_cfg/__init__.py": '''\
            """A test package using setup.cfg only."""

            __version__ = "0.1.0"
            __all__ = ["ping", "pong"]


            def ping() -> str:
                """
                Send a ping.

                Returns
                -------
                str
                    The ping response.
                """
                return "pong"


            def pong() -> str:
                """
                Send a pong.

                Returns
                -------
                str
                    The pong response.
                """
                return "ping"
        ''',
        "README.md": """\
            # gdtest-setup-cfg

            A synthetic test package using ``setup.cfg`` only.
        """,
    },
    "expected": {
        "detected_name": "gdtest-setup-cfg",
        "detected_module": "gdtest_setup_cfg",
        "detected_parser": "numpy",
        "export_names": ["ping", "pong"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp"],
    },
}
