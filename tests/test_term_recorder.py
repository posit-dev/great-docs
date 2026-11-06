"""Tests for the _term_player.recorder module."""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from great_docs._term_player.recorder import (
    _is_recorder_message,
    _set_raw_mode,
    _strip_recorder_messages,
    record_session,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MASTER_FD = 4
_PID = 12345
_STDIN_FD = 0
_STDOUT_FD = 1
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _base_patches():
    """Return a list of context managers for the common OS-level mocks."""
    return [
        patch("pty.fork", return_value=(_PID, _MASTER_FD)),
        patch("fcntl.ioctl"),
        patch("termios.tcgetattr", return_value=[]),
        patch("termios.tcsetattr"),
        patch("os.get_terminal_size", side_effect=OSError("not a tty")),
        patch("os.waitpid", return_value=(_PID, 0)),
        patch("os.WIFEXITED", return_value=True),
        patch("os.WEXITSTATUS", return_value=0),
        patch("os.write"),
        patch("os.close"),
        patch("great_docs._term_player.recorder._set_raw_mode"),
        patch("sys.stdin"),
        patch("sys.stderr"),
    ]


# ---------------------------------------------------------------------------
# record_session — mocked PTY tests
# ---------------------------------------------------------------------------


class TestRecordSession:
    """Tests for record_session() with mocked PTY and OS calls."""

    def _run(self, tmp_path: Path, select_side_effect, read_side_effect=None, **kw):
        """Run record_session with the given mock sequences."""
        output_path = tmp_path / "test.termshow"

        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = _STDIN_FD
        mock_stdout = MagicMock()
        mock_stdout.fileno.return_value = _STDOUT_FD

        patches = _base_patches() + [
            patch("select.select", side_effect=select_side_effect),
        ]
        if read_side_effect is not None:
            patches.append(patch("os.read", side_effect=read_side_effect))
        else:
            patches.append(patch("os.read", return_value=b""))

        with patch("sys.stdin", mock_stdin), patch("sys.stdout", mock_stdout):
            ctx = {}
            for p in patches:
                p.start()
            try:
                record_session(output_path, **kw)
            finally:
                for p in reversed(patches):
                    p.stop()

        return output_path

    def test_pty_output_written_to_file(self, tmp_path: Path):
        """Output events from PTY are recorded in the .termshow file."""
        output_path = tmp_path / "session.termshow"
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = _STDIN_FD

        read_calls = iter([b"$ hello\r\n", b""])  # data then EOF
        select_calls = iter(
            [
                ([_MASTER_FD], [], []),  # first: master_fd readable
                ([_MASTER_FD], [], []),  # second: master_fd readable → EOF
            ]
        )

        with (
            patch("pty.fork", return_value=(_PID, _MASTER_FD)),
            patch("fcntl.ioctl"),
            patch("termios.tcgetattr", return_value=[]),
            patch("termios.tcsetattr"),
            patch("os.get_terminal_size", side_effect=OSError("not a tty")),
            patch("os.waitpid", return_value=(_PID, 0)),
            patch("os.WIFEXITED", return_value=True),
            patch("os.WEXITSTATUS", return_value=0),
            patch("os.write"),
            patch("os.close"),
            patch("os.read", side_effect=lambda fd, n: next(read_calls)),
            patch("select.select", side_effect=lambda *a, **k: next(select_calls)),
            patch("great_docs._term_player.recorder._set_raw_mode"),
            patch("sys.stdin", mock_stdin),
            patch("sys.stderr"),
        ):
            record_session(output_path)

        assert output_path.exists()
        lines = output_path.read_text().strip().splitlines()
        header = json.loads(lines[0])
        assert header["format"] == "termshow"
        assert header["term"]["cols"] == 80
        assert header["term"]["rows"] == 24
        # At least one "o" event
        events = [json.loads(line) for line in lines[1:] if line.strip()]
        o_events = [e for e in events if e[1] == "o"]
        assert len(o_events) >= 1

    def test_child_process_execs_the_shell_at_the_requested_size(self, tmp_path: Path):
        """Check that the child sets its terminal size and starts the requested shell"""
        import struct
        import termios

        mock_stdout = MagicMock()
        mock_stdout.fileno.return_value = _STDOUT_FD

        with (
            patch("pty.fork", return_value=(0, _MASTER_FD)),
            patch("fcntl.ioctl") as ioctl,
            patch("os.execvp") as execvp,
            patch("sys.stdout", mock_stdout),
            pytest.raises(SystemExit) as exit_info,
        ):
            record_session(tmp_path / "child.termshow", shell="/bin/fakesh", cols=30, rows=10)

        execvp.assert_called_once_with("/bin/fakesh", ["/bin/fakesh"])
        ioctl.assert_called_once_with(
            _STDOUT_FD, termios.TIOCSWINSZ, struct.pack("HHHH", 10, 30, 0, 0)
        )
        # The exec stub returns; the child must exit before the parent's recording loop.
        assert exit_info.value.code == 1

    def test_select_oserror_exits_loop(self, tmp_path: Path):
        """OSError from select breaks the loop; file is still written."""
        output_path = tmp_path / "session.termshow"
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = _STDIN_FD

        with (
            patch("pty.fork", return_value=(_PID, _MASTER_FD)),
            patch("fcntl.ioctl"),
            patch("termios.tcgetattr", return_value=[]),
            patch("termios.tcsetattr"),
            patch("os.get_terminal_size", side_effect=OSError),
            patch("os.waitpid", return_value=(_PID, 0)),
            patch("os.WIFEXITED", return_value=True),
            patch("os.WEXITSTATUS", return_value=0),
            patch("os.write"),
            patch("os.close"),
            patch("os.read", return_value=b""),
            patch("select.select", side_effect=OSError("broken")),
            patch("great_docs._term_player.recorder._set_raw_mode"),
            patch("sys.stdin", mock_stdin),
            patch("sys.stderr"),
        ):
            record_session(output_path)

        assert output_path.exists()

    def test_select_valueerror_exits_loop(self, tmp_path: Path):
        """ValueError from select also breaks the loop."""
        output_path = tmp_path / "session.termshow"
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = _STDIN_FD

        with (
            patch("pty.fork", return_value=(_PID, _MASTER_FD)),
            patch("fcntl.ioctl"),
            patch("termios.tcgetattr", return_value=[]),
            patch("termios.tcsetattr"),
            patch("os.get_terminal_size", side_effect=OSError),
            patch("os.waitpid", return_value=(_PID, 0)),
            patch("os.WIFEXITED", return_value=True),
            patch("os.WEXITSTATUS", return_value=0),
            patch("os.write"),
            patch("os.close"),
            patch("os.read", return_value=b""),
            patch("select.select", side_effect=ValueError("bad fd")),
            patch("great_docs._term_player.recorder._set_raw_mode"),
            patch("sys.stdin", mock_stdin),
            patch("sys.stderr"),
        ):
            record_session(output_path)

        assert output_path.exists()

    def test_os_read_oserror_treated_as_empty(self, tmp_path: Path):
        """OSError from os.read(master_fd) is caught; empty data breaks loop."""
        output_path = tmp_path / "session.termshow"
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = _STDIN_FD

        with (
            patch("pty.fork", return_value=(_PID, _MASTER_FD)),
            patch("fcntl.ioctl"),
            patch("termios.tcgetattr", return_value=[]),
            patch("termios.tcsetattr"),
            patch("os.get_terminal_size", side_effect=OSError),
            patch("os.waitpid", return_value=(_PID, 0)),
            patch("os.WIFEXITED", return_value=True),
            patch("os.WEXITSTATUS", return_value=0),
            patch("os.write"),
            patch("os.close"),
            patch("os.read", side_effect=OSError("pty gone")),
            patch("select.select", return_value=([_MASTER_FD], [], [])),
            patch("great_docs._term_player.recorder._set_raw_mode"),
            patch("sys.stdin", mock_stdin),
            patch("sys.stderr"),
        ):
            record_session(output_path)

        assert output_path.exists()

    def test_stdin_input_captured_when_flag_set(self, tmp_path: Path):
        """capture_input=True records stdin events in the file."""
        output_path = tmp_path / "session.termshow"
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = _STDIN_FD

        read_calls = iter([b"ls\n", b""])  # stdin input then EOF
        select_calls = iter(
            [
                ([_STDIN_FD], [], []),  # stdin readable
                ([_STDIN_FD], [], []),  # stdin EOF
            ]
        )

        with (
            patch("pty.fork", return_value=(_PID, _MASTER_FD)),
            patch("fcntl.ioctl"),
            patch("termios.tcgetattr", return_value=[]),
            patch("termios.tcsetattr"),
            patch("os.get_terminal_size", side_effect=OSError),
            patch("os.waitpid", return_value=(_PID, 0)),
            patch("os.WIFEXITED", return_value=True),
            patch("os.WEXITSTATUS", return_value=0),
            patch("os.write"),
            patch("os.close"),
            patch("os.read", side_effect=lambda fd, n: next(read_calls)),
            patch("select.select", side_effect=lambda *a, **k: next(select_calls)),
            patch("great_docs._term_player.recorder._set_raw_mode"),
            patch("sys.stdin", mock_stdin),
            patch("sys.stderr"),
        ):
            record_session(output_path, capture_input=True)

        lines = output_path.read_text().strip().splitlines()
        events = [json.loads(l) for l in lines[1:] if l.strip()]
        i_events = [e for e in events if e[1] == "i"]
        assert len(i_events) >= 1
        assert i_events[0][2] == "ls\n"

    def test_stdin_input_not_captured_by_default(self, tmp_path: Path):
        """Without capture_input, stdin events are forwarded but not recorded."""
        output_path = tmp_path / "session.termshow"
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = _STDIN_FD

        read_calls = iter([b"ls\n", b""])  # stdin data then EOF
        select_calls = iter(
            [
                ([_STDIN_FD], [], []),
                ([_STDIN_FD], [], []),
            ]
        )

        with (
            patch("pty.fork", return_value=(_PID, _MASTER_FD)),
            patch("fcntl.ioctl"),
            patch("termios.tcgetattr", return_value=[]),
            patch("termios.tcsetattr"),
            patch("os.get_terminal_size", side_effect=OSError),
            patch("os.waitpid", return_value=(_PID, 0)),
            patch("os.WIFEXITED", return_value=True),
            patch("os.WEXITSTATUS", return_value=0),
            patch("os.write"),
            patch("os.close"),
            patch("os.read", side_effect=lambda fd, n: next(read_calls)),
            patch("select.select", side_effect=lambda *a, **k: next(select_calls)),
            patch("great_docs._term_player.recorder._set_raw_mode"),
            patch("sys.stdin", mock_stdin),
            patch("sys.stderr"),
        ):
            record_session(output_path, capture_input=False)

        lines = output_path.read_text().strip().splitlines()
        events = [json.loads(l) for l in lines[1:] if l.strip()]
        i_events = [e for e in events if e[1] == "i"]
        assert len(i_events) == 0

    def test_nonzero_exit_recorded(self, tmp_path: Path):
        """Non-zero child exit is captured as an 'x' event with the exit code."""
        output_path = tmp_path / "session.termshow"
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = _STDIN_FD

        with (
            patch("pty.fork", return_value=(_PID, _MASTER_FD)),
            patch("fcntl.ioctl"),
            patch("termios.tcgetattr", return_value=[]),
            patch("termios.tcsetattr"),
            patch("os.get_terminal_size", side_effect=OSError),
            patch("os.waitpid", return_value=(_PID, 256)),  # exit_status=256 → code=1
            patch("os.WIFEXITED", return_value=True),
            patch("os.WEXITSTATUS", return_value=1),
            patch("os.write"),
            patch("os.close"),
            patch("os.read", return_value=b""),
            patch("select.select", side_effect=OSError),
            patch("great_docs._term_player.recorder._set_raw_mode"),
            patch("sys.stdin", mock_stdin),
            patch("sys.stderr"),
        ):
            record_session(output_path)

        lines = output_path.read_text().strip().splitlines()
        events = [json.loads(l) for l in lines[1:] if l.strip()]
        x_events = [e for e in events if e[1] == "x"]
        assert len(x_events) == 1
        assert x_events[0][2] == "1"

    def test_wifexited_false_uses_code_1(self, tmp_path: Path):
        """When WIFEXITED is False, exit code defaults to 1."""
        output_path = tmp_path / "session.termshow"
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = _STDIN_FD

        with (
            patch("pty.fork", return_value=(_PID, _MASTER_FD)),
            patch("fcntl.ioctl"),
            patch("termios.tcgetattr", return_value=[]),
            patch("termios.tcsetattr"),
            patch("os.get_terminal_size", side_effect=OSError),
            patch("os.waitpid", return_value=(_PID, 9)),  # signal-killed
            patch("os.WIFEXITED", return_value=False),
            patch("os.WEXITSTATUS", return_value=0),
            patch("os.write"),
            patch("os.close"),
            patch("os.read", return_value=b""),
            patch("select.select", side_effect=OSError),
            patch("great_docs._term_player.recorder._set_raw_mode"),
            patch("sys.stdin", mock_stdin),
            patch("sys.stderr"),
        ):
            record_session(output_path)

        lines = output_path.read_text().strip().splitlines()
        events = [json.loads(l) for l in lines[1:] if l.strip()]
        x_events = [e for e in events if e[1] == "x"]
        assert x_events[0][2] == "1"

    def test_terminal_size_from_os(self, tmp_path: Path):
        """When cols/rows not given and os.get_terminal_size succeeds, uses those values."""
        output_path = tmp_path / "session.termshow"
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = _STDIN_FD
        mock_size = MagicMock()
        mock_size.columns = 120
        mock_size.lines = 40

        with (
            patch("pty.fork", return_value=(_PID, _MASTER_FD)),
            patch("fcntl.ioctl"),
            patch("termios.tcgetattr", return_value=[]),
            patch("termios.tcsetattr"),
            patch("os.get_terminal_size", return_value=mock_size),
            patch("os.waitpid", return_value=(_PID, 0)),
            patch("os.WIFEXITED", return_value=True),
            patch("os.WEXITSTATUS", return_value=0),
            patch("os.write"),
            patch("os.close"),
            patch("os.read", return_value=b""),
            patch("select.select", side_effect=OSError),
            patch("great_docs._term_player.recorder._set_raw_mode"),
            patch("sys.stdin", mock_stdin),
            patch("sys.stderr"),
        ):
            record_session(output_path)

        header = json.loads(output_path.read_text().splitlines()[0])
        assert header["term"]["cols"] == 120
        assert header["term"]["rows"] == 40

    def test_explicit_cols_rows_shell(self, tmp_path: Path):
        """Explicit cols, rows, shell bypass detection."""
        output_path = tmp_path / "session.termshow"
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = _STDIN_FD

        with (
            patch("pty.fork", return_value=(_PID, _MASTER_FD)),
            patch("fcntl.ioctl"),
            patch("termios.tcgetattr", return_value=[]),
            patch("termios.tcsetattr"),
            patch("os.get_terminal_size", side_effect=OSError),
            patch("os.waitpid", return_value=(_PID, 0)),
            patch("os.WIFEXITED", return_value=True),
            patch("os.WEXITSTATUS", return_value=0),
            patch("os.write"),
            patch("os.close"),
            patch("os.read", return_value=b""),
            patch("select.select", side_effect=OSError),
            patch("great_docs._term_player.recorder._set_raw_mode"),
            patch("sys.stdin", mock_stdin),
            patch("sys.stderr"),
        ):
            record_session(output_path, cols=100, rows=30, shell="/bin/bash")

        header = json.loads(output_path.read_text().splitlines()[0])
        assert header["term"]["cols"] == 100
        assert header["term"]["rows"] == 30

    def test_yml_template_created(self, tmp_path: Path):
        """A companion .termshow.yml template is written alongside the recording."""
        output_path = tmp_path / "session.termshow"
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = _STDIN_FD

        with (
            patch("pty.fork", return_value=(_PID, _MASTER_FD)),
            patch("fcntl.ioctl"),
            patch("termios.tcgetattr", return_value=[]),
            patch("termios.tcsetattr"),
            patch("os.get_terminal_size", side_effect=OSError),
            patch("os.waitpid", return_value=(_PID, 0)),
            patch("os.WIFEXITED", return_value=True),
            patch("os.WEXITSTATUS", return_value=0),
            patch("os.write"),
            patch("os.close"),
            patch("os.read", return_value=b""),
            patch("select.select", side_effect=OSError),
            patch("great_docs._term_player.recorder._set_raw_mode"),
            patch("sys.stdin", mock_stdin),
            patch("sys.stderr"),
        ):
            record_session(output_path)

        yml_path = Path(str(output_path) + ".yml")
        assert yml_path.exists()
        assert "source: session.termshow" in yml_path.read_text()

    def test_yml_not_overwritten_if_exists(self, tmp_path: Path):
        """Pre-existing .yml file is not overwritten."""
        output_path = tmp_path / "session.termshow"
        yml_path = Path(str(output_path) + ".yml")
        yml_path.write_text("existing: content\n")
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = _STDIN_FD

        with (
            patch("pty.fork", return_value=(_PID, _MASTER_FD)),
            patch("fcntl.ioctl"),
            patch("termios.tcgetattr", return_value=[]),
            patch("termios.tcsetattr"),
            patch("os.get_terminal_size", side_effect=OSError),
            patch("os.waitpid", return_value=(_PID, 0)),
            patch("os.WIFEXITED", return_value=True),
            patch("os.WEXITSTATUS", return_value=0),
            patch("os.write"),
            patch("os.close"),
            patch("os.read", return_value=b""),
            patch("select.select", side_effect=OSError),
            patch("great_docs._term_player.recorder._set_raw_mode"),
            patch("sys.stdin", mock_stdin),
            patch("sys.stderr"),
        ):
            record_session(output_path)

        assert yml_path.read_text() == "existing: content\n"

    def test_os_close_oserror_suppressed(self, tmp_path: Path):
        """OSError from os.close in finally is suppressed."""
        output_path = tmp_path / "session.termshow"
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = _STDIN_FD

        with (
            patch("pty.fork", return_value=(_PID, _MASTER_FD)),
            patch("fcntl.ioctl"),
            patch("termios.tcgetattr", return_value=[]),
            patch("termios.tcsetattr"),
            patch("os.get_terminal_size", side_effect=OSError),
            patch("os.waitpid", return_value=(_PID, 0)),
            patch("os.WIFEXITED", return_value=True),
            patch("os.WEXITSTATUS", return_value=0),
            patch("os.write"),
            patch("os.close", side_effect=OSError("already closed")),
            patch("os.read", return_value=b""),
            patch("select.select", side_effect=OSError),
            patch("great_docs._term_player.recorder._set_raw_mode"),
            patch("sys.stdin", mock_stdin),
            patch("sys.stderr"),
        ):
            record_session(output_path)  # must not raise

        assert output_path.exists()

    def test_creates_output_subdirectory(self, tmp_path: Path):
        """Output directory is created if it doesn't exist."""
        output_path = tmp_path / "subdir" / "nested" / "session.termshow"
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = _STDIN_FD

        with (
            patch("pty.fork", return_value=(_PID, _MASTER_FD)),
            patch("fcntl.ioctl"),
            patch("termios.tcgetattr", return_value=[]),
            patch("termios.tcsetattr"),
            patch("os.get_terminal_size", side_effect=OSError),
            patch("os.waitpid", return_value=(_PID, 0)),
            patch("os.WIFEXITED", return_value=True),
            patch("os.WEXITSTATUS", return_value=0),
            patch("os.write"),
            patch("os.close"),
            patch("os.read", return_value=b""),
            patch("select.select", side_effect=OSError),
            patch("great_docs._term_player.recorder._set_raw_mode"),
            patch("sys.stdin", mock_stdin),
            patch("sys.stderr"),
        ):
            record_session(output_path)

        assert output_path.exists()

    def test_loop_continues_when_select_returns_empty(self, tmp_path: Path):
        """select returning no readable fds causes while loop to continue, then OSError exits."""
        output_path = tmp_path / "session.termshow"
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = _STDIN_FD

        select_calls = iter(
            [
                ([], [], []),  # no readable → for loop has no items → else: continue
                OSError("done"),
            ]
        )

        def _sel(*args, **kwargs):
            val = next(select_calls)
            if isinstance(val, Exception):
                raise val
            return val

        with (
            patch("pty.fork", return_value=(_PID, _MASTER_FD)),
            patch("fcntl.ioctl"),
            patch("termios.tcgetattr", return_value=[]),
            patch("termios.tcsetattr"),
            patch("os.get_terminal_size", side_effect=OSError),
            patch("os.waitpid", return_value=(_PID, 0)),
            patch("os.WIFEXITED", return_value=True),
            patch("os.WEXITSTATUS", return_value=0),
            patch("os.write"),
            patch("os.close"),
            patch("os.read", return_value=b""),
            patch("select.select", side_effect=_sel),
            patch("great_docs._term_player.recorder._set_raw_mode"),
            patch("sys.stdin", mock_stdin),
            patch("sys.stderr"),
        ):
            record_session(output_path)

        assert output_path.exists()

    def test_unknown_fd_in_readable_ignored(self, tmp_path: Path):
        """An fd that is neither master_fd nor stdin_fd is silently skipped."""
        output_path = tmp_path / "session.termshow"
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = _STDIN_FD

        UNKNOWN_FD = 99
        select_calls = iter(
            [
                ([UNKNOWN_FD], [], []),  # unknown fd → both if/elif are False → else: continue
                OSError("done"),
            ]
        )

        def _sel(*args, **kwargs):
            val = next(select_calls)
            if isinstance(val, Exception):
                raise val
            return val

        with (
            patch("pty.fork", return_value=(_PID, _MASTER_FD)),
            patch("fcntl.ioctl"),
            patch("termios.tcgetattr", return_value=[]),
            patch("termios.tcsetattr"),
            patch("os.get_terminal_size", side_effect=OSError),
            patch("os.waitpid", return_value=(_PID, 0)),
            patch("os.WIFEXITED", return_value=True),
            patch("os.WEXITSTATUS", return_value=0),
            patch("os.write"),
            patch("os.close"),
            patch("os.read", return_value=b""),
            patch("select.select", side_effect=_sel),
            patch("great_docs._term_player.recorder._set_raw_mode"),
            patch("sys.stdin", mock_stdin),
            patch("sys.stderr"),
        ):
            record_session(output_path)

        assert output_path.exists()

    def test_stdin_read_oserror_treated_as_empty(self, tmp_path: Path):
        """OSError from os.read(stdin_fd) is caught; empty data then breaks loop."""
        output_path = tmp_path / "session.termshow"
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = _STDIN_FD

        def _mock_read(fd, size):
            if fd == _STDIN_FD:
                raise OSError("stdin gone")
            return b""

        with (
            patch("pty.fork", return_value=(_PID, _MASTER_FD)),
            patch("fcntl.ioctl"),
            patch("termios.tcgetattr", return_value=[]),
            patch("termios.tcsetattr"),
            patch("os.get_terminal_size", side_effect=OSError),
            patch("os.waitpid", return_value=(_PID, 0)),
            patch("os.WIFEXITED", return_value=True),
            patch("os.WEXITSTATUS", return_value=0),
            patch("os.write"),
            patch("os.close"),
            patch("os.read", side_effect=_mock_read),
            patch("select.select", return_value=([_STDIN_FD], [], [])),
            patch("great_docs._term_player.recorder._set_raw_mode"),
            patch("sys.stdin", mock_stdin),
            patch("sys.stderr"),
        ):
            record_session(output_path)

        assert output_path.exists()


# ---------------------------------------------------------------------------
# _set_raw_mode
# ---------------------------------------------------------------------------


class TestSetRawMode:
    def test_calls_tty_setraw(self):
        """_set_raw_mode calls tty.setraw with the given fd."""
        with patch("tty.setraw") as mock_setraw, patch("termios.TCSADRAIN", 1):
            _set_raw_mode(5)
        mock_setraw.assert_called_once_with(5, 1)


# ---------------------------------------------------------------------------
# _strip_recorder_messages — uncovered branches
# ---------------------------------------------------------------------------


class TestStripRecorderMessagesEdgeCases:
    def test_invalid_json_line_preserved(self):
        """A line with invalid JSON is kept verbatim in the output."""
        header = json.dumps({"version": 1, "format": "termshow"})
        invalid = "this is not json at all"
        result = _strip_recorder_messages([header, invalid])
        assert invalid in result

    def test_non_list_json_preserved(self):
        """A valid JSON line that is not a list (e.g. a dict) is kept verbatim."""
        header = json.dumps({"version": 1, "format": "termshow"})
        dict_line = json.dumps({"unexpected": "dict"})
        result = _strip_recorder_messages([header, dict_line])
        assert dict_line in result

    def test_short_list_json_preserved(self):
        """A JSON array with fewer than 3 elements is kept verbatim."""
        header = json.dumps({"version": 1, "format": "termshow"})
        short = json.dumps([0.5, "o"])  # only 2 elements
        result = _strip_recorder_messages([header, short])
        assert short in result


# ---------------------------------------------------------------------------
# _is_recorder_message — empty data branch
# ---------------------------------------------------------------------------


class TestIsRecorderMessageEdgeCases:
    def test_empty_string_returns_false(self):
        """Empty data string returns False (no match possible)."""
        ansi_re = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
        assert _is_recorder_message("", ansi_re) is False

    def test_only_ansi_escapes_returns_false(self):
        """Data that is entirely ANSI escape codes → stripped to empty → False."""
        ansi_re = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
        assert _is_recorder_message("\x1b[32m\x1b[0m", ansi_re) is False

    def test_whitespace_only_returns_false(self):
        """Data that is only whitespace after stripping returns False."""
        ansi_re = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
        assert _is_recorder_message("   \n\t  ", ansi_re) is False
