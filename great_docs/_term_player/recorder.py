"""Terminal session recorder using PTY.

Records terminal output with timing information into the .termshow format.
"""

from __future__ import annotations

import json
import os
import select
import sys
import time
from pathlib import Path


def record_session(
    output_path: str | Path,
    *,
    shell: str | None = None,
    cols: int | None = None,
    rows: int | None = None,
    capture_input: bool = False,
) -> None:
    """Record a terminal session to a .termshow file.

    Opens a PTY, spawns the user's shell, and captures all output with
    millisecond timing.

    Parameters
    ----------
    output_path
        Path to write the .termshow file.
    shell
        Shell command to spawn (defaults to $SHELL or /bin/sh).
    cols
        Terminal width override (defaults to current terminal).
    rows
        Terminal height override (defaults to current terminal).
    capture_input
        Whether to capture keyboard input events (opt-in).
    """
    import fcntl
    import pty
    import struct
    import termios

    path = Path(output_path)

    # Detect terminal size
    if cols is None or rows is None:
        try:
            size = os.get_terminal_size()
            cols = cols or size.columns
            rows = rows or size.lines
        except OSError:
            cols = cols or 80
            rows = rows or 24

    # Detect shell
    if shell is None:
        shell = os.environ.get("SHELL", "/bin/sh")

    # Write header
    header = {
        "version": 1,
        "format": "termshow",
        "term": {
            "cols": cols,
            "rows": rows,
            "type": os.environ.get("TERM", "xterm-256color"),
        },
        "timestamp": int(time.time()),
        "title": path.stem,
    }

    events: list[str] = []
    events.append(json.dumps(header))

    # Fork PTY
    pid, master_fd = pty.fork()

    if pid == 0:
        # Child process: exec shell
        # Set terminal size
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(sys.stdout.fileno(), termios.TIOCSWINSZ, winsize)
        os.execvp(shell, [shell])
        # Should not reach here
        sys.exit(1)

    # Parent process: capture output
    # Set terminal size on master
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)

    # Put terminal in raw mode
    old_attrs = termios.tcgetattr(sys.stdin.fileno())
    try:
        _set_raw_mode(sys.stdin.fileno())

        start_time = time.monotonic()
        prev_time = start_time

        sys.stderr.write(
            f"\x1b[32mRecording...\x1b[0m (cols={cols}, rows={rows})\n"
            f"Press Ctrl+D or type 'exit' to stop.\n\n"
        )

        while True:
            try:
                readable, _, _ = select.select([master_fd, sys.stdin.fileno()], [], [], 0.1)
            except (OSError, ValueError):
                break

            for fd in readable:
                if fd == master_fd:
                    # Output from the shell
                    try:
                        data = os.read(master_fd, 65536)
                    except OSError:
                        data = b""

                    if not data:
                        # EOF from PTY
                        break

                    now = time.monotonic()
                    interval = round(now - prev_time, 3)
                    prev_time = now

                    # Write to real terminal
                    os.write(sys.stdout.fileno(), data)

                    # Record event
                    text = data.decode("utf-8", errors="replace")
                    event = json.dumps([interval, "o", text])
                    events.append(event)

                elif fd == sys.stdin.fileno():
                    # Input from user
                    try:
                        data = os.read(sys.stdin.fileno(), 65536)
                    except OSError:
                        data = b""

                    if not data:
                        break

                    # Forward to PTY
                    os.write(master_fd, data)

                    # Optionally record input
                    if capture_input:
                        now = time.monotonic()
                        interval = round(now - prev_time, 3)
                        prev_time = now
                        text = data.decode("utf-8", errors="replace")
                        event = json.dumps([interval, "i", text])
                        events.append(event)
            else:
                continue
            break

        # Wait for child to exit
        _, exit_status = os.waitpid(pid, 0)
        exit_code = os.WEXITSTATUS(exit_status) if os.WIFEXITED(exit_status) else 1

        # Record exit event
        now = time.monotonic()
        interval = round(now - prev_time, 3)
        events.append(json.dumps([interval, "x", str(exit_code)]))

    finally:
        # Restore terminal
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_attrs)
        try:
            os.close(master_fd)
        except OSError:
            pass

    # Strip recorder diagnostic messages from the event stream
    events = _strip_recorder_messages(events)

    # Write output file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(events) + "\n", encoding="utf-8")

    # Create companion .termshow.yml with commented template
    yml_path = Path(str(path) + ".yml")
    if not yml_path.exists():
        yml_content = f"""\
source: {path.name}

settings:
  idle_time_limit: 2.0
  # window_chrome: colorful
  # theme: monokai
  # font_size: 14

# chapters:
#   - at: 0.0
#     label: Start
#   - at: 5.0
#     label: Next Step

# annotations:
#   - at: 1.0
#     duration: 3.0
#     text: Explain what's happening here
#     position: top-right
#     style: callout

# cuts:
#   - from: 8.0
#     to: 11.0
#     type: ellipsis
"""
        yml_path.write_text(yml_content, encoding="utf-8")
        sys.stderr.write(f"  Script template: {yml_path}\n")

    duration = round(time.monotonic() - start_time, 1)
    event_count = len(events) - 1  # Exclude header
    sys.stderr.write(
        f"\n\x1b[32mRecording saved:\x1b[0m {path} ({duration}s, {event_count} events)\n"
    )


def _set_raw_mode(fd: int) -> None:
    """Set terminal to raw mode (no echo, no canonical processing)."""
    import termios
    import tty

    tty.setraw(fd, termios.TCSADRAIN)


