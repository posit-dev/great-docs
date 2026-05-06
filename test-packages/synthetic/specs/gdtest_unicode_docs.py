"""
gdtest_unicode_docs — Docstrings with unicode characters.

Dimensions: A1, B1, C1, D1, E6, F6, G1, H7
Focus: Docstrings containing accented chars, emoji, CJK characters,
       and mathematical symbols. Tests unicode safety.
"""

SPEC = {
    "name": "gdtest_unicode_docs",
    "description": "Docstrings with unicode characters",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-unicode-docs",
            "version": "0.1.0",
            "description": "Test unicode in docstrings",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_unicode_docs/__init__.py": '''\
            """Package with unicode-heavy docstrings."""

            __version__ = "0.1.0"
            __all__ = ["greet_international", "analyze_text", "compute_stats"]


            def greet_international(name: str, language: str = "en") -> str:
                """
                Greet someone in their language.

                Supported greetings include:

                - English: "Hello"
                - French: "Bonjour" (by Ren\\u00e9 Descartes)
                - Japanese: "\\u3053\\u3093\\u306b\\u3061\\u306f"
                - Chinese: "\\u4f60\\u597d"
                - Arabic: "\\u0645\\u0631\\u062d\\u0628\\u0627"
                - Emoji: "\\U0001f44b"

                Parameters
                ----------
                name
                    The person's name.
                language
                    Language code (en, fr, ja, zh, ar).

                Returns
                -------
                str
                    Greeting string.
                """
                greetings = {
                    "en": "Hello",
                    "fr": "Bonjour",
                    "ja": "\\u3053\\u3093\\u306b\\u3061\\u306f",
                    "zh": "\\u4f60\\u597d",
                    "ar": "\\u0645\\u0631\\u062d\\u0628\\u0627",
                }
                return f"{greetings.get(language, 'Hello')}, {name}! \\U0001f44b"


            def analyze_text(text: str) -> dict:
                """
                Analyze text with support for unicode characters.

                Handles various scripts: Latin (caf\\u00e9), Greek (\\u03b1\\u03b2\\u03b3),
                Cyrillic (\\u041f\\u0440\\u0438\\u0432\\u0435\\u0442), CJK (\\u6570\\u636e\\u5206\\u6790).

                Statistical symbols: \\u03bc (mean), \\u03c3 (std dev), \\u03a3 (sum).

                Parameters
                ----------
                text
                    Input text (any unicode).

                Returns
                -------
                dict
                    Analysis with keys: length, unique_chars, scripts.
                """
                return {
                    "length": len(text),
                    "unique_chars": len(set(text)),
                }


            def compute_stats(values: list) -> dict:
                """
                Compute basic statistics.

                Returns \\u03bc (mean) and \\u03c3 (standard deviation).

                Mathematical notation: \\u03bc = \\u03a3x\\u1d62/n

                Set operations: A \\u222a B, A \\u2229 B, A \\u2286 B

                Integral: \\u222b f(x)dx, Product: \\u220f x\\u1d62

                Parameters
                ----------
                values
                    Numeric values.

                Returns
                -------
                dict
                    Statistics dictionary with \\u03bc and \\u03c3.
                """
                n = len(values)
                if n == 0:
                    return {"\\u03bc": 0, "\\u03c3": 0}
                mean = sum(values) / n
                variance = sum((x - mean) ** 2 for x in values) / n
                return {"\\u03bc": mean, "\\u03c3": variance ** 0.5}
        ''',
        "README.md": """\
            # gdtest-unicode-docs

            Tests unicode characters in docstrings: caf\u00e9, \U0001f4ca, \u6570\u636e, \u222b\u03a3\u220f.
        """,
    },
    "expected": {
        "detected_name": "gdtest-unicode-docs",
        "detected_module": "gdtest_unicode_docs",
        "detected_parser": "numpy",
        "export_names": ["greet_international", "analyze_text", "compute_stats"],
        "num_exports": 3,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
