"""
gdtest_ref_explicit — Explicit reference config listing specific objects.

Dimensions: P1
Focus: Reference config with two named sections, each listing specific functions.
"""

SPEC = {
    "name": "gdtest_ref_explicit",
    "description": "Explicit reference config listing specific objects in named sections.",
    "dimensions": ["P1"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-ref-explicit",
            "version": "0.1.0",
            "description": "Test explicit reference config.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "reference": [
            {
                "title": "Builders",
                "desc": "Build functions",
                "contents": [
                    {"name": "build"},
                    {"name": "compile_source"},
                ],
            },
            {
                "title": "Runners",
                "desc": "Execution",
                "contents": [
                    {"name": "run"},
                    {"name": "execute"},
                ],
            },
        ],
    },
    "files": {
        "gdtest_ref_explicit/__init__.py": '"""Test package for explicit reference config."""\n\nfrom .builders import build, compile_source\nfrom .runners import execute, run\n\n__all__ = ["build", "compile_source", "execute", "run"]\n',
        "gdtest_ref_explicit/builders.py": '''
            """Builder functions for compiling and building targets."""


            def build(target: str) -> None:
                """Build the specified target.

                Parameters
                ----------
                target : str
                    The target to build.

                Returns
                -------
                None

                Examples
                --------
                >>> build("main")
                """
                pass


            def compile_source(source: str) -> bytes:
                """Compile source code into bytes.

                Parameters
                ----------
                source : str
                    The source code to compile.

                Returns
                -------
                bytes
                    The compiled bytecode.

                Examples
                --------
                >>> compile_source("print('hello')")
                b'...'
                """
                return source.encode()
        ''',
        "gdtest_ref_explicit/runners.py": '''
            """Runner functions for executing commands and scripts."""


            def run(cmd: str) -> int:
                """Run a shell command and return the exit code.

                Parameters
                ----------
                cmd : str
                    The command to run.

                Returns
                -------
                int
                    The exit code of the command.

                Examples
                --------
                >>> run("echo hello")
                0
                """
                return 0


            def execute(script: str) -> str:
                """Execute a script and return its output.

                Parameters
                ----------
                script : str
                    The script to execute.

                Returns
                -------
                str
                    The output of the script execution.

                Examples
                --------
                >>> execute("print('hi')")
                'hi'
                """
                return "hi"
        ''',
        "README.md": ("# gdtest-ref-explicit\n\nTest explicit reference config.\n"),
    },
    "expected": {
        "detected_name": "gdtest-ref-explicit",
        "detected_module": "gdtest_ref_explicit",
        "detected_parser": "numpy",
        "export_names": ["build", "compile_source", "execute", "run"],
        "num_exports": 4,
    },
}
