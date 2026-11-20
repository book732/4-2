"""Collect interval CPU and resident memory metrics from Linux procfs."""

import argparse
import csv
import datetime
import math
import os
from pathlib import Path
import sys
import time


def _positive_integer(_value):
    _number = int(_value)
    if _number <= 0:
        raise argparse.ArgumentTypeError("1 이상의 정수를 지정하세요.")
    return _number


def _positive_interval(_value):
    _number = float(_value)
    if not math.isfinite(_number) or _number < 0.1:
        raise argparse.ArgumentTypeError("측정 간격은 0.1초 이상의 유한수여야 합니다.")
    return _number


def _read_process(_path):
    # The command name may contain spaces and closing parentheses.
    _fields = _path.read_text(encoding="utf-8").rpartition(") ")[2].split()
    if len(_fields) < 22:
        raise ValueError("/proc/PID/stat 형식이 올바르지 않습니다.")
    return {
        "state": _fields[0],
        "ticks": int(_fields[11]) + int(_fields[12]),
        "threads": int(_fields[17]),
        "start": int(_fields[19]),
        "rss_pages": int(_fields[21]),
    }


def _calculate_metrics(_previous, _current, _elapsed, _clock_ticks, _page_size, _total_kib):
    # CPU uses one logical core as 100%; multithreaded values may exceed 100%.
    _cpu = (_current["ticks"] - _previous["ticks"]) * 100 / (_clock_ticks * _elapsed)
    _rss_kib = _current["rss_pages"] * _page_size / 1024
    return round(_cpu, 3), round(_rss_kib, 3), round(_rss_kib * 100 / _total_kib, 5)


def _monitor(_pid, _interval, _samples):
    _path = Path(f"/proc/{_pid}/stat")
    _clock_ticks = os.sysconf("SC_CLK_TCK")
    _page_size = os.sysconf("SC_PAGE_SIZE")
    _total_kib = int(Path("/proc/meminfo").read_text(encoding="ascii").splitlines()[0].split()[1])
    _previous = _read_process(_path)
    _previous_time = time.monotonic()
    if _previous["state"] in ("Z", "X", "x"):
        raise ValueError("대상 PID가 이미 종료 상태입니다.")
    _writer = csv.writer(sys.stdout)
    _writer.writerow(("timestamp", "pid", "cpu_percent", "rss_kib", "memory_percent", "threads", "state"))
    sys.stdout.flush()
    _count = 0
    while _samples is None or _count < _samples:
        time.sleep(_interval)
        try:
            _current = _read_process(_path)
        except ProcessLookupError:
            break
        except FileNotFoundError:
            break
        _now = time.monotonic()
        if _current["start"] != _previous["start"] or _current["state"] in ("Z", "X", "x"):
            break
        _metrics = _calculate_metrics(_previous, _current, _now - _previous_time, _clock_ticks, _page_size, _total_kib)
        _writer.writerow((datetime.datetime.now().astimezone().isoformat(timespec="milliseconds"), _pid,
                          *_metrics, _current["threads"], _current["state"]))
        sys.stdout.flush()
        _previous, _previous_time = _current, _now
        _count += 1


def _main():
    _parser = argparse.ArgumentParser(description="Linux PID별 CPU·RSS CSV 수집")
    _parser.add_argument("pid", type=_positive_integer)
    _parser.add_argument("--interval", type=_positive_interval, default=1.0)
    _parser.add_argument("--samples", type=_positive_integer, help="생략하면 프로세스 종료까지 수집")
    _args = _parser.parse_args()
    if not sys.platform.startswith("linux"):
        _parser.error("관제 실행은 Linux에서만 지원합니다.")
    try:
        _monitor(_args.pid, _args.interval, _args.samples)
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError) as _error:
        print(f"관제 실패: {_error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_main())
