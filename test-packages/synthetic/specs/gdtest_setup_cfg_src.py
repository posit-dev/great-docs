"""
gdtest_setup_cfg_src — setup.cfg only + src/ layout.

Dimensions: A7, A2, B1, C1, D1, E6, F6, G1, H7
Focus: No pyproject.toml — metadata from setup.cfg while module lives
       in src/ directory. Tests both fallback paths together.
"""

SPEC = {
    "name": "gdtest_setup_cfg_src",
    "description": "setup.cfg metadata with src/ layout",
    "dimensions": ["A7", "A2", "B1", "C1", "D1", "E6", "F6", "G1", "H7"],
    "setup_cfg": """\
[metadata]
name = gdtest-setup-cfg-src
version = 0.1.0
description = Test setup.cfg with src/ layout

[options]
package_dir =
    = src
packages = find:

[options.packages.find]
where = src
""",
    "files": {
        "src/gdtest_setup_cfg_src/__init__.py": '''\
            """Package using setup.cfg with src/ layout."""

            __version__ = "0.1.0"
            __all__ = ["parse", "format_text"]


            def parse(text: str) -> list:
                """
                Parse text into tokens.

                Parameters
                ----------
                text
                    Input text.

                Returns
                -------
                list
                    List of tokens.
                """
                return text.split()


            def format_text(tokens: list) -> str:
                """
                Format tokens back into text.

                Parameters
                ----------
                tokens
                    List of tokens.

                Returns
                -------
                str
                    Formatted text.
                """
                return " ".join(tokens)
        ''',
        "README.md": """\
            # gdtest-setup-cfg-src

            Tests setup.cfg metadata detection with src/ layout.
        """,
    },
    "expected": {
        "detected_name": "gdtest-setup-cfg-src",
        "detected_module": "gdtest_setup_cfg_src",
        "detected_parser": "numpy",
        "export_names": ["parse", "format_text"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
