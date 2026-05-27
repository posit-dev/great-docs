"""
gdtest_termshow — Demonstrate the termshow feature for CLI/TUI documentation.

Dimensions: A1, B1, C4, D2, E4, F1, G1, H3
Focus: The termshow shortcode rendering pre-recorded terminal sessions as
       interactive SVG-based players with chapter navigation, annotations,
       speed control, and keyboard shortcuts. Includes demos of CLI commands,
       TUI interfaces, and scripted recordings with edit overlays.
"""

SPEC = {
    "name": "gdtest_termshow",
    "description": "Terminal player demo with CLI/TUI recordings",
    "dimensions": ["A1", "B1", "C4", "D2", "E4", "F1", "G1", "H3"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-termshow",
            "version": "1.0.0",
            "description": "A demo package showing the termshow terminal recording feature",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        # ── Python module (minimal CLI tool for demo) ────────────────────
        "gdtest_termshow/__init__.py": (
            '"""A sample CLI/TUI tool for demonstrating termshow recordings."""\n'
            "\n"
            '__version__ = "1.0.0"\n'
            '__all__ = ["greet", "init_project", "run_task"]\n'
            "\n"
            "\n"
            "def greet(name: str) -> str:\n"
            '    """Greet a user by name.\n'
            "\n"
            "    Parameters\n"
            "    ----------\n"
            "    name\n"
            "        The name to greet.\n"
            "\n"
            "    Returns\n"
            "    -------\n"
            "    str\n"
            "        A greeting string.\n"
            '    """\n'
            '    return f"Hello, {name}!"\n'
            "\n"
            "\n"
            "def init_project(path: str, *, template: str = 'default') -> dict:\n"
            '    """Initialize a new project at the given path.\n'
            "\n"
            "    Parameters\n"
            "    ----------\n"
            "    path\n"
            "        Directory to create the project in.\n"
            "    template\n"
            "        Project template to use.\n"
            "\n"
            "    Returns\n"
            "    -------\n"
            "    dict\n"
            "        Project metadata.\n"
            '    """\n'
            "    return {'path': path, 'template': template}\n"
            "\n"
            "\n"
            "def run_task(task_name: str, *, verbose: bool = False) -> int:\n"
            '    """Run a named task.\n'
            "\n"
            "    Parameters\n"
            "    ----------\n"
            "    task_name\n"
            "        Name of the task to execute.\n"
            "    verbose\n"
            "        Enable verbose output.\n"
            "\n"
            "    Returns\n"
            "    -------\n"
            "    int\n"
            "        Exit code (0 for success).\n"
            '    """\n'
            "    return 0\n"
        ),
        # ── Terminal recordings ──────────────────────────────────────────
        #
        # Recording 1: Simple CLI commands
        "demos/getting-started.termshow": (
            '{"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 20, "type": "xterm-256color"}, "title": "Getting Started"}\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[0.08, "o", "p"]\n'
            '[0.06, "o", "i"]\n'
            '[0.07, "o", "p"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "i"]\n'
            '[0.06, "o", "n"]\n'
            '[0.08, "o", "s"]\n'
            '[0.06, "o", "t"]\n'
            '[0.07, "o", "a"]\n'
            '[0.06, "o", "l"]\n'
            '[0.08, "o", "l"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "m"]\n'
            '[0.06, "o", "y"]\n'
            '[0.08, "o", "-"]\n'
            '[0.06, "o", "t"]\n'
            '[0.07, "o", "o"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", "l"]\n'
            '[0.6, "o", "\\r\\n"]\n'
            '[0.3, "o", "\\u001b[2K\\u001b[33mCollecting my-tool...\\u001b[0m\\r\\n"]\n'
            '[0.8, "o", "\\u001b[2K\\u001b[33mDownloading my_tool-1.0.0-py3-none-any.whl (12 kB)\\u001b[0m\\r\\n"]\n'
            '[0.5, "o", "\\u001b[2K\\u001b[32mSuccessfully installed my-tool-1.0.0\\u001b[0m\\r\\n"]\n'
            '[1.0, "m", "Installation complete"]\n'
            '[0.8, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[0.08, "o", "m"]\n'
            '[0.06, "o", "y"]\n'
            '[0.08, "o", "-"]\n'
            '[0.06, "o", "t"]\n'
            '[0.07, "o", "o"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", "l"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "i"]\n'
            '[0.06, "o", "n"]\n'
            '[0.08, "o", "i"]\n'
            '[0.06, "o", "t"]\n'
            '[0.6, "o", "\\r\\n"]\n'
            '[0.2, "o", "\\u001b[36m\\u001b[1m\\u2728 Initializing new project...\\u001b[0m\\r\\n"]\n'
            '[0.5, "o", "\\r\\n"]\n'
            '[0.1, "o", "  \\u001b[1mProject name:\\u001b[0m my-awesome-project\\r\\n"]\n'
            '[0.1, "o", "  \\u001b[1mTemplate:\\u001b[0m     default\\r\\n"]\n'
            '[0.1, "o", "  \\u001b[1mDirectory:\\u001b[0m    ./my-awesome-project/\\r\\n"]\n'
            '[0.3, "o", "\\r\\n"]\n'
            '[0.2, "o", "\\u001b[32m\\u2714 Project created successfully!\\u001b[0m\\r\\n"]\n'
            '[1.0, "m", "Project initialized"]\n'
            '[0.8, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[0.08, "o", "m"]\n'
            '[0.06, "o", "y"]\n'
            '[0.08, "o", "-"]\n'
            '[0.06, "o", "t"]\n'
            '[0.07, "o", "o"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", "l"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "r"]\n'
            '[0.06, "o", "u"]\n'
            '[0.08, "o", "n"]\n'
            '[0.1, "o", " "]\n'
            '[0.06, "o", "-"]\n'
            '[0.08, "o", "-"]\n'
            '[0.06, "o", "v"]\n'
            '[0.07, "o", "e"]\n'
            '[0.06, "o", "r"]\n'
            '[0.08, "o", "b"]\n'
            '[0.06, "o", "o"]\n'
            '[0.07, "o", "s"]\n'
            '[0.06, "o", "e"]\n'
            '[0.6, "o", "\\r\\n"]\n'
            '[0.2, "o", "\\u001b[36m\\u2699\\ufe0f  Running task: build\\u001b[0m\\r\\n"]\n'
            '[0.4, "o", "  \\u001b[90m[1/4]\\u001b[0m Collecting sources...\\r\\n"]\n'
            '[0.5, "o", "  \\u001b[90m[2/4]\\u001b[0m Compiling...\\r\\n"]\n'
            '[0.6, "o", "  \\u001b[90m[3/4]\\u001b[0m Running tests...\\r\\n"]\n'
            '[0.4, "o", "  \\u001b[90m[4/4]\\u001b[0m Packaging...\\r\\n"]\n'
            '[0.3, "o", "\\r\\n\\u001b[32m\\u2714 Build complete (1.2s)\\u001b[0m\\r\\n"]\n'
            '[1.0, "m", "Build finished"]\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
        ),
        # Script for the getting-started recording
        "demos/getting-started.termshow.yml": (
            "source: demos/getting-started.termshow\n"
            "\n"
            "settings:\n"
            "  window_chrome: colorful\n"
            "\n"
            "chapters:\n"
            "  - at: 0.0\n"
            '    label: "Install"\n'
            "  - at: 4.5\n"
            '    label: "Initialize"\n'
            "  - at: 10.0\n"
            '    label: "Build"\n'
            "\n"
            "annotations:\n"
            "  - at: 0.5\n"
            "    duration: 3.0\n"
            '    text: "Install from PyPI with pip"\n'
            "    position: top-right\n"
            "    style: callout\n"
            "  - at: 5.0\n"
            "    duration: 3.5\n"
            '    text: "Creates project structure with sensible defaults"\n'
            "    position: bottom-right\n"
            "    style: subtle\n"
            "  - at: 11.0\n"
            "    duration: 3.0\n"
            '    text: "Verbose mode shows each build step"\n'
            "    position: top-right\n"
            "    style: callout\n"
            "\n"
            "snippets:\n"
            "  - at: 0.0\n"
            "    duration: 4.0\n"
            '    text: "pip install my-tool"\n'
            '    label: "Install"\n'
            "  - at: 4.5\n"
            "    duration: 5.0\n"
            '    text: "my-tool init"\n'
            '    label: "Initialize"\n'
            "  - at: 10.0\n"
            "    duration: 4.5\n"
            '    match: "\\\\$ (.+)"\n'
            '    label: "Run"\n'
        ),
        # Recording 2: TUI interface demo
        "demos/tui-demo.termshow": (
            '{"version": 1, "format": "termshow", "term": {"cols": 60, "rows": 18, "type": "xterm-256color"}, "title": "TUI Interface"}\n'
            '[0.3, "o", "\\u001b[2J\\u001b[H"]\n'
            '[0.2, "o", "\\u001b[34m\\u001b[1m\\u250c\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2510\\u001b[0m\\r\\n"]\n'
            '[0.02, "o", "\\u001b[34m\\u001b[1m\\u2502\\u001b[0m                                                \\u001b[34m\\u001b[1m\\u2502\\u001b[0m\\r\\n"]\n'
            '[0.02, "o", "\\u001b[34m\\u001b[1m\\u2502\\u001b[0m   \\u001b[36m\\u001b[1m\\u2728 my-tool v1.0\\u001b[0m                               \\u001b[34m\\u001b[1m\\u2502\\u001b[0m\\r\\n"]\n'
            '[0.02, "o", "\\u001b[34m\\u001b[1m\\u2502\\u001b[0m                                                \\u001b[34m\\u001b[1m\\u2502\\u001b[0m\\r\\n"]\n'
            '[0.02, "o", "\\u001b[34m\\u001b[1m\\u2502\\u001b[0m   \\u001b[33m\\u276f\\u001b[0m \\u001b[1mNew Project\\u001b[0m                              \\u001b[34m\\u001b[1m\\u2502\\u001b[0m\\r\\n"]\n'
            '[0.02, "o", "\\u001b[34m\\u001b[1m\\u2502\\u001b[0m     Open Existing                            \\u001b[34m\\u001b[1m\\u2502\\u001b[0m\\r\\n"]\n'
            '[0.02, "o", "\\u001b[34m\\u001b[1m\\u2502\\u001b[0m     Recent Files                             \\u001b[34m\\u001b[1m\\u2502\\u001b[0m\\r\\n"]\n'
            '[0.02, "o", "\\u001b[34m\\u001b[1m\\u2502\\u001b[0m     Settings                                 \\u001b[34m\\u001b[1m\\u2502\\u001b[0m\\r\\n"]\n'
            '[0.02, "o", "\\u001b[34m\\u001b[1m\\u2502\\u001b[0m     \\u001b[90mQuit\\u001b[0m                                     \\u001b[34m\\u001b[1m\\u2502\\u001b[0m\\r\\n"]\n'
            '[0.02, "o", "\\u001b[34m\\u001b[1m\\u2502\\u001b[0m                                                \\u001b[34m\\u001b[1m\\u2502\\u001b[0m\\r\\n"]\n'
            '[0.02, "o", "\\u001b[34m\\u001b[1m\\u2502\\u001b[0m   \\u001b[90m\\u2191/\\u2193 navigate  \\u23ce enter  q quit\\u001b[0m             \\u001b[34m\\u001b[1m\\u2502\\u001b[0m\\r\\n"]\n'
            '[0.02, "o", "\\u001b[34m\\u001b[1m\\u2502\\u001b[0m                                                \\u001b[34m\\u001b[1m\\u2502\\u001b[0m\\r\\n"]\n'
            '[0.02, "o", "\\u001b[34m\\u001b[1m\\u2514\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2518\\u001b[0m\\r\\n"]\n'
            '[2.0, "m", "Main menu"]\n'
            # User navigates down
            '[0.8, "o", "\\u001b[9;1H"]\n'
            '[0.05, "o", "\\u001b[34m\\u001b[1m\\u2502\\u001b[0m     New Project                              \\u001b[34m\\u001b[1m\\u2502\\u001b[0m"]\n'
            '[0.05, "o", "\\u001b[10;1H"]\n'
            '[0.05, "o", "\\u001b[34m\\u001b[1m\\u2502\\u001b[0m   \\u001b[33m\\u276f\\u001b[0m \\u001b[1mOpen Existing\\u001b[0m                            \\u001b[34m\\u001b[1m\\u2502\\u001b[0m"]\n'
            '[1.5, "m", "Navigate to Open"]\n'
            # User presses Enter
            '[0.5, "o", "\\u001b[2J\\u001b[H"]\n'
            '[0.2, "o", "\\u001b[36m\\u001b[1m\\u2594\\u2594\\u2594\\u2594\\u2594\\u2594\\u2594\\u2594\\u2594\\u2594\\u2594\\u2594\\u2594\\u2594\\u2594\\u2594\\u2594\\u2594\\u2594\\u2594\\u2594\\u2594\\u2594\\u2594\\u2594\\u2594\\u2594\\u2594\\u2594\\u2594\\u001b[0m\\r\\n"]\n'
            '[0.05, "o", "  \\u001b[1mOpen Project\\u001b[0m\\r\\n"]\n'
            '[0.05, "o", "\\u001b[36m\\u001b[1m\\u2581\\u2581\\u2581\\u2581\\u2581\\u2581\\u2581\\u2581\\u2581\\u2581\\u2581\\u2581\\u2581\\u2581\\u2581\\u2581\\u2581\\u2581\\u2581\\u2581\\u2581\\u2581\\u2581\\u2581\\u2581\\u2581\\u2581\\u2581\\u2581\\u2581\\u001b[0m\\r\\n"]\n'
            '[0.1, "o", "\\r\\n"]\n'
            '[0.1, "o", "  \\u001b[90mPath:\\u001b[0m ~/projects/\\u001b[4mmy-app\\u001b[0m\\r\\n"]\n'
            '[0.3, "o", "\\r\\n"]\n'
            '[0.2, "o", "  \\u001b[32m\\u2714\\u001b[0m Loaded \\u001b[1m3 files\\u001b[0m, \\u001b[1m2 configs\\u001b[0m\\r\\n"]\n'
            '[0.5, "o", "  \\u001b[32m\\u2714\\u001b[0m Project ready\\r\\n"]\n'
            '[1.5, "m", "Project loaded"]\n'
        ),
        # Script for TUI demo
        "demos/tui-demo.termshow.yml": (
            "source: demos/tui-demo.termshow\n"
            "\n"
            "settings:\n"
            "  window_chrome: colorful\n"
            "\n"
            "chapters:\n"
            "  - at: 0.0\n"
            '    label: "Main Menu"\n'
            "  - at: 3.0\n"
            '    label: "Navigation"\n'
            "  - at: 5.5\n"
            '    label: "Open Project"\n'
            "\n"
            "annotations:\n"
            "  - at: 0.5\n"
            "    duration: 2.5\n"
            '    text: "Full-screen TUI with keyboard navigation"\n'
            "    position: top-right\n"
            "    style: callout\n"
            "  - at: 3.2\n"
            "    duration: 2.0\n"
            '    text: "Arrow keys move the selection cursor"\n'
            "    position: bottom-right\n"
            "    style: subtle\n"
            "  - at: 6.0\n"
            "    duration: 2.5\n"
            '    text: "Enter confirms and opens the sub-view"\n'
            "    position: top-left\n"
            "    style: callout\n"
        ),
        # Recording 3: Live Great Docs CLI commands
        "demos/great-docs-cli.termshow": (
            '{"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 24, "type": "xterm-256color"}, "title": "Great Docs CLI"}\n'
            # -- Chapter 1: Version check --
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[0.08, "o", "g"]\n'
            '[0.06, "o", "r"]\n'
            '[0.07, "o", "e"]\n'
            '[0.06, "o", "a"]\n'
            '[0.08, "o", "t"]\n'
            '[0.06, "o", "-"]\n'
            '[0.07, "o", "d"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", "c"]\n'
            '[0.06, "o", "s"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "-"]\n'
            '[0.06, "o", "-"]\n'
            '[0.06, "o", "v"]\n'
            '[0.07, "o", "e"]\n'
            '[0.06, "o", "r"]\n'
            '[0.08, "o", "s"]\n'
            '[0.06, "o", "i"]\n'
            '[0.07, "o", "o"]\n'
            '[0.06, "o", "n"]\n'
            '[0.5, "o", "\\r\\n"]\n'
            '[0.2, "o", "great-docs, version 0.10.0\\r\\n"]\n'
            '[1.0, "m", "version"]\n'
            # -- Chapter 2: Scan --
            '[0.6, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[0.08, "o", "g"]\n'
            '[0.06, "o", "r"]\n'
            '[0.07, "o", "e"]\n'
            '[0.06, "o", "a"]\n'
            '[0.08, "o", "t"]\n'
            '[0.06, "o", "-"]\n'
            '[0.07, "o", "d"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", "c"]\n'
            '[0.06, "o", "s"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "s"]\n'
            '[0.06, "o", "c"]\n'
            '[0.08, "o", "a"]\n'
            '[0.06, "o", "n"]\n'
            '[0.5, "o", "\\r\\n"]\n'
            '[0.3, "o", "\\r\\n"]\n'
            '[0.1, "o", "\\u001b[36m\\u001b[1mPackage:\\u001b[0m gdtest_termshow\\r\\n"]\n'
            '[0.1, "o", "\\u001b[36m\\u001b[1mVersion:\\u001b[0m 1.0.0\\r\\n"]\n'
            '[0.1, "o", "\\r\\n"]\n'
            '[0.1, "o", "\\u001b[1mDiscovered Exports (3):\\u001b[0m\\r\\n"]\n'
            '[0.05, "o", "\\r\\n"]\n'
            '[0.05, "o", "  \\u001b[33mFunctions:\\u001b[0m\\r\\n"]\n'
            '[0.05, "o", "    \\u001b[32m\\u2022\\u001b[0m greet(name)\\r\\n"]\n'
            '[0.05, "o", "    \\u001b[32m\\u2022\\u001b[0m init_project(path, *, template)\\r\\n"]\n'
            '[0.05, "o", "    \\u001b[32m\\u2022\\u001b[0m run_task(task_name, *, verbose)\\r\\n"]\n'
            '[0.1, "o", "\\r\\n"]\n'
            '[0.1, "o", "\\u001b[90m\\u2139 All 3 exports have docstrings.\\u001b[0m\\r\\n"]\n'
            '[1.2, "m", "scan complete"]\n'
            # -- Chapter 3: Lint --
            '[0.6, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[0.08, "o", "g"]\n'
            '[0.06, "o", "r"]\n'
            '[0.07, "o", "e"]\n'
            '[0.06, "o", "a"]\n'
            '[0.08, "o", "t"]\n'
            '[0.06, "o", "-"]\n'
            '[0.07, "o", "d"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", "c"]\n'
            '[0.06, "o", "s"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "l"]\n'
            '[0.06, "o", "i"]\n'
            '[0.08, "o", "n"]\n'
            '[0.06, "o", "t"]\n'
            '[0.5, "o", "\\r\\n"]\n'
            '[0.3, "o", "\\r\\n"]\n'
            '[0.1, "o", "\\u001b[36m\\u001b[1mLinting:\\u001b[0m gdtest_termshow\\r\\n"]\n'
            '[0.2, "o", "\\r\\n"]\n'
            '[0.15, "o", "  \\u001b[32m\\u2714\\u001b[0m docstrings \\u001b[90m........\\u001b[0m 3/3 documented\\r\\n"]\n'
            '[0.15, "o", "  \\u001b[32m\\u2714\\u001b[0m cross-refs \\u001b[90m........\\u001b[0m no broken references\\r\\n"]\n'
            '[0.15, "o", "  \\u001b[32m\\u2714\\u001b[0m style \\u001b[90m.............\\u001b[0m consistent (numpy)\\r\\n"]\n'
            '[0.15, "o", "  \\u001b[32m\\u2714\\u001b[0m directives \\u001b[90m........\\u001b[0m all valid\\r\\n"]\n'
            '[0.15, "o", "  \\u001b[32m\\u2714\\u001b[0m stale-versions \\u001b[90m....\\u001b[0m none found\\r\\n"]\n'
            '[0.2, "o", "\\r\\n"]\n'
            '[0.1, "o", "\\u001b[32m\\u001b[1m\\u2728 All checks passed!\\u001b[0m No issues found.\\r\\n"]\n'
            '[1.2, "m", "lint complete"]\n'
            # -- Chapter 4: Term render --
            '[0.6, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[0.08, "o", "g"]\n'
            '[0.06, "o", "r"]\n'
            '[0.07, "o", "e"]\n'
            '[0.06, "o", "a"]\n'
            '[0.08, "o", "t"]\n'
            '[0.06, "o", "-"]\n'
            '[0.07, "o", "d"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", "c"]\n'
            '[0.06, "o", "s"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "t"]\n'
            '[0.06, "o", "e"]\n'
            '[0.08, "o", "r"]\n'
            '[0.06, "o", "m"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "r"]\n'
            '[0.06, "o", "e"]\n'
            '[0.08, "o", "n"]\n'
            '[0.06, "o", "d"]\n'
            '[0.07, "o", "e"]\n'
            '[0.06, "o", "r"]\n'
            '[0.1, "o", " "]\n'
            '[0.06, "o", "d"]\n'
            '[0.07, "o", "e"]\n'
            '[0.06, "o", "m"]\n'
            '[0.08, "o", "o"]\n'
            '[0.06, "o", "s"]\n'
            '[0.07, "o", "/"]\n'
            '[0.06, "o", "g"]\n'
            '[0.07, "o", "e"]\n'
            '[0.06, "o", "t"]\n'
            '[0.08, "o", "t"]\n'
            '[0.06, "o", "i"]\n'
            '[0.07, "o", "n"]\n'
            '[0.06, "o", "g"]\n'
            '[0.08, "o", "-"]\n'
            '[0.06, "o", "s"]\n'
            '[0.07, "o", "t"]\n'
            '[0.06, "o", "a"]\n'
            '[0.07, "o", "r"]\n'
            '[0.06, "o", "t"]\n'
            '[0.08, "o", "e"]\n'
            '[0.06, "o", "d"]\n'
            '[0.6, "o", "\\r\\n"]\n'
            '[0.3, "o", "\\r\\n"]\n'
            '[0.1, "o", "\\u001b[36m\\u001b[1mRendering:\\u001b[0m demos/getting-started.termshow\\r\\n"]\n'
            '[0.2, "o", "  \\u001b[90mScript:\\u001b[0m  demos/getting-started.termshow.yml\\r\\n"]\n'
            '[0.1, "o", "  \\u001b[90mChrome:\\u001b[0m  colorful\\r\\n"]\n'
            '[0.1, "o", "  \\u001b[90mSize:\\u001b[0m    80\\u00d720\\r\\n"]\n'
            '[0.2, "o", "\\r\\n"]\n'
            '[0.4, "o", "  \\u001b[33m\\u25cf\\u001b[0m Parsing recording (24 events)...\\r\\n"]\n'
            '[0.5, "o", "  \\u001b[33m\\u25cf\\u001b[0m Rendering keyframes...\\r\\n"]\n'
            '[0.2, "o", "    \\u001b[90mframe-000.svg\\u001b[0m (0.00s)\\r\\n"]\n'
            '[0.15, "o", "    \\u001b[90mframe-001.svg\\u001b[0m (0.50s)\\r\\n"]\n'
            '[0.15, "o", "    \\u001b[90mframe-002.svg\\u001b[0m (2.08s)\\r\\n"]\n'
            '[0.15, "o", "    \\u001b[90mframe-003.svg\\u001b[0m (3.28s)\\r\\n"]\n'
            '[0.15, "o", "    \\u001b[90mframe-004.svg\\u001b[0m (4.50s)\\r\\n"]\n'
            '[0.15, "o", "    \\u001b[90mframe-005.svg\\u001b[0m (5.10s)\\r\\n"]\n'
            '[0.15, "o", "    \\u001b[90mframe-006.svg\\u001b[0m (7.60s)\\r\\n"]\n'
            '[0.15, "o", "    \\u001b[90mframe-007.svg\\u001b[0m (10.00s)\\r\\n"]\n'
            '[0.15, "o", "    \\u001b[90mframe-008.svg\\u001b[0m (10.60s)\\r\\n"]\n'
            '[0.15, "o", "    \\u001b[90mframe-009.svg\\u001b[0m (14.20s)\\r\\n"]\n'
            '[0.2, "o", "  \\u001b[33m\\u25cf\\u001b[0m Writing manifest.json\\r\\n"]\n'
            '[0.1, "o", "\\r\\n"]\n'
            '[0.1, "o", "\\u001b[32m\\u001b[1m\\u2714 Done!\\u001b[0m 10 frames, 3 chapters, 16.6s duration\\r\\n"]\n'
            '[0.1, "o", "  \\u001b[90mOutput: termshow/getting-started/\\u001b[0m\\r\\n"]\n'
            '[1.0, "m", "render complete"]\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
        ),
        # Script for the Great Docs CLI demo
        "demos/great-docs-cli.termshow.yml": (
            "source: demos/great-docs-cli.termshow\n"
            "\n"
            "settings:\n"
            "  window_chrome: colorful\n"
            "\n"
            "chapters:\n"
            "  - at: 0.0\n"
            '    label: "Version"\n'
            "  - at: 3.5\n"
            '    label: "Scan Exports"\n'
            "  - at: 9.0\n"
            '    label: "Lint Docs"\n'
            "  - at: 14.5\n"
            '    label: "Render Recording"\n'
            "\n"
            "annotations:\n"
            "  - at: 0.5\n"
            "    duration: 2.5\n"
            '    text: "Check your installed version"\n'
            "    position: top-right\n"
            "    style: subtle\n"
            "  - at: 4.0\n"
            "    duration: 4.0\n"
            '    text: "Discovers all public exports with docstring coverage"\n'
            "    position: top-right\n"
            "    style: callout\n"
            "  - at: 9.5\n"
            "    duration: 4.0\n"
            '    text: "Checks docs quality: docstrings, cross-refs, style, and more"\n'
            "    position: top-right\n"
            "    style: callout\n"
            "  - at: 15.5\n"
            "    duration: 4.0\n"
            '    text: "Renders .termshow recordings into SVG keyframes for embedding"\n'
            "    position: top-right\n"
            "    style: highlight\n"
            "\n"
            "snippets:\n"
            "  - at: 0.0\n"
            "    duration: 3.0\n"
            '    match: "\\\\$ (.+)"\n'
            '    label: "Version"\n'
            "  - at: 3.5\n"
            "    duration: 5.0\n"
            '    match: "\\\\$ (.+)"\n'
            '    label: "Scan"\n'
            "  - at: 9.0\n"
            "    duration: 5.0\n"
            '    match: "\\\\$ (.+)"\n'
            '    label: "Lint"\n'
            "  - at: 14.5\n"
            "    duration: 6.0\n"
            '    match: "\\\\$ (.+)"\n'
            '    label: "Render"\n'
        ),
        # ── User guide pages ─────────────────────────────────────────────
        "user_guide/01-quick-start.qmd": (
            "---\n"
            "title: Quick Start\n"
            "---\n"
            "\n"
            "## Installation & First Run\n"
            "\n"
            "Watch this quick demo to see `my-tool` in action — from installation\n"
            "through your first build:\n"
            "\n"
            '{{< termshow file="demos/getting-started" pause_on_chapters="true" >}}\n'
            "\n"
            "### What just happened?\n"
            "\n"
            "The recording above shows three steps:\n"
            "\n"
            "1. **Install** — `pip install my-tool` fetches the package from PyPI\n"
            "2. **Initialize** — `my-tool init` scaffolds a new project\n"
            "3. **Build** — `my-tool run --verbose` executes the build pipeline\n"
            "\n"
            "You can click any chapter marker in the timeline to jump directly\n"
            "to that step, or use keyboard shortcuts:\n"
            "\n"
            "| Key | Action |\n"
            "|-----|--------|\n"
            "| Space | Play/Pause |\n"
            "| ← / → | Seek 5 seconds |\n"
            "| . | Next chapter |\n"
            "| , | Previous chapter |\n"
            "\n"
            "## Next Steps\n"
            "\n"
            "Now that you have `my-tool` installed, check out the\n"
            "[TUI Interface](02-tui-interface.qmd) guide for the interactive mode.\n"
        ),
        "user_guide/02-tui-interface.qmd": (
            "---\n"
            "title: TUI Interface\n"
            "---\n"
            "\n"
            "## Interactive Mode\n"
            "\n"
            "`my-tool` includes a full-screen terminal interface for visual\n"
            "project management. Launch it with:\n"
            "\n"
            "```bash\n"
            "my-tool --interactive\n"
            "```\n"
            "\n"
            "Here's how it looks:\n"
            "\n"
            '{{< termshow file="demos/tui-demo" pause_on_chapters="true" >}}\n'
            "\n"
            "### Navigation\n"
            "\n"
            "The TUI uses standard terminal navigation:\n"
            "\n"
            "- **↑/↓** arrows to move between items\n"
            "- **Enter** to select/confirm\n"
            "- **q** to quit\n"
            "- **Esc** to go back one level\n"
            "\n"
            "### Features\n"
            "\n"
            "The interactive mode provides:\n"
            "\n"
            "- Project creation wizard\n"
            "- File browser with preview\n"
            "- Live build output\n"
            "- Configuration editor\n"
        ),
        "user_guide/03-recording-tips.qmd": (
            "---\n"
            "title: Recording Tips\n"
            "---\n"
            "\n"
            "## Creating Your Own Recordings\n"
            "\n"
            "Great Docs makes it easy to record, edit, and embed terminal\n"
            "sessions in your documentation.\n"
            "\n"
            "### Recording\n"
            "\n"
            "```bash\n"
            "# Start recording\n"
            "great-docs termshow record demos/my-demo.termshow\n"
            "\n"
            "# Perform your CLI actions...\n"
            "# Press Ctrl+D or type 'exit' to stop\n"
            "```\n"
            "\n"
            "### Editing with Scripts\n"
            "\n"
            "Create a `.termshow.yml` file alongside your recording to add\n"
            "chapters, annotations, and timing adjustments:\n"
            "\n"
            "```yaml\n"
            "source: demos/my-demo.termshow\n"
            "\n"
            "settings:\n"
            "  window_chrome: colorful\n"
            "\n"
            "chapters:\n"
            "  - at: 0.0\n"
            "    label: Introduction\n"
            "  - at: 10.0\n"
            "    label: Main Feature\n"
            "\n"
            "annotations:\n"
            "  - at: 2.0\n"
            "    duration: 3.0\n"
            "    text: This step installs dependencies\n"
            "    position: top-right\n"
            "    style: callout\n"
            "\n"
            "cuts:\n"
            "  - from: 5.0\n"
            "    to: 8.0\n"
            "    type: ellipsis\n"
            "```\n"
            "\n"
            "### Rendering\n"
            "\n"
            "```bash\n"
            "# Render SVG frames\n"
            "great-docs termshow render demos/my-demo.termshow\n"
            "```\n"
            "\n"
            "### Embedding\n"
            "\n"
            "Use the `termshow` shortcode in your `.qmd` files:\n"
            "\n"
            "```markdown\n"
            '{{< termshow file="demos/my-demo" pause_on_chapters="true" >}}\n'
            "```\n"
            "\n"
            "### Importing Existing Recordings\n"
            "\n"
            "Already have recordings from asciinema?\n"
            "\n"
            "```bash\n"
            "# Import from asciinema\n"
            "great-docs termshow import-cast recording.cast demos/my-demo\n"
            "```\n"
        ),
        # ── Detailed termshow guide ───────────────────────────────────
        "user_guide/04-termshow-guide.qmd": (
            "---\n"
            "title: Termshow Guide\n"
            "---\n"
            "\n"
            "## Overview\n"
            "\n"
            "The **termshow** is Great Docs' built-in terminal recording player.\n"
            "It renders pre-recorded terminal sessions as interactive, frame-accurate\n"
            "SVG animations directly in your documentation pages — no JavaScript\n"
            "framework dependencies, no external services.\n"
            "\n"
            "Key capabilities:\n"
            "\n"
            "- Frame-accurate SVG rendering of terminal output\n"
            "- Chapter-based navigation with labeled markers\n"
            "- Contextual annotations that appear at specific timestamps\n"
            "- Keyboard shortcuts for power users\n"
            "- Adjustable playback speed (0.5× to 3×)\n"
            "- Works offline and with `file://` protocol (all data embedded inline)\n"
            "- Responsive layout that scales to any viewport width\n"
            "- Light/dark theme support (follows the site theme)\n"
            "\n"
            "### Live Demo\n"
            "\n"
            "Here's a recording of real Great Docs CLI commands — `scan`, `lint`,\n"
            "and `term render` — running against this very package:\n"
            "\n"
            '{{< termshow file="demos/great-docs-cli" pause_on_chapters="true" >}}\n'
            "\n"
            "## The Recording Format\n"
            "\n"
            "Termshow uses a two-file system for each recording:\n"
            "\n"
            "### The `.termshow` File\n"
            "\n"
            "This is the raw terminal recording in NDJSON format. Each line is\n"
            "a JSON array with `[delay, event_type, data]`:\n"
            "\n"
            "```json\n"
            '{"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 20}}\n'
            '[0.5, "o", "$ "]\n'
            '[0.1, "o", "echo hello"]\n'
            '[0.6, "o", "\\r\\nhello\\r\\n"]\n'
            '[1.0, "m", "Command executed"]\n'
            "```\n"
            "\n"
            "Event types:\n"
            "\n"
            "| Type | Meaning |\n"
            "|------|---------|\n"
            '| `"o"` | Output — terminal data written to stdout |\n'
            '| `"i"` | Input — user keystrokes (for display purposes) |\n'
            '| `"m"` | Marker — internal marker used for chapter sync |\n'
            "\n"
            "The header line sets terminal dimensions and metadata.\n"
            "\n"
            "### The `.termshow.yml` Script File\n"
            "\n"
            "This companion file defines chapters, annotations, timing adjustments,\n"
            "and visual settings:\n"
            "\n"
            "```yaml\n"
            "source: demos/my-recording.termshow\n"
            "\n"
            "settings:\n"
            "  window_chrome: colorful   # Window decoration style\n"
            "  theme: monokai            # Terminal color scheme\n"
            "  font_size: 14             # Font size in pixels\n"
            "\n"
            "chapters:\n"
            "  - at: 0.0\n"
            "    label: Introduction\n"
            "  - at: 5.0\n"
            "    label: Configuration\n"
            "  - at: 12.0\n"
            "    label: Running Tests\n"
            "\n"
            "annotations:\n"
            "  - at: 1.0\n"
            "    duration: 3.0\n"
            "    text: This installs all required dependencies\n"
            "    position: top-right\n"
            "    style: callout\n"
            "  - at: 6.0\n"
            "    duration: 2.5\n"
            "    text: Configuration is auto-detected\n"
            "    position: bottom-right\n"
            "    style: subtle\n"
            "\n"
            "cuts:\n"
            "  - from: 8.0\n"
            "    to: 11.0\n"
            "    type: ellipsis   # Shows '…' for the cut section\n"
            "\n"
            "snippets:\n"
            "  - at: 0.0\n"
            "    duration: 5.0\n"
            "    text: pip install my-package\n"
            "    label: Install\n"
            "  - at: 12.0\n"
            "    duration: 4.0\n"
            '    match: "\\\\$ (.+)"   # Regex: captures command after $ prompt\n'
            "    label: Run\n"
            "```\n"
            "\n"
            "## Snippets\n"
            "\n"
            "Snippets add a **copy button** to the player that appears during a time range.\n"
            "Readers can click it to copy text to their clipboard without manual retyping.\n"
            "\n"
            "### Literal Text\n"
            "\n"
            "Use `text` when you know the exact string to copy:\n"
            "\n"
            "```yaml\n"
            "snippets:\n"
            "  - at: 0.5\n"
            "    duration: 7.0\n"
            "    text: pip install my-tool\n"
            "    label: Install\n"
            "```\n"
            "\n"
            "### Regex Match\n"
            "\n"
            "Use `match` to extract text dynamically from the terminal buffer:\n"
            "\n"
            "```yaml\n"
            "snippets:\n"
            "  - at: 0.5\n"
            "    duration: 7.0\n"
            '    match: "\\\\$ (.+)"\n'
            "    label: Copy Command\n"
            "```\n"
            "\n"
            "The regex runs against the visible terminal text when the reader clicks\n"
            "the copy button. If it has a capture group, group 1 is copied; otherwise\n"
            "the full match is used. This is useful when the terminal shows a typed\n"
            "command and you want to extract it without hardcoding.\n"
            "\n"
            "### Snippet Fields\n"
            "\n"
            "| Field | Default | Description |\n"
            "|-------|---------|-------------|\n"
            "| `at` | *(required)* | Time in seconds when the button appears |\n"
            "| `duration` | `5.0` | How long the button stays visible |\n"
            '| `text` | `""` | Literal text copied on click |\n'
            '| `match` | `""` | Regex matched against visible terminal text |\n'
            '| `label` | `"Copy"` | Button label shown alongside the copy icon |\n'
            "\n"
            "At least one of `text` or `match` must be provided. If both are set,\n"
            "`match` takes priority (with `text` as fallback).\n"
            "\n"
            "## Settings Reference\n"
            "\n"
            "| Setting | Default | Description |\n"
            "|---------|---------|-------------|\n"
            "| `window_chrome` | `colorful` | Window decoration: `colorful`, `plain`, `none` |\n"
            "| `theme` | (auto) | Terminal color scheme |\n"
            "| `font_size` | `14` | Font size in rendered SVG (px) |\n"
            "| `line_height` | `1.2` | Line height multiplier |\n"
            "| `padding` | `12` | Inner padding of the terminal area (px) |\n"
            "\n"
            "## Annotation Styles\n"
            "\n"
            "Annotations appear as overlays on the terminal at specified times.\n"
            "Three styles are available:\n"
            "\n"
            "| Style | Appearance |\n"
            "|-------|------------|\n"
            "| `callout` | Semi-opaque dark card with accent border |\n"
            "| `subtle` | Lighter, smaller text — less intrusive |\n"
            "| `highlight` | Amber-tinted with warm border — draws attention |\n"
            "\n"
            "Positions: `top-left`, `top`, `top-right`, `left`, `right`,\n"
            "`bottom-left`, `bottom`, `bottom-right`.\n"
            "\n"
            "Widths: `small` (25%), `medium` (50%, default), `large` (75%).\n"
            "\n"
            "## Embedding in Pages\n"
            "\n"
            "Use the `termshow` Quarto shortcode in any `.qmd` file:\n"
            "\n"
            "````markdown\n"
            "## Basic usage\n"
            "\n"
            '{{< termshow file="demos/getting-started" >}}\n'
            "\n"
            "## With chapter pausing\n"
            "\n"
            '{{< termshow file="demos/workflow" pause_on_chapters="true" >}}\n'
            "\n"
            "## Autoplay with custom speed\n"
            "\n"
            '{{< termshow file="demos/quick" autoplay="true" speed="1.5" >}}\n'
            "````\n"
            "\n"
            "### Shortcode Options\n"
            "\n"
            "| Option | Default | Description |\n"
            "|--------|---------|-------------|\n"
            "| `file` | (required) | Path to `.termshow` file (without extension) |\n"
            "| `autoplay` | `false` | Start playing automatically on page load |\n"
            "| `loop` | `false` | Loop playback when reaching the end |\n"
            "| `speed` | `1` | Initial playback speed multiplier |\n"
            "| `pause_on_chapters` | `false` | Auto-pause at each chapter boundary |\n"
            "| `controls` | `true` | Show the control bar |\n"
            "| `theme` | `auto` | Player theme: `auto`, `dark`, or `light` |\n"
            "\n"
            "## Player Controls\n"
            "\n"
            "The player provides a full set of interactive controls:\n"
            "\n"
            "### Control Bar\n"
            "\n"
            "From left to right:\n"
            "\n"
            "1. **Play/Pause button** — Toggles playback. Shows ↺ (replay) at the end.\n"
            "2. **Current time** — Elapsed time counter.\n"
            "3. **Timeline scrub bar** — Click anywhere to seek. Chapter markers\n"
            "   appear as gold ticks with wider hit targets for easy clicking.\n"
            "4. **Remaining time** — Counts down to zero during playback.\n"
            "5. **Speed button** — Cycles through 0.5×, 1×, 1.5×, 2×, 3×.\n"
            "\n"
            "### Chapter Bar\n"
            "\n"
            "A thin overlay at the top of the player shows the name of the\n"
            "current chapter, updating as playback progresses.\n"
            "\n"
            "### Center Overlay\n"
            "\n"
            "A semi-transparent button in the center of the viewport:\n"
            "\n"
            "- **Before playback** — Shows ▶ as a call-to-action.\n"
            "- **After playback ends** — Shows ↺ to indicate replay. Clicking\n"
            "  returns the player to its initial state (frame 0, ready to play).\n"
            "- **During chapter pauses** — Hidden, so the terminal content\n"
            "  remains fully visible.\n"
            "\n"
            "### Keyboard Shortcuts\n"
            "\n"
            "Click the player viewport first to give it focus, then use:\n"
            "\n"
            "| Key | Action |\n"
            "|-----|--------|\n"
            "| `Space` | Play / Pause (or reset from ended state) |\n"
            "| `→` | Seek forward 5 seconds |\n"
            "| `←` | Seek backward 5 seconds |\n"
            "| `.` | Jump to next chapter |\n"
            "| `,` | Jump to previous chapter |\n"
            "\n"
            "## Workflow\n"
            "\n"
            "The full termshow workflow from recording to rendered page:\n"
            "\n"
            "```text\n"
            "1. Record          great-docs termshow record demos/my-demo.termshow\n"
            "2. Edit script     Create/edit demos/my-demo.termshow.yml\n"
            "3. Preview         great-docs termshow play demos/my-demo.termshow\n"
            "4. Embed           Add {{< termshow ... >}} to your .qmd\n"
            "5. Build           great-docs build (renders SVG frames automatically)\n"
            "```\n"
            "\n"
            "### Step 1: Record\n"
            "\n"
            "```bash\n"
            "great-docs termshow record demos/install-guide.termshow\n"
            "```\n"
            "\n"
            "This launches a recording session. Everything you type and see in\n"
            "the terminal is captured with precise timing. Press `Ctrl+D` or\n"
            "type `exit` to end the recording.\n"
            "\n"
            "### Step 2: Create the Script\n"
            "\n"
            "Create `demos/install-guide.termshow.yml` alongside the recording.\n"
            "Define chapters at logical breakpoints in your workflow, and add\n"
            "annotations to explain what's happening:\n"
            "\n"
            "```yaml\n"
            "source: demos/install-guide.termshow\n"
            "\n"
            "settings:\n"
            "  window_chrome: colorful\n"
            "\n"
            "chapters:\n"
            "  - at: 0.0\n"
            "    label: Setup\n"
            "  - at: 8.0\n"
            "    label: Install\n"
            "  - at: 15.0\n"
            "    label: Verify\n"
            "\n"
            "annotations:\n"
            "  - at: 1.0\n"
            "    duration: 3.0\n"
            "    text: Start by activating the virtual environment\n"
            "    position: top-right\n"
            "    style: callout\n"
            "```\n"
            "\n"
            "### Step 3: Preview\n"
            "\n"
            "```bash\n"
            "great-docs termshow play demos/install-guide.termshow\n"
            "```\n"
            "\n"
            "This plays the recording in your terminal so you can verify\n"
            "timing and check that chapter boundaries feel natural.\n"
            "\n"
            "### Step 4: Embed\n"
            "\n"
            "Add the shortcode to any user guide or documentation page:\n"
            "\n"
            "```markdown\n"
            '{{< termshow file="demos/install-guide" pause_on_chapters="true" >}}\n'
            "```\n"
            "\n"
            "### Step 5: Build\n"
            "\n"
            "```bash\n"
            "great-docs build\n"
            "```\n"
            "\n"
            "During the build, Great Docs:\n"
            "\n"
            "1. Finds all `.termshow` files in your project\n"
            "2. Renders each recording into a series of SVG keyframes\n"
            "3. Generates a `manifest.json` with timing, chapters, and annotations\n"
            "4. The Lua shortcode filter embeds the manifest and all SVG frames\n"
            "   inline in the HTML — no runtime fetches needed\n"
            "\n"
            "## Importing Existing Recordings\n"
            "\n"
            "Already have terminal recordings from asciinema? Import them:\n"
            "\n"
            "```bash\n"
            "# From asciinema (.cast files)\n"
            "great-docs termshow import-cast recording.cast demos/my-demo\n"
            "```\n"
            "\n"
            "The import preserves timing and terminal dimensions. You'll still\n"
            "want to create a `.termshow.yml` script to add chapters and\n"
            "annotations.\n"
            "\n"
            "## Tips & Best Practices\n"
            "\n"
            "- **Keep recordings short** — 15–30 seconds is ideal. Split longer\n"
            "  workflows into multiple recordings.\n"
            "  waiting through your thinking time.\n"
            "- **Place chapters at logical transitions** — Each chapter should\n"
            "  represent one distinct step in the workflow.\n"
            "- **Use `pause_on_chapters`** for tutorials — Gives readers time\n"
            "  to absorb each step before the next one plays.\n"
            "- **Annotations are brief** — One sentence max. They complement\n"
            "  the terminal output, not replace it.\n"
            "- **Test at different speeds** — Make sure annotations are still\n"
            "  readable at 1.5× and 2× speed.\n"
            "- **80 columns, 20 rows** works well for most CLI recordings.\n"
            "  Use 60 columns for narrower TUI demos.\n"
            "\n"
            "## Architecture\n"
            "\n"
            "Under the hood, termshow works in two phases:\n"
            "\n"
            "**Build time** (Python + Lua):\n"
            "\n"
            "1. `core.py` discovers `.termshow` files and calls the renderer\n"
            "2. The renderer parses the NDJSON recording + YAML script\n"
            "3. It produces SVG keyframes at each visual change point\n"
            "4. A `manifest.json` captures timing, chapters, and annotation data\n"
            "5. The Lua shortcode embeds everything inline as `<script>` JSON blocks\n"
            "\n"
            "**Page load** (JavaScript):\n"
            "\n"
            "1. `termshow.js` finds `.gd-termshow` containers\n"
            "2. Reads inline manifest and SVG frame data from `<script>` elements\n"
            "3. Builds the player UI (viewport, controls, chapter bar, overlays)\n"
            "4. On play: advances time via `requestAnimationFrame`, swaps SVG\n"
            "   frames at the correct timestamps\n"
            "\n"
            "This architecture means:\n"
            "\n"
            "- Zero network requests at runtime\n"
            "- Works with `file://` protocol (offline docs)\n"
            "- No CORS or fetch issues\n"
            "- SVGs scale perfectly at any zoom level\n"
        ),
        # ── Annotation gallery recordings ─────────────────────────────
        #
        # A compact base recording used for all annotation position/width
        # demos. Shows a simple command + output so annotations are visible
        # against real terminal content.
        #
        # --- Position demos ---
        "demos/ann-pos-top-left.termshow": (
            '{"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 20, "type": "xterm-256color"}, "title": "Annotation Position Demo"}\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[0.08, "o", "e"]\n'
            '[0.06, "o", "c"]\n'
            '[0.07, "o", "h"]\n'
            '[0.06, "o", "o"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "\\""]\n'
            '[0.06, "o", "H"]\n'
            '[0.07, "o", "e"]\n'
            '[0.06, "o", "l"]\n'
            '[0.08, "o", "l"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", " "]\n'
            '[0.06, "o", "f"]\n'
            '[0.07, "o", "r"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", "m"]\n'
            '[0.06, "o", " "]\n'
            '[0.07, "o", "G"]\n'
            '[0.06, "o", "r"]\n'
            '[0.08, "o", "e"]\n'
            '[0.06, "o", "a"]\n'
            '[0.07, "o", "t"]\n'
            '[0.06, "o", " "]\n'
            '[0.08, "o", "D"]\n'
            '[0.06, "o", "o"]\n'
            '[0.07, "o", "c"]\n'
            '[0.06, "o", "s"]\n'
            '[0.08, "o", "\\""]\n'
            '[0.5, "o", "\\r\\n"]\n'
            '[0.2, "o", "Hello from Great Docs\\r\\n"]\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[5.0, "o", ""]\n'
        ),
        "demos/ann-pos-top-left.termshow.yml": (
            "source: demos/ann-pos-top-left.termshow\n"
            "\n"
            "settings:\n"
            "  window_chrome: colorful\n"
            "\n"
            "annotations:\n"
            "  - at: 1.0\n"
            "    duration: 5.0\n"
            '    text: "Annotation at top-left"\n'
            "    position: top-left\n"
            "    style: callout\n"
        ),
        "demos/ann-pos-top.termshow": (
            '{"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 20, "type": "xterm-256color"}, "title": "Annotation Position Demo"}\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[0.08, "o", "e"]\n'
            '[0.06, "o", "c"]\n'
            '[0.07, "o", "h"]\n'
            '[0.06, "o", "o"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "\\""]\n'
            '[0.06, "o", "H"]\n'
            '[0.07, "o", "e"]\n'
            '[0.06, "o", "l"]\n'
            '[0.08, "o", "l"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", " "]\n'
            '[0.06, "o", "f"]\n'
            '[0.07, "o", "r"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", "m"]\n'
            '[0.06, "o", " "]\n'
            '[0.07, "o", "G"]\n'
            '[0.06, "o", "r"]\n'
            '[0.08, "o", "e"]\n'
            '[0.06, "o", "a"]\n'
            '[0.07, "o", "t"]\n'
            '[0.06, "o", " "]\n'
            '[0.08, "o", "D"]\n'
            '[0.06, "o", "o"]\n'
            '[0.07, "o", "c"]\n'
            '[0.06, "o", "s"]\n'
            '[0.08, "o", "\\""]\n'
            '[0.5, "o", "\\r\\n"]\n'
            '[0.2, "o", "Hello from Great Docs\\r\\n"]\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[5.0, "o", ""]\n'
        ),
        "demos/ann-pos-top.termshow.yml": (
            "source: demos/ann-pos-top.termshow\n"
            "\n"
            "settings:\n"
            "  window_chrome: colorful\n"
            "\n"
            "annotations:\n"
            "  - at: 1.0\n"
            "    duration: 5.0\n"
            '    text: "Annotation at top"\n'
            "    position: top\n"
            "    style: callout\n"
        ),
        "demos/ann-pos-top-right.termshow": (
            '{"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 20, "type": "xterm-256color"}, "title": "Annotation Position Demo"}\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[0.08, "o", "e"]\n'
            '[0.06, "o", "c"]\n'
            '[0.07, "o", "h"]\n'
            '[0.06, "o", "o"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "\\""]\n'
            '[0.06, "o", "H"]\n'
            '[0.07, "o", "e"]\n'
            '[0.06, "o", "l"]\n'
            '[0.08, "o", "l"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", " "]\n'
            '[0.06, "o", "f"]\n'
            '[0.07, "o", "r"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", "m"]\n'
            '[0.06, "o", " "]\n'
            '[0.07, "o", "G"]\n'
            '[0.06, "o", "r"]\n'
            '[0.08, "o", "e"]\n'
            '[0.06, "o", "a"]\n'
            '[0.07, "o", "t"]\n'
            '[0.06, "o", " "]\n'
            '[0.08, "o", "D"]\n'
            '[0.06, "o", "o"]\n'
            '[0.07, "o", "c"]\n'
            '[0.06, "o", "s"]\n'
            '[0.08, "o", "\\""]\n'
            '[0.5, "o", "\\r\\n"]\n'
            '[0.2, "o", "Hello from Great Docs\\r\\n"]\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[5.0, "o", ""]\n'
        ),
        "demos/ann-pos-top-right.termshow.yml": (
            "source: demos/ann-pos-top-right.termshow\n"
            "\n"
            "settings:\n"
            "  window_chrome: colorful\n"
            "\n"
            "annotations:\n"
            "  - at: 1.0\n"
            "    duration: 5.0\n"
            '    text: "Annotation at top-right"\n'
            "    position: top-right\n"
            "    style: callout\n"
        ),
        "demos/ann-pos-left.termshow": (
            '{"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 20, "type": "xterm-256color"}, "title": "Annotation Position Demo"}\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[0.08, "o", "e"]\n'
            '[0.06, "o", "c"]\n'
            '[0.07, "o", "h"]\n'
            '[0.06, "o", "o"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "\\""]\n'
            '[0.06, "o", "H"]\n'
            '[0.07, "o", "e"]\n'
            '[0.06, "o", "l"]\n'
            '[0.08, "o", "l"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", " "]\n'
            '[0.06, "o", "f"]\n'
            '[0.07, "o", "r"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", "m"]\n'
            '[0.06, "o", " "]\n'
            '[0.07, "o", "G"]\n'
            '[0.06, "o", "r"]\n'
            '[0.08, "o", "e"]\n'
            '[0.06, "o", "a"]\n'
            '[0.07, "o", "t"]\n'
            '[0.06, "o", " "]\n'
            '[0.08, "o", "D"]\n'
            '[0.06, "o", "o"]\n'
            '[0.07, "o", "c"]\n'
            '[0.06, "o", "s"]\n'
            '[0.08, "o", "\\""]\n'
            '[0.5, "o", "\\r\\n"]\n'
            '[0.2, "o", "Hello from Great Docs\\r\\n"]\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[5.0, "o", ""]\n'
        ),
        "demos/ann-pos-left.termshow.yml": (
            "source: demos/ann-pos-left.termshow\n"
            "\n"
            "settings:\n"
            "  window_chrome: colorful\n"
            "\n"
            "annotations:\n"
            "  - at: 1.0\n"
            "    duration: 5.0\n"
            '    text: "Annotation at left"\n'
            "    position: left\n"
            "    style: callout\n"
        ),
        "demos/ann-pos-right.termshow": (
            '{"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 20, "type": "xterm-256color"}, "title": "Annotation Position Demo"}\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[0.08, "o", "e"]\n'
            '[0.06, "o", "c"]\n'
            '[0.07, "o", "h"]\n'
            '[0.06, "o", "o"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "\\""]\n'
            '[0.06, "o", "H"]\n'
            '[0.07, "o", "e"]\n'
            '[0.06, "o", "l"]\n'
            '[0.08, "o", "l"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", " "]\n'
            '[0.06, "o", "f"]\n'
            '[0.07, "o", "r"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", "m"]\n'
            '[0.06, "o", " "]\n'
            '[0.07, "o", "G"]\n'
            '[0.06, "o", "r"]\n'
            '[0.08, "o", "e"]\n'
            '[0.06, "o", "a"]\n'
            '[0.07, "o", "t"]\n'
            '[0.06, "o", " "]\n'
            '[0.08, "o", "D"]\n'
            '[0.06, "o", "o"]\n'
            '[0.07, "o", "c"]\n'
            '[0.06, "o", "s"]\n'
            '[0.08, "o", "\\""]\n'
            '[0.5, "o", "\\r\\n"]\n'
            '[0.2, "o", "Hello from Great Docs\\r\\n"]\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[5.0, "o", ""]\n'
        ),
        "demos/ann-pos-right.termshow.yml": (
            "source: demos/ann-pos-right.termshow\n"
            "\n"
            "settings:\n"
            "  window_chrome: colorful\n"
            "\n"
            "annotations:\n"
            "  - at: 1.0\n"
            "    duration: 5.0\n"
            '    text: "Annotation at right"\n'
            "    position: right\n"
            "    style: callout\n"
        ),
        "demos/ann-pos-bottom-left.termshow": (
            '{"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 20, "type": "xterm-256color"}, "title": "Annotation Position Demo"}\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[0.08, "o", "e"]\n'
            '[0.06, "o", "c"]\n'
            '[0.07, "o", "h"]\n'
            '[0.06, "o", "o"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "\\""]\n'
            '[0.06, "o", "H"]\n'
            '[0.07, "o", "e"]\n'
            '[0.06, "o", "l"]\n'
            '[0.08, "o", "l"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", " "]\n'
            '[0.06, "o", "f"]\n'
            '[0.07, "o", "r"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", "m"]\n'
            '[0.06, "o", " "]\n'
            '[0.07, "o", "G"]\n'
            '[0.06, "o", "r"]\n'
            '[0.08, "o", "e"]\n'
            '[0.06, "o", "a"]\n'
            '[0.07, "o", "t"]\n'
            '[0.06, "o", " "]\n'
            '[0.08, "o", "D"]\n'
            '[0.06, "o", "o"]\n'
            '[0.07, "o", "c"]\n'
            '[0.06, "o", "s"]\n'
            '[0.08, "o", "\\""]\n'
            '[0.5, "o", "\\r\\n"]\n'
            '[0.2, "o", "Hello from Great Docs\\r\\n"]\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[5.0, "o", ""]\n'
        ),
        "demos/ann-pos-bottom-left.termshow.yml": (
            "source: demos/ann-pos-bottom-left.termshow\n"
            "\n"
            "settings:\n"
            "  window_chrome: colorful\n"
            "\n"
            "annotations:\n"
            "  - at: 1.0\n"
            "    duration: 5.0\n"
            '    text: "Annotation at bottom-left"\n'
            "    position: bottom-left\n"
            "    style: callout\n"
        ),
        "demos/ann-pos-bottom.termshow": (
            '{"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 20, "type": "xterm-256color"}, "title": "Annotation Position Demo"}\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[0.08, "o", "e"]\n'
            '[0.06, "o", "c"]\n'
            '[0.07, "o", "h"]\n'
            '[0.06, "o", "o"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "\\""]\n'
            '[0.06, "o", "H"]\n'
            '[0.07, "o", "e"]\n'
            '[0.06, "o", "l"]\n'
            '[0.08, "o", "l"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", " "]\n'
            '[0.06, "o", "f"]\n'
            '[0.07, "o", "r"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", "m"]\n'
            '[0.06, "o", " "]\n'
            '[0.07, "o", "G"]\n'
            '[0.06, "o", "r"]\n'
            '[0.08, "o", "e"]\n'
            '[0.06, "o", "a"]\n'
            '[0.07, "o", "t"]\n'
            '[0.06, "o", " "]\n'
            '[0.08, "o", "D"]\n'
            '[0.06, "o", "o"]\n'
            '[0.07, "o", "c"]\n'
            '[0.06, "o", "s"]\n'
            '[0.08, "o", "\\""]\n'
            '[0.5, "o", "\\r\\n"]\n'
            '[0.2, "o", "Hello from Great Docs\\r\\n"]\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[5.0, "o", ""]\n'
        ),
        "demos/ann-pos-bottom.termshow.yml": (
            "source: demos/ann-pos-bottom.termshow\n"
            "\n"
            "settings:\n"
            "  window_chrome: colorful\n"
            "\n"
            "annotations:\n"
            "  - at: 1.0\n"
            "    duration: 5.0\n"
            '    text: "Annotation at bottom"\n'
            "    position: bottom\n"
            "    style: callout\n"
        ),
        "demos/ann-pos-bottom-right.termshow": (
            '{"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 20, "type": "xterm-256color"}, "title": "Annotation Position Demo"}\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[0.08, "o", "e"]\n'
            '[0.06, "o", "c"]\n'
            '[0.07, "o", "h"]\n'
            '[0.06, "o", "o"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "\\""]\n'
            '[0.06, "o", "H"]\n'
            '[0.07, "o", "e"]\n'
            '[0.06, "o", "l"]\n'
            '[0.08, "o", "l"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", " "]\n'
            '[0.06, "o", "f"]\n'
            '[0.07, "o", "r"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", "m"]\n'
            '[0.06, "o", " "]\n'
            '[0.07, "o", "G"]\n'
            '[0.06, "o", "r"]\n'
            '[0.08, "o", "e"]\n'
            '[0.06, "o", "a"]\n'
            '[0.07, "o", "t"]\n'
            '[0.06, "o", " "]\n'
            '[0.08, "o", "D"]\n'
            '[0.06, "o", "o"]\n'
            '[0.07, "o", "c"]\n'
            '[0.06, "o", "s"]\n'
            '[0.08, "o", "\\""]\n'
            '[0.5, "o", "\\r\\n"]\n'
            '[0.2, "o", "Hello from Great Docs\\r\\n"]\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[5.0, "o", ""]\n'
        ),
        "demos/ann-pos-bottom-right.termshow.yml": (
            "source: demos/ann-pos-bottom-right.termshow\n"
            "\n"
            "settings:\n"
            "  window_chrome: colorful\n"
            "\n"
            "annotations:\n"
            "  - at: 1.0\n"
            "    duration: 5.0\n"
            '    text: "Annotation at bottom-right"\n'
            "    position: bottom-right\n"
            "    style: callout\n"
        ),
        # --- Width demos (all at top-right) ---
        "demos/ann-width-small.termshow": (
            '{"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 20, "type": "xterm-256color"}, "title": "Annotation Width Demo"}\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[0.08, "o", "e"]\n'
            '[0.06, "o", "c"]\n'
            '[0.07, "o", "h"]\n'
            '[0.06, "o", "o"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "\\""]\n'
            '[0.06, "o", "H"]\n'
            '[0.07, "o", "e"]\n'
            '[0.06, "o", "l"]\n'
            '[0.08, "o", "l"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", " "]\n'
            '[0.06, "o", "f"]\n'
            '[0.07, "o", "r"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", "m"]\n'
            '[0.06, "o", " "]\n'
            '[0.07, "o", "G"]\n'
            '[0.06, "o", "r"]\n'
            '[0.08, "o", "e"]\n'
            '[0.06, "o", "a"]\n'
            '[0.07, "o", "t"]\n'
            '[0.06, "o", " "]\n'
            '[0.08, "o", "D"]\n'
            '[0.06, "o", "o"]\n'
            '[0.07, "o", "c"]\n'
            '[0.06, "o", "s"]\n'
            '[0.08, "o", "\\""]\n'
            '[0.5, "o", "\\r\\n"]\n'
            '[0.2, "o", "Hello from Great Docs\\r\\n"]\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[5.0, "o", ""]\n'
        ),
        "demos/ann-width-small.termshow.yml": (
            "source: demos/ann-width-small.termshow\n"
            "\n"
            "settings:\n"
            "  window_chrome: colorful\n"
            "\n"
            "annotations:\n"
            "  - at: 1.0\n"
            "    duration: 5.0\n"
            '    text: "Small"\n'
            "    position: top-right\n"
            "    style: callout\n"
            "    width: small\n"
        ),
        "demos/ann-width-medium.termshow": (
            '{"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 20, "type": "xterm-256color"}, "title": "Annotation Width Demo"}\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[0.08, "o", "e"]\n'
            '[0.06, "o", "c"]\n'
            '[0.07, "o", "h"]\n'
            '[0.06, "o", "o"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "\\""]\n'
            '[0.06, "o", "H"]\n'
            '[0.07, "o", "e"]\n'
            '[0.06, "o", "l"]\n'
            '[0.08, "o", "l"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", " "]\n'
            '[0.06, "o", "f"]\n'
            '[0.07, "o", "r"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", "m"]\n'
            '[0.06, "o", " "]\n'
            '[0.07, "o", "G"]\n'
            '[0.06, "o", "r"]\n'
            '[0.08, "o", "e"]\n'
            '[0.06, "o", "a"]\n'
            '[0.07, "o", "t"]\n'
            '[0.06, "o", " "]\n'
            '[0.08, "o", "D"]\n'
            '[0.06, "o", "o"]\n'
            '[0.07, "o", "c"]\n'
            '[0.06, "o", "s"]\n'
            '[0.08, "o", "\\""]\n'
            '[0.5, "o", "\\r\\n"]\n'
            '[0.2, "o", "Hello from Great Docs\\r\\n"]\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[5.0, "o", ""]\n'
        ),
        "demos/ann-width-medium.termshow.yml": (
            "source: demos/ann-width-medium.termshow\n"
            "\n"
            "settings:\n"
            "  window_chrome: colorful\n"
            "\n"
            "annotations:\n"
            "  - at: 1.0\n"
            "    duration: 5.0\n"
            '    text: "Medium width annotation with more text content"\n'
            "    position: top-right\n"
            "    style: callout\n"
            "    width: medium\n"
        ),
        "demos/ann-width-large.termshow": (
            '{"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 20, "type": "xterm-256color"}, "title": "Annotation Width Demo"}\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[0.08, "o", "e"]\n'
            '[0.06, "o", "c"]\n'
            '[0.07, "o", "h"]\n'
            '[0.06, "o", "o"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "\\""]\n'
            '[0.06, "o", "H"]\n'
            '[0.07, "o", "e"]\n'
            '[0.06, "o", "l"]\n'
            '[0.08, "o", "l"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", " "]\n'
            '[0.06, "o", "f"]\n'
            '[0.07, "o", "r"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", "m"]\n'
            '[0.06, "o", " "]\n'
            '[0.07, "o", "G"]\n'
            '[0.06, "o", "r"]\n'
            '[0.08, "o", "e"]\n'
            '[0.06, "o", "a"]\n'
            '[0.07, "o", "t"]\n'
            '[0.06, "o", " "]\n'
            '[0.08, "o", "D"]\n'
            '[0.06, "o", "o"]\n'
            '[0.07, "o", "c"]\n'
            '[0.06, "o", "s"]\n'
            '[0.08, "o", "\\""]\n'
            '[0.5, "o", "\\r\\n"]\n'
            '[0.2, "o", "Hello from Great Docs\\r\\n"]\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[5.0, "o", ""]\n'
        ),
        "demos/ann-width-large.termshow.yml": (
            "source: demos/ann-width-large.termshow\n"
            "\n"
            "settings:\n"
            "  window_chrome: colorful\n"
            "\n"
            "annotations:\n"
            "  - at: 1.0\n"
            "    duration: 5.0\n"
            '    text: "Large width annotation that takes up more horizontal space for longer explanations"\n'
            "    position: top-right\n"
            "    style: callout\n"
            "    width: large\n"
        ),
        # ── Highlight style gallery recordings ────────────────────────
        #
        # A compact base recording used for all highlight style demos.
        # Shows a command with colored output so highlights are clearly
        # visible against terminal content.
        #
        # --- Style: outline ---
        "demos/hl-style-outline.termshow": (
            '{"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 12, "type": "xterm-256color"}, "title": "Highlight: Outline"}\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[0.08, "o", "g"]\n'
            '[0.06, "o", "r"]\n'
            '[0.07, "o", "e"]\n'
            '[0.06, "o", "a"]\n'
            '[0.08, "o", "t"]\n'
            '[0.06, "o", "-"]\n'
            '[0.07, "o", "d"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", "c"]\n'
            '[0.06, "o", "s"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "s"]\n'
            '[0.06, "o", "c"]\n'
            '[0.07, "o", "a"]\n'
            '[0.06, "o", "n"]\n'
            '[0.5, "o", "\\r\\n"]\n'
            '[0.3, "o", "\\u001b[36mScanning project...\\u001b[0m\\r\\n"]\n'
            '[0.4, "o", "\\u001b[32m\\u2713\\u001b[0m Found 4 modules\\r\\n"]\n'
            '[0.3, "o", "\\u001b[32m\\u2713\\u001b[0m Found 12 functions\\r\\n"]\n'
            '[0.3, "o", "\\u001b[32m\\u2713\\u001b[0m Found 3 classes\\r\\n"]\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[5.0, "o", ""]\n'
        ),
        "demos/hl-style-outline.termshow.yml": (
            "source: demos/hl-style-outline.termshow\n"
            "\n"
            "settings:\n"
            "  window_chrome: colorful\n"
            "\n"
            "highlights:\n"
            "  - at: 1.5\n"
            "    duration: 5.0\n"
            "    style: outline\n"
            "    target:\n"
            "      region: {row: 2, col: 2, width: 15, height: 1}\n"
        ),
        # --- Style: underline ---
        "demos/hl-style-underline.termshow": (
            '{"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 12, "type": "xterm-256color"}, "title": "Highlight: Underline"}\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[0.08, "o", "g"]\n'
            '[0.06, "o", "r"]\n'
            '[0.07, "o", "e"]\n'
            '[0.06, "o", "a"]\n'
            '[0.08, "o", "t"]\n'
            '[0.06, "o", "-"]\n'
            '[0.07, "o", "d"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", "c"]\n'
            '[0.06, "o", "s"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "l"]\n'
            '[0.06, "o", "i"]\n'
            '[0.07, "o", "n"]\n'
            '[0.06, "o", "t"]\n'
            '[0.5, "o", "\\r\\n"]\n'
            '[0.3, "o", "\\u001b[36mLinting sources...\\u001b[0m\\r\\n"]\n'
            '[0.4, "o", "\\u001b[33m\\u26a0\\u001b[0m  src/core.py:42 — unused import\\r\\n"]\n'
            '[0.3, "o", "\\u001b[33m\\u26a0\\u001b[0m  src/utils.py:8 — line too long\\r\\n"]\n'
            '[0.3, "o", "\\u001b[32m\\u2713\\u001b[0m 2 warnings, 0 errors\\r\\n"]\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[5.0, "o", ""]\n'
        ),
        "demos/hl-style-underline.termshow.yml": (
            "source: demos/hl-style-underline.termshow\n"
            "\n"
            "settings:\n"
            "  window_chrome: colorful\n"
            "\n"
            "highlights:\n"
            "  - at: 1.5\n"
            "    duration: 5.0\n"
            "    style: underline\n"
            "    color: '#f9e2af'\n"
            "    target:\n"
            "      region: {row: 2, col: 3, width: 30, height: 1}\n"
        ),
        # --- Style: underline-wavy ---
        "demos/hl-style-underline-wavy.termshow": (
            '{"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 12, "type": "xterm-256color"}, "title": "Highlight: Underline Wavy"}\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[0.08, "o", "p"]\n'
            '[0.06, "o", "y"]\n'
            '[0.07, "o", "t"]\n'
            '[0.06, "o", "h"]\n'
            '[0.08, "o", "o"]\n'
            '[0.06, "o", "n"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "a"]\n'
            '[0.06, "o", "p"]\n'
            '[0.07, "o", "p"]\n'
            '[0.06, "o", "."]\n'
            '[0.08, "o", "p"]\n'
            '[0.06, "o", "y"]\n'
            '[0.5, "o", "\\r\\n"]\n'
            '[0.3, "o", "Traceback (most recent call last):\\r\\n"]\n'
            '[0.2, "o", "  File \\"app.py\\", line 7, in <module>\\r\\n"]\n'
            '[0.2, "o", "    result = compute(data)\\r\\n"]\n'
            '[0.2, "o", "\\u001b[31mTypeError: unsupported operand type(s)\\u001b[0m\\r\\n"]\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[5.0, "o", ""]\n'
        ),
        "demos/hl-style-underline-wavy.termshow.yml": (
            "source: demos/hl-style-underline-wavy.termshow\n"
            "\n"
            "settings:\n"
            "  window_chrome: colorful\n"
            "\n"
            "highlights:\n"
            "  - at: 1.5\n"
            "    duration: 5.0\n"
            "    style: underline-wavy\n"
            "    color: '#f38ba8'\n"
            "    target:\n"
            "      region: {row: 4, col: 0, width: 38, height: 1}\n"
        ),
        # --- Style: background ---
        "demos/hl-style-background.termshow": (
            '{"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 12, "type": "xterm-256color"}, "title": "Highlight: Background"}\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[0.08, "o", "c"]\n'
            '[0.06, "o", "a"]\n'
            '[0.07, "o", "t"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "c"]\n'
            '[0.06, "o", "o"]\n'
            '[0.07, "o", "n"]\n'
            '[0.06, "o", "f"]\n'
            '[0.08, "o", "i"]\n'
            '[0.06, "o", "g"]\n'
            '[0.07, "o", "."]\n'
            '[0.06, "o", "t"]\n'
            '[0.08, "o", "o"]\n'
            '[0.06, "o", "m"]\n'
            '[0.07, "o", "l"]\n'
            '[0.5, "o", "\\r\\n"]\n'
            '[0.2, "o", "\\u001b[36m[project]\\u001b[0m\\r\\n"]\n'
            '[0.2, "o", "name = \\"my-tool\\"\\r\\n"]\n'
            '[0.2, "o", "version = \\"2.1.0\\"\\r\\n"]\n'
            '[0.2, "o", "description = \\"A fast CLI utility\\"\\r\\n"]\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[5.0, "o", ""]\n'
        ),
        "demos/hl-style-background.termshow.yml": (
            "source: demos/hl-style-background.termshow\n"
            "\n"
            "settings:\n"
            "  window_chrome: colorful\n"
            "\n"
            "highlights:\n"
            "  - at: 1.5\n"
            "    duration: 5.0\n"
            "    style: background\n"
            "    color: '#89b4fa'\n"
            "    target:\n"
            "      region: {row: 3, col: 0, width: 17, height: 1}\n"
        ),
        # --- Style: spotlight ---
        "demos/hl-style-spotlight.termshow": (
            '{"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 12, "type": "xterm-256color"}, "title": "Highlight: Spotlight"}\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[0.08, "o", "g"]\n'
            '[0.06, "o", "r"]\n'
            '[0.07, "o", "e"]\n'
            '[0.06, "o", "a"]\n'
            '[0.08, "o", "t"]\n'
            '[0.06, "o", "-"]\n'
            '[0.07, "o", "d"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", "c"]\n'
            '[0.06, "o", "s"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "b"]\n'
            '[0.06, "o", "u"]\n'
            '[0.07, "o", "i"]\n'
            '[0.06, "o", "l"]\n'
            '[0.08, "o", "d"]\n'
            '[0.5, "o", "\\r\\n"]\n'
            '[0.3, "o", "\\u001b[36mBuilding documentation...\\u001b[0m\\r\\n"]\n'
            '[0.5, "o", "\\u001b[32m\\u2713\\u001b[0m Rendered 24 pages\\r\\n"]\n'
            '[0.3, "o", "\\u001b[32m\\u2713\\u001b[0m Generated search index\\r\\n"]\n'
            '[0.3, "o", "\\u001b[1m\\u001b[32m\\u2728 Build complete!\\u001b[0m Output: _site/\\r\\n"]\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[5.0, "o", ""]\n'
        ),
        "demos/hl-style-spotlight.termshow.yml": (
            "source: demos/hl-style-spotlight.termshow\n"
            "\n"
            "settings:\n"
            "  window_chrome: colorful\n"
            "\n"
            "highlights:\n"
            "  - at: 1.5\n"
            "    duration: 5.0\n"
            "    style: spotlight\n"
            "    color: '#a6e3a1'\n"
            "    target:\n"
            "      region: {row: 4, col: 0, width: 32, height: 1}\n"
        ),
        # --- Style: glow ---
        "demos/hl-style-glow.termshow": (
            '{"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 12, "type": "xterm-256color"}, "title": "Highlight: Glow"}\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[0.08, "o", "g"]\n'
            '[0.06, "o", "r"]\n'
            '[0.07, "o", "e"]\n'
            '[0.06, "o", "a"]\n'
            '[0.08, "o", "t"]\n'
            '[0.06, "o", "-"]\n'
            '[0.07, "o", "d"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", "c"]\n'
            '[0.06, "o", "s"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "v"]\n'
            '[0.06, "o", "e"]\n'
            '[0.07, "o", "r"]\n'
            '[0.06, "o", "s"]\n'
            '[0.08, "o", "i"]\n'
            '[0.06, "o", "o"]\n'
            '[0.07, "o", "n"]\n'
            '[0.5, "o", "\\r\\n"]\n'
            '[0.3, "o", "great-docs \\u001b[1mv0.9.0\\u001b[0m\\r\\n"]\n'
            '[0.2, "o", "Python 3.12.4\\r\\n"]\n'
            '[0.2, "o", "Platform: macOS-14.5-arm64\\r\\n"]\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[5.0, "o", ""]\n'
        ),
        "demos/hl-style-glow.termshow.yml": (
            "source: demos/hl-style-glow.termshow\n"
            "\n"
            "settings:\n"
            "  window_chrome: colorful\n"
            "\n"
            "highlights:\n"
            "  - at: 1.5\n"
            "    duration: 5.0\n"
            "    style: glow\n"
            "    color: '#cba6f7'\n"
            "    target:\n"
            "      region: {row: 1, col: 11, width: 6, height: 1}\n"
            "    pulse: true\n"
        ),
        # --- Style: box ---
        "demos/hl-style-box.termshow": (
            '{"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 12, "type": "xterm-256color"}, "title": "Highlight: Box"}\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[0.08, "o", "p"]\n'
            '[0.06, "o", "y"]\n'
            '[0.07, "o", "t"]\n'
            '[0.06, "o", "e"]\n'
            '[0.08, "o", "s"]\n'
            '[0.06, "o", "t"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "-"]\n'
            '[0.06, "o", "-"]\n'
            '[0.07, "o", "c"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", "v"]\n'
            '[0.5, "o", "\\r\\n"]\n'
            '[0.3, "o", "\\u001b[36mRunning tests with coverage...\\u001b[0m\\r\\n"]\n'
            '[0.5, "o", "\\u001b[32m\\u2713\\u001b[0m 48 passed\\r\\n"]\n'
            '[0.3, "o", "\\u001b[32m\\u2713\\u001b[0m Coverage: \\u001b[1m94%\\u001b[0m\\r\\n"]\n'
            '[0.3, "o", "\\u001b[33m\\u26a0\\u001b[0m  Uncovered: utils.py:102-108\\r\\n"]\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[5.0, "o", ""]\n'
        ),
        "demos/hl-style-box.termshow.yml": (
            "source: demos/hl-style-box.termshow\n"
            "\n"
            "settings:\n"
            "  window_chrome: colorful\n"
            "\n"
            "highlights:\n"
            "  - at: 1.5\n"
            "    duration: 5.0\n"
            "    style: box\n"
            "    color: '#a6e3a1'\n"
            "    target:\n"
            "      region: {row: 2, col: 0, width: 20, height: 2}\n"
        ),
        # --- Style: badge-before ---
        "demos/hl-style-badge-before.termshow": (
            '{"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 12, "type": "xterm-256color"}, "title": "Highlight: Badge Before"}\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[0.08, "o", "g"]\n'
            '[0.06, "o", "r"]\n'
            '[0.07, "o", "e"]\n'
            '[0.06, "o", "a"]\n'
            '[0.08, "o", "t"]\n'
            '[0.06, "o", "-"]\n'
            '[0.07, "o", "d"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", "c"]\n'
            '[0.06, "o", "s"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "d"]\n'
            '[0.06, "o", "e"]\n'
            '[0.07, "o", "p"]\n'
            '[0.06, "o", "l"]\n'
            '[0.08, "o", "o"]\n'
            '[0.06, "o", "y"]\n'
            '[0.5, "o", "\\r\\n"]\n'
            '[0.3, "o", "\\u001b[36mDeploying to production...\\u001b[0m\\r\\n"]\n'
            '[0.5, "o", "\\u001b[32m\\u2713\\u001b[0m Uploaded 24 files\\r\\n"]\n'
            '[0.3, "o", "\\u001b[32m\\u2713\\u001b[0m CDN cache invalidated\\r\\n"]\n'
            '[0.3, "o", "\\u001b[1m\\u001b[32m\\u2728 Live at https://docs.example.com\\u001b[0m\\r\\n"]\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[5.0, "o", ""]\n'
        ),
        "demos/hl-style-badge-before.termshow.yml": (
            "source: demos/hl-style-badge-before.termshow\n"
            "\n"
            "settings:\n"
            "  window_chrome: colorful\n"
            "\n"
            "highlights:\n"
            "  - at: 1.5\n"
            "    duration: 5.0\n"
            "    style: badge-before\n"
            "    color: '#89b4fa'\n"
            '    badge_text: "NEW"\n'
            "    target:\n"
            "      region: {row: 4, col: 0, width: 34, height: 1}\n"
        ),
        # --- Style: badge-after ---
        "demos/hl-style-badge-after.termshow": (
            '{"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 12, "type": "xterm-256color"}, "title": "Highlight: Badge After"}\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[0.08, "o", "g"]\n'
            '[0.06, "o", "r"]\n'
            '[0.07, "o", "e"]\n'
            '[0.06, "o", "a"]\n'
            '[0.08, "o", "t"]\n'
            '[0.06, "o", "-"]\n'
            '[0.07, "o", "d"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", "c"]\n'
            '[0.06, "o", "s"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "d"]\n'
            '[0.06, "o", "i"]\n'
            '[0.07, "o", "f"]\n'
            '[0.06, "o", "f"]\n'
            '[0.5, "o", "\\r\\n"]\n'
            '[0.3, "o", "\\u001b[36mComparing v0.8 \\u2192 v0.9...\\u001b[0m\\r\\n"]\n'
            '[0.4, "o", "\\u001b[32m+ greet()\\u001b[0m  — new function\\r\\n"]\n'
            '[0.3, "o", "\\u001b[33m~ init_project()\\u001b[0m  — signature changed\\r\\n"]\n'
            '[0.3, "o", "\\u001b[31m- old_helper()\\u001b[0m  — removed\\r\\n"]\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[5.0, "o", ""]\n'
        ),
        "demos/hl-style-badge-after.termshow.yml": (
            "source: demos/hl-style-badge-after.termshow\n"
            "\n"
            "settings:\n"
            "  window_chrome: colorful\n"
            "\n"
            "highlights:\n"
            "  - at: 1.5\n"
            "    duration: 5.0\n"
            "    style: badge-after\n"
            "    color: '#f38ba8'\n"
            '    badge_text: "BREAKING"\n'
            "    target:\n"
            "      region: {row: 3, col: 0, width: 37, height: 1}\n"
        ),
        # --- Style: bracket ---
        "demos/hl-style-bracket.termshow": (
            '{"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 12, "type": "xterm-256color"}, "title": "Highlight: Bracket"}\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[0.08, "o", "g"]\n'
            '[0.06, "o", "r"]\n'
            '[0.07, "o", "e"]\n'
            '[0.06, "o", "a"]\n'
            '[0.08, "o", "t"]\n'
            '[0.06, "o", "-"]\n'
            '[0.07, "o", "d"]\n'
            '[0.06, "o", "o"]\n'
            '[0.08, "o", "c"]\n'
            '[0.06, "o", "s"]\n'
            '[0.1, "o", " "]\n'
            '[0.07, "o", "s"]\n'
            '[0.06, "o", "t"]\n'
            '[0.07, "o", "a"]\n'
            '[0.06, "o", "t"]\n'
            '[0.08, "o", "s"]\n'
            '[0.5, "o", "\\r\\n"]\n'
            '[0.3, "o", "\\u001b[36m\\u2500\\u2500 Build Summary \\u2500\\u2500\\u001b[0m\\r\\n"]\n'
            '[0.3, "o", "  Pages rendered:  24\\r\\n"]\n'
            '[0.3, "o", "  Assets copied:   18\\r\\n"]\n'
            '[0.3, "o", "  Total time:      1.3s\\r\\n"]\n'
            '[0.3, "o", "  Output size:     2.4 MB\\r\\n"]\n'
            '[0.5, "o", "\\u001b[32m\\u001b[1m$\\u001b[0m "]\n'
            '[5.0, "o", ""]\n'
        ),
        "demos/hl-style-bracket.termshow.yml": (
            "source: demos/hl-style-bracket.termshow\n"
            "\n"
            "settings:\n"
            "  window_chrome: colorful\n"
            "\n"
            "highlights:\n"
            "  - at: 1.5\n"
            "    duration: 5.0\n"
            "    style: bracket\n"
            "    color: '#f9e2af'\n"
            "    target:\n"
            "      region: {row: 2, col: 0, width: 30, height: 4}\n"
        ),
        # ── Highlight gallery page ───────────────────────────────────
        "user_guide/06-highlight-gallery.qmd": (
            "---\n"
            "title: Highlight Gallery\n"
            "---\n"
            "\n"
            "## Highlight Styles\n"
            "\n"
            "Highlights draw attention to specific regions of the terminal\n"
            "during playback. Each style creates a different visual effect.\n"
            "All examples below target a cell region and auto-play with loop.\n"
            "\n"
            "### Style: Outline\n"
            "\n"
            "A simple 2px border around the target region.\n"
            "Highlighted text: `Found 4 modules`\n"
            "\n"
            '{{< termshow file="demos/hl-style-outline" autoplay="true" loop="true" >}}\n'
            "\n"
            "### Style: Underline\n"
            "\n"
            "A solid line beneath the target — useful for drawing attention\n"
            "to specific text without obscuring it.\n"
            "Highlighted text: `src/core.py:42 — unused import`\n"
            "\n"
            '{{< termshow file="demos/hl-style-underline" autoplay="true" loop="true" >}}\n'
            "\n"
            "### Style: Underline (Wavy)\n"
            "\n"
            "A wavy underline, similar to spell-check or error indicators\n"
            "in code editors. Great for highlighting errors.\n"
            "Highlighted text: `TypeError: unsupported operand type(s)`\n"
            "\n"
            '{{< termshow file="demos/hl-style-underline-wavy" autoplay="true" loop="true" >}}\n'
            "\n"
            "### Style: Background\n"
            "\n"
            "A subtle translucent background fill behind the target region.\n"
            'Highlighted text: `version = "2.1.0"`\n'
            "\n"
            '{{< termshow file="demos/hl-style-background" autoplay="true" loop="true" >}}\n'
            "\n"
            "### Style: Spotlight\n"
            "\n"
            "Background fill with an outer glow, making the target\n"
            '"pop" against the surrounding content.\n'
            "Highlighted text: `\u2728 Build complete! Output: _site/`\n"
            "\n"
            '{{< termshow file="demos/hl-style-spotlight" autoplay="true" loop="true" >}}\n'
            "\n"
            "### Style: Glow\n"
            "\n"
            "An animated neon-style glow around the target. This example\n"
            "also uses `pulse: true` for a breathing effect.\n"
            "Highlighted text: `v0.9.0`\n"
            "\n"
            '{{< termshow file="demos/hl-style-glow" autoplay="true" loop="true" >}}\n'
            "\n"
            "### Style: Box\n"
            "\n"
            "Combines a border with a translucent fill — the classic\n"
            '"selection rectangle" look.\n'
            "Highlighted text: `✓ 48 passed` and `✓ Coverage: 94%`\n"
            "\n"
            '{{< termshow file="demos/hl-style-box" autoplay="true" loop="true" >}}\n'
            "\n"
            "### Style: Badge (Before)\n"
            "\n"
            "Border with a labeled badge above the target region.\n"
            "Use `badge_text` to set the label.\n"
            "Highlighted text: `\u2728 Live at https://docs.example.com`\n"
            "\n"
            '{{< termshow file="demos/hl-style-badge-before" autoplay="true" loop="true" >}}\n'
            "\n"
            "### Style: Badge (After)\n"
            "\n"
            "Border with a labeled badge below the target region.\n"
            "Highlighted text: `~ init_project() \u2014 signature changed`\n"
            "\n"
            '{{< termshow file="demos/hl-style-badge-after" autoplay="true" loop="true" >}}\n'
            "\n"
            "### Style: Bracket\n"
            "\n"
            "A left-edge bracket marking a multi-line block of output.\n"
            "Great for grouping related lines.\n"
            "Highlighted text: the four build summary statistics lines\n"
            "\n"
            '{{< termshow file="demos/hl-style-bracket" autoplay="true" loop="true" >}}\n'
            "\n"
            "## YAML Example\n"
            "\n"
            "```yaml\n"
            "highlights:\n"
            "  - at: 2.0\n"
            "    duration: 3.0\n"
            "    style: glow\n"
            "    color: '#cba6f7'\n"
            "    pulse: true\n"
            "    target:\n"
            "      region: {row: 1, col: 11, width: 6, height: 1}\n"
            "```\n"
            "\n"
            "## Available Styles\n"
            "\n"
            "| Style | Effect |\n"
            "|-------|--------|\n"
            "| `outline` | 2px colored border |\n"
            "| `underline` | Solid line beneath target |\n"
            "| `underline-wavy` | Wavy line beneath target |\n"
            "| `background` | Translucent fill |\n"
            "| `spotlight` | Fill + outer glow |\n"
            "| `glow` | Neon glow (inner + outer shadow) |\n"
            "| `box` | Border + translucent fill |\n"
            "| `badge-before` | Border + label above |\n"
            "| `badge-after` | Border + label below |\n"
            "| `bracket` | Left-edge bracket |\n"
            "\n"
            "## Targeting Modes\n"
            "\n"
            "Highlights support three targeting modes:\n"
            "\n"
            "- **Region** — explicit cell coordinates (`row`, `col`, `width`, `height`)\n"
            "- **Pattern** — regex match against the terminal buffer (`match`, `group`)\n"
            "- **Lines** — list of line numbers to highlight\n"
            "\n"
            "## Animation Options\n"
            "\n"
            "| Option | Default | Description |\n"
            "|--------|---------|-------------|\n"
            "| `fade_in` | 0.3 | Seconds to fade in |\n"
            "| `fade_out` | 0.3 | Seconds to fade out |\n"
            "| `pulse` | false | Breathing animation |\n"
            "| `color` | `#f1fa8c` | Hex color for the highlight |\n"
        ),
        # ── Annotation gallery page ──────────────────────────────────
        "user_guide/05-annotation-gallery.qmd": (
            "---\n"
            "title: Annotation Gallery\n"
            "---\n"
            "\n"
            "## Annotation Positions\n"
            "\n"
            "Annotations can be placed at any edge or corner of the terminal\n"
            "viewport. All examples below use the default `medium` width\n"
            "and `callout` style.\n"
            "\n"
            "### Position: Top-Left\n"
            "\n"
            '{{< termshow file="demos/ann-pos-top-left" autoplay="true" loop="true" >}}\n'
            "\n"
            "### Position: Top\n"
            "\n"
            '{{< termshow file="demos/ann-pos-top" autoplay="true" loop="true" >}}\n'
            "\n"
            "### Position: Top-Right\n"
            "\n"
            '{{< termshow file="demos/ann-pos-top-right" autoplay="true" loop="true" >}}\n'
            "\n"
            "### Position: Left\n"
            "\n"
            '{{< termshow file="demos/ann-pos-left" autoplay="true" loop="true" >}}\n'
            "\n"
            "### Position: Right\n"
            "\n"
            '{{< termshow file="demos/ann-pos-right" autoplay="true" loop="true" >}}\n'
            "\n"
            "### Position: Bottom-Left\n"
            "\n"
            '{{< termshow file="demos/ann-pos-bottom-left" autoplay="true" loop="true" >}}\n'
            "\n"
            "### Position: Bottom\n"
            "\n"
            '{{< termshow file="demos/ann-pos-bottom" autoplay="true" loop="true" >}}\n'
            "\n"
            "### Position: Bottom-Right\n"
            "\n"
            '{{< termshow file="demos/ann-pos-bottom-right" autoplay="true" loop="true" >}}\n'
            "\n"
            "## Annotation Widths\n"
            "\n"
            "The `width` field controls how wide an annotation can grow as\n"
            "a fraction of the player viewport. All examples below use\n"
            "`top-right` position and `callout` style.\n"
            "\n"
            "### Small (25%)\n"
            "\n"
            '{{< termshow file="demos/ann-width-small" autoplay="true" loop="true" >}}\n'
            "\n"
            "### Medium (50%) — Default\n"
            "\n"
            '{{< termshow file="demos/ann-width-medium" autoplay="true" loop="true" >}}\n'
            "\n"
            "### Large (75%)\n"
            "\n"
            '{{< termshow file="demos/ann-width-large" autoplay="true" loop="true" >}}\n'
            "\n"
            "## Choosing Settings\n"
            "\n"
            "| Goal | Recommended |\n"
            "|------|-------------|\n"
            "| Brief label next to code | `position: right`, `width: small` |\n"
            "| Step explanation avoiding left-aligned output | `position: top-right`, `width: medium` |\n"
            "| Long description with room to breathe | `position: top`, `width: large` |\n"
            "| Warning banner across the top | `position: top`, `width: large`, `style: highlight` |\n"
            "| Subtle aside | `position: bottom-right`, `width: small`, `style: subtle` |\n"
            "\n"
            "## YAML Example\n"
            "\n"
            "```yaml\n"
            "annotations:\n"
            "  - at: 2.0\n"
            "    duration: 3.0\n"
            "    text: This step installs all dependencies\n"
            "    position: top-right\n"
            "    style: callout\n"
            "    width: large\n"
            "```\n"
            "\n"
            "Available positions: `top-left`, `top`, `top-right`, `left`, `right`,\n"
            "`bottom-left`, `bottom`, `bottom-right`.\n"
            "\n"
            "Available widths: `small` (25%), `medium` (50%, default), `large` (75%).\n"
        ),
    },
    "config": {
        "package_name": "gdtest_termshow",
        "display_name": "My Tool",
        "description": "A demo showing terminal recordings in documentation",
        "user_guide": True,
    },
}
