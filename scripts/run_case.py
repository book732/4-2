"""Run one bounded experiment and collect workload PID evidence."""

import argparse
import csv
import datetime
import errno
import hashlib
import json
import os
from pathlib import Path
import pty
import signal
import socket
import subprocess
import sys
import time

from monitor import _positive_interval


def _drain_output(_descriptor, _log):
    # A PTY preserves line-buffered terminal messages before abrupt exit.
    while True:
        try:
            _data = os.read(_descriptor, 65536)
        except BlockingIOError:
            break
        except OSError as _error:
            if _error.errno == errno.EIO:
                break
            raise
        if not _data:
            break
        _log.write(_data)
    _log.flush()


def _snapshot(_directory, _launcher_pid, _workload_pid):
    for _name, _command in (
        ("ps.txt", ["ps", "-p", f"{_launcher_pid},{_workload_pid}", "-o", "pid,ppid,pgid,etime,pcpu,pmem,rss,nlwp,stat,args"]),
        ("threads.txt", ["ps", "-L", "-p", str(_workload_pid), "-o", "pid,tid,pcpu,stat,wchan:32,comm"]),
        ("top.txt", ["top", "-H", "-b", "-n", "1", "-p", str(_workload_pid)]),
    ):
        with (_directory / _name).open("a", encoding="utf-8") as _output:
            _output.write("\n" + datetime.datetime.now().astimezone().isoformat() + "\n")
            _output.flush()
            subprocess.run(_command, stdout=_output, stderr=subprocess.STDOUT, check=False, timeout=5)


def _run_case(_args):
    _root = Path(__file__).resolve().parents[1]
    if os.geteuid() == 0 or not os.environ.get("AGENT_HOME"):
        raise RuntimeError("일반 사용자로 prepare.sh를 먼저 적용하세요.")
    with socket.socket() as _socket:
        _socket.bind(("0.0.0.0", 15034))
    _directory = _root / "evidence" / (_args.label + "-" + datetime.datetime.now().strftime("%Y%m%dT%H%M%S"))
    _directory.mkdir(mode=0o700)
    (_directory / "application").mkdir()
    _environment = os.environ.copy()
    _environment.update(AGENT_LOG_DIR=str(_directory / "application"), MEMORY_LIMIT=str(_args.memory),
                        CPU_MAX_OCCUPY=str(_args.cpu), MULTI_THREAD_ENABLE=_args.threads)
    _metadata = {"label": _args.label, "started_at": datetime.datetime.now().astimezone().isoformat(),
                 "max_seconds": _args.seconds, "MEMORY_LIMIT": _args.memory, "CPU_MAX_OCCUPY": _args.cpu,
                 "MULTI_THREAD_ENABLE": _args.threads, "manual_stop": False,
                 "interval_seconds": _args.interval, "capture_mode": "pty",
                 "python_version": sys.version.split()[0], "kernel": os.uname().release,
                 "binary_sha256": hashlib.sha256((_root / "bin/agent-leak-app-x86").read_bytes()).hexdigest()}
    _started = time.monotonic()
    _monitor = None
    _top = None
    _top_log = None
    with (_directory / "app.log").open("wb") as _log, (_directory / "monitor.csv").open("w", encoding="utf-8", newline="") as _csv:
        _master, _slave = pty.openpty()
        os.set_blocking(_master, False)
        _process = subprocess.Popen([str(_root / "bin/agent-leak-app-x86")], env=_environment,
                                    stdout=_slave, stderr=subprocess.STDOUT, start_new_session=True)
        os.close(_slave)
        _workload_pid = _process.pid
        try:
            # The provided one-file launcher starts the actual workload as its child.
            for _index in range(30):
                if _process.poll() is not None:
                    break
                _children = Path(f"/proc/{_process.pid}/task/{_process.pid}/children").read_text().split()
                if _children:
                    _workload_pid = int(_children[0])
                    break
                time.sleep(0.1)
            _metadata.update(launcher_pid=_process.pid, workload_pid=_workload_pid)
            if _process.poll() is None:
                _monitor = subprocess.Popen([sys.executable, str(_root / "scripts/monitor.py"), str(_workload_pid),
                                             "--interval", str(_args.interval)], stdout=_csv)
                if _args.label.startswith("cpu-"):
                    _top_log = (_directory / "top-continuous.txt").open("w", encoding="utf-8")
                    _top = subprocess.Popen(["top", "-H", "-b", "-d", str(_args.interval), "-n",
                                             str(int(_args.seconds / _args.interval) + 2), "-p", str(_workload_pid)],
                                            stdout=_top_log, stderr=subprocess.STDOUT)
            _next_snapshot = 0
            while _process.poll() is None and time.monotonic() - _started < _args.seconds:
                _drain_output(_master, _log)
                if time.monotonic() >= _next_snapshot:
                    _snapshot(_directory, _process.pid, _workload_pid)
                    _next_snapshot = time.monotonic() + 5
                time.sleep(0.1)
            if _process.poll() is None:
                _metadata["manual_stop"] = True
                _snapshot(_directory, _process.pid, _workload_pid)
        finally:
            # Signal only the process group created by this experiment.
            if _process.poll() is None:
                _metadata["manual_stop"] = True
            try:
                os.killpg(_process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                _process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(_process.pid, signal.SIGKILL)
                _process.wait()
            if _monitor is not None:
                try:
                    _monitor.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    _monitor.terminate()
                    _monitor.wait(timeout=2)
                _metadata["monitor_returncode"] = _monitor.returncode
            if _top is not None:
                if _top.poll() is None:
                    _top.terminate()
                try:
                    _top.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    _top.kill()
                    _top.wait()
                _top_log.close()
            _metadata.update(returncode=_process.returncode, elapsed_seconds=round(time.monotonic() - _started, 3),
                             ended_at=datetime.datetime.now().astimezone().isoformat())
            _drain_output(_master, _log)
            os.close(_master)
            (_directory / "metadata.json").write_text(json.dumps(_metadata, indent=2) + "\n", encoding="utf-8")
    with (_directory / "monitor.csv").open(newline="", encoding="utf-8") as _input:
        _rows = list(csv.DictReader(_input))
    if _rows:
        _metadata.update(samples=len(_rows), first_rss_kib=float(_rows[0]["rss_kib"]),
                         max_rss_kib=max(float(_row["rss_kib"]) for _row in _rows),
                         max_cpu_percent=max(float(_row["cpu_percent"]) for _row in _rows))
        (_directory / "metadata.json").write_text(json.dumps(_metadata, indent=2) + "\n", encoding="utf-8")
    print(_directory, flush=True)
    print(json.dumps(_metadata), flush=True)
    print("\n".join((_directory / "app.log").read_text(encoding="utf-8", errors="replace").splitlines()[-30:]), flush=True)


def _main():
    _parser = argparse.ArgumentParser(description="단일 장애 실험과 원본 증거 수집")
    _parser.add_argument("label", choices=("oom-before", "oom-after", "cpu-before", "cpu-after", "deadlock-before", "deadlock-after"))
    _parser.add_argument("--memory", type=int, choices=range(50, 513), required=True)
    _parser.add_argument("--cpu", type=int, choices=range(10, 101), required=True)
    _parser.add_argument("--threads", choices=("true", "false"), required=True)
    _parser.add_argument("--seconds", type=int, choices=range(1, 601), default=90)
    _parser.add_argument("--interval", type=_positive_interval, default=1.0)
    _run_case(_parser.parse_args())


if __name__ == "__main__":
    _main()
