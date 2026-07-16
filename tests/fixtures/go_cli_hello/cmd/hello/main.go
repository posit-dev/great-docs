package main

import (
	"fmt"
	"os"
	"strings"
)

// Minimal CLI that emits cobra-style --help output so great-docs parsing
// helpers can be exercised without an external Go dependency.

const rootHelp = `A minimal CLI fixture for great-docs testing.

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
	args := os.Args[1:]

	isHelp := func(a []string) bool {
		for _, arg := range a {
			if arg == "--help" || arg == "-h" {
				return true
			}
		}
		return false
	}

	if len(args) == 0 || isHelp(args) {
		// Determine which subcommand's help to show
		sub := ""
		for _, a := range args {
			if !strings.HasPrefix(a, "-") {
				sub = a
				break
			}
		}
		switch sub {
		case "greet":
			fmt.Println(greetHelp)
		case "version":
			fmt.Println(versionHelp)
		default:
			fmt.Println(rootHelp)
		}
		return
	}

	switch args[0] {
	case "greet":
		name := "World"
		for i, a := range args[1:] {
			if (a == "--name" || a == "-n") && i+2 < len(args) {
				name = args[i+2]
			}
		}
		fmt.Printf("Hello, %s!\n", name)
	case "version":
		fmt.Println("hello 0.1.0")
	default:
		fmt.Fprintf(os.Stderr, "unknown command: %s\n", args[0])
		os.Exit(1)
	}
}
