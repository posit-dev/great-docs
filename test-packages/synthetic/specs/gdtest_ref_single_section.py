"""
gdtest_ref_single_section — Reference with one named section containing all exports.

Dimensions: P5
Focus: Reference config with a single section grouping all functions together.
"""

SPEC = {
    "name": "gdtest_ref_single_section",
    "description": "Reference with one named section containing all exports.",
    "dimensions": ["P5"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-ref-single-section",
            "version": "0.1.0",
            "description": "Test reference with a single named section.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "reference": [
            {
                "title": "Complete API",
                "desc": "All functions",
                "contents": [
                    {"name": "alpha"},
                    {"name": "beta"},
                    {"name": "gamma"},
                    {"name": "delta"},
                ],
            },
        ],
    },
    "files": {
        "gdtest_ref_single_section/__init__.py": '"""Test package for reference with a single named section."""\n',
        "gdtest_ref_single_section/api.py": '''
            """Complete API with four functions."""


            def alpha(x: int) -> int:
                """Apply the alpha transformation.

                Parameters
                ----------
                x : int
                    The input value.

                Returns
                -------
                int
                    The transformed value.

                Examples
                --------
                >>> alpha(5)
                10
                """
                return x * 2


            def beta(x: int) -> int:
                """Apply the beta transformation.

                Parameters
                ----------
                x : int
                    The input value.

                Returns
                -------
                int
                    The transformed value.

                Examples
                --------
                >>> beta(5)
                25
                """
                return x ** 2


            def gamma(x: int, y: int) -> int:
                """Combine two values using the gamma operation.

                Parameters
                ----------
                x : int
                    The first input value.
                y : int
                    The second input value.

                Returns
                -------
                int
                    The combined result.

                Examples
                --------
                >>> gamma(3, 4)
                7
                """
                return x + y


            def delta(x: int) -> float:
                """Compute the delta of a value.

                Parameters
                ----------
                x : int
                    The input value.

                Returns
                -------
                float
                    The delta result.

                Examples
                --------
                >>> delta(10)
                5.0
                """
                return x / 2.0
        ''',
        "README.md": (
            "# gdtest-v2-ref-single-section\n\nTest reference with a single named section.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-v2-ref-single-section",
        "detected_module": "gdtest_ref_single_section",
        "detected_parser": "numpy",
        "export_names": ["alpha", "beta", "delta", "gamma"],
        "num_exports": 4,
    },
}
