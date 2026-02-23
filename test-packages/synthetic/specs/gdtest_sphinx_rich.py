"""
gdtest_sphinx_rich — Rich Sphinx-format docstrings with field lists.

Dimensions: L17
Focus: Two functions with comprehensive Sphinx-format docstrings using
       :param:, :type:, :returns:, :rtype:, :raises:, plus prose Notes
       and Examples blocks.
"""

SPEC = {
    "name": "gdtest_sphinx_rich",
    "description": "Rich Sphinx-format docstrings with full field lists",
    "dimensions": ["L17"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-sphinx-rich",
            "version": "0.1.0",
            "description": "Test rich Sphinx docstring section rendering",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "parser": "sphinx",
    },
    "files": {
        "gdtest_sphinx_rich/__init__.py": '''\
            """Package with rich Sphinx-format docstrings."""

            __version__ = "0.1.0"
            __all__ = ["execute", "schedule"]


            def execute(command: str, timeout: int = 30) -> str:
                """Execute a shell command and return its output.

                Runs the given command string in a subprocess and captures
                the standard output. The command is subject to a timeout
                to prevent hangs.

                :param command: The shell command to execute.
                :type command: str
                :param timeout: Maximum seconds to wait for the command
                    to complete. Defaults to 30.
                :type timeout: int
                :returns: The captured standard output from the command.
                :rtype: str
                :raises OSError: If the command cannot be found or executed.
                :raises TimeoutError: If the command exceeds the timeout.
                :raises RuntimeError: If the command exits with a non-zero
                    return code.

                .. note::

                    The command is executed in a new subprocess. Environment
                    variables from the parent process are inherited.

                .. warning::

                    Never pass untrusted input directly as the command string.
                    This function does not sanitize inputs.

                **Examples**::

                    >>> execute("echo hello")
                    'hello'

                    >>> execute("sleep 5", timeout=2)
                    TimeoutError: Command timed out after 2 seconds
                """
                import subprocess

                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                if result.returncode != 0:
                    raise RuntimeError(
                        f"Command failed with code {result.returncode}: "
                        f"{result.stderr}"
                    )
                return result.stdout.strip()


            def schedule(task: str, delay: float = 0.0) -> bool:
                """Schedule a task for later execution.

                Registers the given task identifier to be executed after
                the specified delay. Returns whether the scheduling was
                successful.

                :param task: The task identifier string to schedule.
                :type task: str
                :param delay: Number of seconds to wait before executing.
                    Must be non-negative. Defaults to ``0.0``.
                :type delay: float
                :returns: True if the task was successfully scheduled,
                    False if the task is already scheduled.
                :rtype: bool
                :raises ValueError: If ``delay`` is negative.
                :raises TypeError: If ``task`` is not a string.

                .. note::

                    Tasks are identified by their string name. Scheduling
                    the same task twice will return False the second time.

                **Examples**::

                    >>> schedule("cleanup")
                    True

                    >>> schedule("backup", delay=60.0)
                    True

                    >>> schedule("cleanup")
                    False
                """
                if not isinstance(task, str):
                    raise TypeError("task must be a string")
                if delay < 0:
                    raise ValueError("delay must be non-negative")
                return True
        ''',
        "README.md": """\
            # gdtest-v2-sphinx-rich

            A synthetic test package with rich Sphinx-format docstrings.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-sphinx-rich",
        "detected_module": "gdtest_sphinx_rich",
        "detected_parser": "sphinx",
        "export_names": ["execute", "schedule"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
    },
}
