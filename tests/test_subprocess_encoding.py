"""Tests for UTF-8 subprocess text-mode decoding (issue #200 follow-up)."""

from __future__ import annotations

import subprocess
import sys

from great_docs._subprocess import TEXT_MODE_KWARGS


def test_text_mode_kwargs_decode_utf8_child_output():
    """Parent must read UTF-8 bytes from children without locale decode errors."""
    child_code = (
        "import sys; "
        "sys.stdout.buffer.write(bytes(["
        "0x0a, 0xf0, 0x9f, 0x94, 0x8d, 0x20, 0x53, 0x45, 0x4f, 0x0a"
        "])); "
        "sys.stdout.flush()"
    )

    proc = subprocess.Popen(
        [sys.executable, "-c", child_code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **TEXT_MODE_KWARGS,
    )
    assert proc.stdout is not None
    output = proc.stdout.read()
    proc.wait()
    assert "SEO" in output


def test_locale_codec_fails_on_utf8_child_output():
    """Reproduce the Windows cp1252 parent-decode failure from issue #200."""
    child_code = (
        "import sys; "
        "sys.stdout.buffer.write(bytes(["
        "0x0a, 0xf0, 0x9f, 0x94, 0x8d, 0x20, 0x53, 0x45, 0x4f, 0x0a"
        "])); "
        "sys.stdout.flush()"
    )

    proc = subprocess.Popen(
        [sys.executable, "-c", child_code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="cp1252",
        errors="strict",
    )
    assert proc.stdout is not None
    try:
        proc.stdout.read()
        raised = False
    except UnicodeDecodeError:
        raised = True
    finally:
        proc.wait()

    assert raised
