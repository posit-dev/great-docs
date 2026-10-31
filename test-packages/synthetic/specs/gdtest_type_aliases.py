"""
gdtest_type_aliases — PEP 695 `type` statement aliases.

Dimensions: A1, B1, C25, D1, E6, F6, G1, H7
Focus: every PEP 695 type alias form, a class-nested alias, and the pre-PEP 695
       `X: TypeAlias = ...` spelling alongside them.

Requires Python 3.12: `type X = ...` is a SyntaxError before it, so griffe
cannot parse this package on 3.11. `min_python` keeps it out of the parametrized
runs there.

PEP 696 type parameter defaults (`type X[T = int]`) are deliberately absent —
that is 3.13 syntax, and gating this package at 3.13 would cost the 3.12 job all
the coverage above. The unit tests carry those cases with their own marker.
"""

SPEC = {
    "name": "gdtest_type_aliases",
    "description": "PEP 695 type aliases",
    "dimensions": ["A1", "B1", "C25", "D1", "E6", "F6", "G1", "H7"],
    "min_python": (3, 12),
    "pyproject_toml": {
        "project": {
            "name": "gdtest-type-aliases",
            "version": "0.1.0",
            "description": "A synthetic test package built from PEP 695 type aliases",
            "requires-python": ">=3.12",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_type_aliases/__init__.py": '''\
            """A test package whose public API is mostly PEP 695 type aliases."""

            __version__ = "0.1.0"
            __all__ = [
                "Clause",
                "ContractId",
                "Jurisdiction",
                "Key",
                "Ledger",
                "Named",
                "Pair",
                "Row",
                "Signature",
                "Validator",
                "sign",
                "summarize",
            ]

            from collections.abc import Callable
            from typing import Literal, TypeAlias

            type ContractId = str
            """An opaque identifier for a single contract"""

            type Pair[T] = tuple[T, T]
            """Two values of the same type, e.g. a counterparty pair"""

            type Named[T: str] = dict[T, ContractId]
            """Contracts keyed by name, where the key type is bounded by `str`"""

            type Key[K: (str, bytes)] = dict[K, ContractId]
            """A lookup keyed by either `str` or `bytes`, but not a mix of the two

            griffe stores constraints separately from bounds, leaving `bound` as
            None, so this is the form that catches reading only `bound`.
            """

            type Row[T, *Ts] = tuple[T, *Ts]
            """A heterogeneous ledger row: a leading column plus any number of others"""

            type Validator[**P] = Callable[P, bool]
            """Any predicate, however it is called"""

            type Clause = str | list[Clause]
            """A contract clause, possibly nested

            Refers to itself. PEP 695 evaluates alias values lazily, so this
            needs no quoting and nothing resolves it while rendering.
            """

            type Jurisdiction = Literal[
                "us-ca", "us-ny", "us-tx", "gb-eng", "gb-sct", "de-by", "fr-idf", "jp-13"
            ]
            """A supported governing jurisdiction, as an ISO-ish region code"""

            Signature: TypeAlias = Literal["ed25519", "rsa"]
            """Which signing scheme produced a signature

            The pre-PEP 695 spelling. It stays a plain attribute rather than a
            TypeAlias object, but should carry the same label as its neighbours.
            """


            class Ledger:
                """
                An append-only record of contract state changes.

                Declares a type alias in its own body, which belongs under a
                "Type Aliases" heading of its own rather than being dropped.
                """

                type Entry = tuple[ContractId, Jurisdiction]
                """A single ledger entry: which contract, and where it applies"""

                max_entries: int = 1000
                """How many entries the ledger retains before rotating"""

                def __init__(self) -> None:
                    self._entries: list[Entry] = []

                def append(self, contract_id: ContractId, where: Jurisdiction) -> None:
                    """
                    Record that `contract_id` applies in `where`.

                    Parameters
                    ----------
                    contract_id
                        The contract being recorded.
                    where
                        The jurisdiction it applies in.
                    """
                    self._entries.append((contract_id, where))

                def entries(self) -> list[Entry]:
                    """
                    Every recorded entry, oldest first.

                    Returns
                    -------
                    list
                        The entries in insertion order.
                    """
                    return list(self._entries)


            def sign(contract_id: ContractId, scheme: Signature) -> bool:
                """
                Sign a contract with the named scheme.

                Parameters
                ----------
                contract_id
                    The contract to sign.
                scheme
                    Which signing scheme to use.

                Returns
                -------
                bool
                    True when the contract was signed.
                """
                return bool(contract_id and scheme)


            def summarize(rows: Row[ContractId], where: Jurisdiction = "us-ca") -> Named[str]:
                """
                Group contracts by name for one jurisdiction.

                Parameters
                ----------
                rows
                    The contracts to summarize.
                where
                    Which jurisdiction's rules to apply.

                Returns
                -------
                dict
                    Each contract name mapped to its identifier.
                """
                return {str(row): str(row) for row in rows}
        ''',
        "README.md": """\
            # gdtest-type-aliases

            A synthetic test package whose public API is mostly PEP 695 type aliases.
        """,
    },
    "expected": {
        "detected_name": "gdtest-type-aliases",
        "detected_module": "gdtest_type_aliases",
        "detected_parser": "numpy",
        "export_names": [
            "Clause",
            "ContractId",
            "Jurisdiction",
            "Key",
            "Ledger",
            "Named",
            "Pair",
            "Row",
            "Signature",
            "Validator",
            "sign",
            "summarize",
        ],
        "num_exports": 12,
        # The legacy `Signature: TypeAlias = ...` lands in Type Aliases with the PEP 695 aliases.
        "section_titles": ["Classes", "Functions", "Type Aliases"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
