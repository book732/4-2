"""Verify nonblocking terminal capture, including abrupt child termination."""

import importlib
import io
import os
from pathlib import Path
import pty
import subprocess
import sys
import unittest


def _load_runner():
    _path = str(Path(__file__).resolve().parents[1] / "scripts")
    sys.path.insert(0, _path)
    try:
        return importlib.import_module("run_case")
    finally:
        sys.path.pop(0)


def _test_empty_terminal_does_not_block():
    _module = _load_runner()
    _master, _slave = pty.openpty()
    os.set_blocking(_master, False)
    try:
        _output = io.BytesIO()
        _module._drain_output(_master, _output)
        assert _output.getvalue() == b""
    finally:
        os.close(_master)
        os.close(_slave)


def _test_last_line_survives_sigterm():
    _module = _load_runner()
    _master, _slave = pty.openpty()
    os.set_blocking(_master, False)
    try:
        _process = subprocess.Popen(
            [sys.executable, "-c", "import os,signal; print('FINAL TERMINAL MESSAGE'); os.kill(os.getpid(), signal.SIGTERM)"],
            stdout=_slave, stderr=subprocess.STDOUT,
        )
        os.close(_slave)
        _slave = None
        assert _process.wait(timeout=5) == -15
        _output = io.BytesIO()
        _module._drain_output(_master, _output)
        assert _output.getvalue().replace(b"\r\n", b"\n") == b"FINAL TERMINAL MESSAGE\n"
    finally:
        os.close(_master)
        if _slave is not None:
            os.close(_slave)


def _main():
    _suite = unittest.TestSuite(unittest.FunctionTestCase(_test) for _test in
                                (_test_empty_terminal_does_not_block, _test_last_line_survives_sigterm))
    return 0 if unittest.TextTestRunner(verbosity=2).run(_suite).wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(_main())
