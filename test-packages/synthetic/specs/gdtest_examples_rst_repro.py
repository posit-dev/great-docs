"""
gdtest_examples_rst_repro — RST markup inside a numpy Examples section.

Regression fixture: prose interleaved between doctest blocks of a numpy
``Examples`` section must receive the same RST->Markdown conversion as the
main description body. The SAME inline RST markup (a ``:func:`` role and
inline ``:math:``) appears both (a) in the description body and (b) in the
prose between the ``>>>`` blocks of the Examples section, so a single
rendered page shows whether the two paths agree.

Guards against the interleaved-Examples text (the ``ExampleText`` branch in
``_render/doc.py``) being routed through doctest fencing only and skipping
``convert_docstring_text`` — which leaves roles/math rendered as raw text.
"""

SPEC = {
    "name": "gdtest_examples_rst_repro",
    "description": "RST markup inside a numpy Examples section (finding #1 repro)",
    "dimensions": ["L18"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-examples-rst-repro",
            "version": "0.1.0",
            "description": "Repro for RST markup in Examples prose",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "parser": "numpy",
    },
    "files": {
        "gdtest_examples_rst_repro/__init__.py": '''\
            """Package reproducing RST-in-Examples rendering."""

            __version__ = "0.1.0"
            __all__ = ["compute"]


            def compute(n: int) -> int:
                """
                Compute something, see :func:`compute` and :math:`n^2`.

                This BODY paragraph contains a role :func:`compute` and inline
                math :math:`x_i` and an RST literal ``value``. These should be
                converted (role -> link/code, math -> MathJax, literal -> code).

                Examples
                --------
                >>> compute(2)
                4

                The PROSE below references :func:`compute` and inline math
                :math:`n^2` and an RST literal ``value`` — the exact same
                markup as the body above:

                >>> compute(3)
                9
                """
                return n * n
        ''',
        "README.md": """\
            # gdtest-examples-rst-repro

            Repro package for RST markup inside a numpy Examples section.
        """,
    },
    "expected": {
        "detected_name": "gdtest-examples-rst-repro",
        "detected_module": "gdtest_examples_rst_repro",
        "detected_parser": "numpy",
        "export_names": ["compute"],
        "num_exports": 1,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
