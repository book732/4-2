"""Verify procfs parsing and interval calculations without Linux dependencies."""

import argparse
import importlib.util
from pathlib import Path
import tempfile
import unittest


def _load_monitor():
    _spec = importlib.util.spec_from_file_location("_monitor", Path(__file__).resolve().parents[1] / "scripts/monitor.py")
    _module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_module)
    return _module


def _test_stat_command_name():
    _module = _load_monitor()
    _fields = ["0"] * 22
    _fields[0], _fields[11], _fields[12] = "S", "200", "50"
    _fields[17], _fields[19], _fields[21] = "4", "12345", "1024"
    with tempfile.TemporaryDirectory() as _directory:
        _path = Path(_directory) / "stat"
        _path.write_text("42 (worker ) name) " + " ".join(_fields), encoding="utf-8")
        assert _module._read_process(_path) == {"state": "S", "ticks": 250, "threads": 4, "start": 12345, "rss_pages": 1024}


def _test_cpu_and_rss_units():
    _module = _load_monitor()
    _result = _module._calculate_metrics({"ticks": 100}, {"ticks": 500, "rss_pages": 256}, 2.0, 100, 4096, 2048)
    assert _result == (200.0, 1024.0, 50.0), _result


def _test_idle_process():
    _module = _load_monitor()
    assert _module._calculate_metrics({"ticks": 100}, {"ticks": 100, "rss_pages": 256}, 1, 100, 4096, 2048)[0] == 0


def _test_malformed_stat():
    _module = _load_monitor()
    with tempfile.TemporaryDirectory() as _directory:
        _path = Path(_directory) / "stat"
        _path.write_text("42 (worker) S 1", encoding="utf-8")
        with unittest.TestCase().assertRaises(ValueError):
            _module._read_process(_path)


def _test_interval_validation():
    _module = _load_monitor()
    for _value in ("nan", "inf", "-1", "0", "0.01"):
        with unittest.TestCase().assertRaises(argparse.ArgumentTypeError):
            _module._positive_interval(_value)
    assert _module._positive_interval("0.1") == 0.1


def _test_integer_validation():
    _module = _load_monitor()
    for _value in ("0", "-1"):
        with unittest.TestCase().assertRaises(argparse.ArgumentTypeError):
            _module._positive_integer(_value)
    assert _module._positive_integer("42") == 42


def _main():
    _tests = (_test_stat_command_name, _test_cpu_and_rss_units, _test_idle_process,
              _test_malformed_stat, _test_interval_validation, _test_integer_validation)
    _suite = unittest.TestSuite(unittest.FunctionTestCase(_test) for _test in _tests)
    return 0 if unittest.TextTestRunner(verbosity=2).run(_suite).wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(_main())
