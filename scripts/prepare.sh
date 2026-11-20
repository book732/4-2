#!/usr/bin/env bash

_prepare() {
    local _root _value
    if [[ ${OSTYPE:-} != linux* || $EUID -eq 0 ]]; then
        printf '%s\n' 'Linux 일반 사용자 계정에서 source scripts/prepare.sh로 실행하세요.' >&2
        return 1
    fi

    _root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)" || return 1
    export AGENT_HOME="${AGENT_HOME:-$_root/.runtime}"
    export AGENT_PORT="${AGENT_PORT:-15034}"
    export AGENT_UPLOAD_DIR="${AGENT_UPLOAD_DIR:-$AGENT_HOME/upload_files}"
    export AGENT_KEY_PATH="${AGENT_KEY_PATH:-$AGENT_HOME/api_keys}"
    export AGENT_LOG_DIR="${AGENT_LOG_DIR:-$AGENT_HOME/logs}"
    export MEMORY_LIMIT="${MEMORY_LIMIT:-256}"
    export CPU_MAX_OCCUPY="${CPU_MAX_OCCUPY:-50}"
    export MULTI_THREAD_ENABLE="${MULTI_THREAD_ENABLE:-false}"

    if [[ $AGENT_PORT != 15034 || $AGENT_HOME != /* ||
          $AGENT_UPLOAD_DIR != "$AGENT_HOME/upload_files" ||
          $AGENT_KEY_PATH != "$AGENT_HOME/api_keys" ]]; then
        printf '%s\n' 'AGENT_HOME은 절대 경로, 포트는 15034, 업로드·키 경로는 PDF 지정값이어야 합니다.' >&2
        return 1
    fi
    if [[ ! $MEMORY_LIMIT =~ ^[0-9]{2,3}$ || ! $CPU_MAX_OCCUPY =~ ^[0-9]{2,3}$ ]]; then
        printf '%s\n' 'MEMORY_LIMIT와 CPU_MAX_OCCUPY는 범위 내 정수여야 합니다.' >&2
        return 1
    fi
    if (( 10#$MEMORY_LIMIT < 50 || 10#$MEMORY_LIMIT > 512 ||
          10#$CPU_MAX_OCCUPY < 10 || 10#$CPU_MAX_OCCUPY > 100 )); then
        printf '%s\n' 'MEMORY_LIMIT: 50~512 MB, CPU_MAX_OCCUPY: 10~100% 범위를 확인하세요.' >&2
        return 1
    fi
    _value="${MULTI_THREAD_ENABLE,,}"
    case "$_value" in
        true|1|yes) export MULTI_THREAD_ENABLE=true ;;
        false|0|no) export MULTI_THREAD_ENABLE=false ;;
        *) printf '%s\n' 'MULTI_THREAD_ENABLE 값이 올바르지 않습니다.' >&2; return 1 ;;
    esac

    # Restrict permissions without changing the caller's umask.
    (umask 077; mkdir -p -- "$AGENT_UPLOAD_DIR" "$AGENT_KEY_PATH" "$AGENT_LOG_DIR") || return 1
    if [[ ! -e $AGENT_KEY_PATH/secret.key ]]; then
        (umask 077; set -o noclobber; printf '%s\n' 'agent_api_key_test' > "$AGENT_KEY_PATH/secret.key") || return 1
    fi
    if [[ $(< "$AGENT_KEY_PATH/secret.key") != agent_api_key_test || ! -w $AGENT_LOG_DIR ]]; then
        printf '%s\n' 'secret.key 내용 또는 로그 디렉터리 쓰기 권한을 확인하세요.' >&2
        return 1
    fi
    printf '%s\n' '환경 준비 완료. 15034 포트 바인딩 가능 여부는 실행 전에 확인하세요.'
}

_prepare
