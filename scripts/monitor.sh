#!/usr/bin/env bash

_main() {
    local _script_dir
    _script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || return 1
    python3 "$_script_dir/monitor.py" "$@"
}

_main "$@"
