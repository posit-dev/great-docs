"""
gdtest_go_cli — Minimal Go CLI project documentation.

Dimensions: Z1, F6, G1, H7
Focus: Go CLI detection (go.mod + cmd/hello layout), binary compilation,
       recursive --help extraction, and CLI reference page generation.
       No Python module; the site is driven entirely by the Go CLI.
"""

SPEC = {
    "name": "gdtest_go_cli",
    "description": "Go CLI project with cobra-style --help output",
    "dimensions": ["Z1", "F6", "G1", "H7"],
    # ── Project metadata ──────────────────────────────────────────────────────
    # No pyproject_toml: render_all.py will add a minimal one as a root barrier.
    # The real project identity comes from go.mod.
    # ── Source files ──────────────────────────────────────────────────────────
    "files": {
        "go.mod": """\
            module github.com/posit-dev/great-docs/testdata/gdtest_go_cli

            go 1.21
        """,
        "cmd/hello/main.go": """\
            package main

            import (
            \t"fmt"
            \t"os"
            \t"strings"
            )

            // Minimal CLI that emits cobra-style --help output so great-docs CLI
            // reference generation can be exercised without external Go dependencies.

            const rootHelp = `A minimal Go CLI for testing great-docs documentation.

            Usage:
              hello [command]

            Available Commands:
              greet       Print a personalised greeting
              version     Print the version

            Flags:
              --config string   config file (default: hello.toml)
              -h, --help        help for hello
              -v, --verbose     enable verbose output

            Use "hello [command] --help" for more information about a command.`

            const greetHelp = `Print a personalised greeting to standard output.

            Usage:
              hello greet [flags]

            Flags:
              -h, --help          help for greet
              -n, --name string   name to greet (default "World")

            Global Flags:
              --config string   config file (default: hello.toml)
              -v, --verbose     enable verbose output`

            const versionHelp = `Print the version string and exit.

            Usage:
              hello version [flags]

            Flags:
              -h, --help   help for version

            Global Flags:
              --config string   config file (default: hello.toml)
              -v, --verbose     enable verbose output`

            func main() {
            \targs := os.Args[1:]

            \tisHelp := func(a []string) bool {
            \t\tfor _, arg := range a {
            \t\t\tif arg == "--help" || arg == "-h" {
            \t\t\t\treturn true
            \t\t\t}
            \t\t}
            \t\treturn false
            \t}

            \tif len(args) == 0 || isHelp(args) {
            \t\tsub := ""
            \t\tfor _, a := range args {
            \t\t\tif !strings.HasPrefix(a, "-") {
            \t\t\t\tsub = a
            \t\t\t\tbreak
            \t\t\t}
            \t\t}
            \t\tswitch sub {
            \t\tcase "greet":
            \t\t\tfmt.Println(greetHelp)
            \t\tcase "version":
            \t\t\tfmt.Println(versionHelp)
            \t\tdefault:
            \t\t\tfmt.Println(rootHelp)
            \t\t}
            \t\treturn
            \t}

            \tswitch args[0] {
            \tcase "greet":
            \t\tname := "World"
            \t\tfor i, a := range args[1:] {
            \t\t\tif (a == "--name" || a == "-n") && i+2 < len(args) {
            \t\t\t\tname = args[i+2]
            \t\t\t}
            \t\t}
            \t\tfmt.Printf("Hello, %s!\\n", name)
            \tcase "version":
            \t\tfmt.Println("hello 0.1.0")
            \tdefault:
            \t\tfmt.Fprintf(os.Stderr, "unknown command: %s\\n", args[0])
            \t\tos.Exit(1)
            \t}
            }
        """,
        "README.md": """\
            # hello

            A minimal Go CLI for testing great-docs Go CLI documentation generation.

            ## Installation

            ```bash
            go install github.com/posit-dev/great-docs/testdata/gdtest_go_cli/cmd/hello@latest
            ```

            ## Usage

            ```bash
            hello greet --name World
            hello version
            ```
        """,
    },
    # ── great-docs config ─────────────────────────────────────────────────────
    # Providing config here means `great-docs init` is skipped; only `build` runs.
    "config": {
        "go_cli": {
            "enabled": True,
        },
    },
    # ── Expected outcomes ─────────────────────────────────────────────────────
    "expected": {
        # render_all.py writes a pyproject.toml root-barrier with the spec name,
        # so detected_name comes from that.
        "detected_name": "gdtest-go-cli",
        # No Python module — pure Go project.
        "detected_module": None,
        "has_user_guide": False,
        "has_license_page": False,
        "has_citation_page": False,
        "go_cli_enabled": True,
        # Coverage levels this package does NOT participate in (no Python API).
        "coverage_exclude": [
            "nodoc",
            "bigcl",
            "ug",
            "supp",
            "hdg",
            "ref",
            "sig",
            "desc",
            "param",
            "pmatch",
            "ret",
            "refidx",
            "sechdg",
        ],
    },
}
