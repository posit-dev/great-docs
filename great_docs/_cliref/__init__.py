"""
CLI discovery, extraction and reference pages

`click` discovers Click and Typer commands and extracts separate page and snapshot models. `go`
and `rust` detect Go and Rust command-line projects and extract their commands from `--help`
output. `model` defines the command tree that the Click, Go and Rust extractors share. `render`
writes the reference pages.
"""
