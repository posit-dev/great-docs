"""
gdtest_source_disabled — Tests source.enabled: false config.

Dimensions: K5
Focus: source.enabled config option set to false to disable source links.
"""

SPEC = {
    "name": "gdtest_source_disabled",
    "description": "Tests source.enabled: false config",
    "dimensions": ["K5"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-source-disabled",
            "version": "0.1.0",
            "description": "Test source.enabled false config",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "source": {
            "enabled": False,
        },
    },
    "files": {
        "gdtest_source_disabled/__init__.py": '''\
            """Package testing source.enabled false config."""

            __version__ = "0.1.0"
            __all__ = ["encrypt", "decrypt"]


            def encrypt(text: str, key: str) -> str:
                """
                Encrypt text with a key.

                Parameters
                ----------
                text
                    The plaintext to encrypt.
                key
                    The encryption key.

                Returns
                -------
                str
                    The encrypted text.
                """
                return ""


            def decrypt(text: str, key: str) -> str:
                """
                Decrypt text with a key.

                Parameters
                ----------
                text
                    The ciphertext to decrypt.
                key
                    The decryption key.

                Returns
                -------
                str
                    The decrypted text.
                """
                return ""
        ''',
        "README.md": """\
            # gdtest-v2-source-disabled

            Tests source.enabled: false config.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-source-disabled",
        "detected_module": "gdtest_source_disabled",
        "detected_parser": "numpy",
        "export_names": ["decrypt", "encrypt"],
        "num_exports": 2,
    },
}
