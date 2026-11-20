# 초기 구성 검증

검증일: 2026-11-20, Windows 호스트.

| 항목 | 결과 |
| --- | --- |
| 원본 PDF 및 프로젝트 내 사본 SHA-256 | 일치 |
| PDF 10페이지 텍스트와 렌더 이미지 확인 | 완료 |
| `python tests/test_monitor.py` | 6개 통과 |
| Python 파일 `py_compile` | 통과 |
| `bash -n scripts/prepare.sh` | 통과 |
| `bash -n scripts/monitor.sh` | 통과 |

Python 검증에는 Codex 번들 Python 3.12를 사용했다. 셸 구문 검사는 Git Bash를 사용했다. Git Bash의 최초 실행이 샌드박스에서 차단되어, 읽기 전용 구문 검사를 별도 실행 권한으로 재시도한 뒤 통과했다.

계산 테스트는 공백·닫는 괄호가 포함된 프로세스 이름, 다중 코어 CPU 수치, RSS 단위 변환, 유휴 CPU, 손상된 stat 입력, 측정 인자 범위를 확인했다.

이 초기 검증 시점에는 Linux 실측을 수행하지 않았다. 이후 Ubuntu 설치와 실제 실험 검증 결과는 아래 후속 기록에 구분했다.

## 제공 ZIP 확인 및 실행 파일 배치

2026-11-20에 사용자가 제공한 `C:\Users\last_\Downloads\agent-app-leak.zip`을 확인했다. 실행 파일의 내용은 수정하지 않고 `bin/`에 배치했으며 ZIP에서 읽은 바이트와 배치된 파일이 일치함을 검증했다. macOS 부가 메타데이터인 `__MACOSX/` 항목은 배치하지 않았다.

| 파일 | 크기(bytes) | 형식 |
| --- | --- | --- |
| bin/agent-leak-app-x86 | 6502016 | ELF 64비트, little endian, x86-64 |
| bin/agent-leak-app-arm64 | 6261928 | ELF 64비트, little endian, AArch64 |

SHA-256:

- 원본 ZIP: `249c9c2841718cb29ef2ed680668f328f5ee253354090225347e130a2e456641`
- x86-64: `7e0a19cfa80ece6b547a5008273661f0d4d71e526e96b51e0d0f341dd1bb3e40`
- ARM64: `2edd8eb1b6ae40ac611afe880b864f0399ff0977bfd72d9d0fd98aa41ca6d1ff`

현재 Windows 호스트 아키텍처는 AMD64다. WSL 목록 조회는 최초 샌드박스 접근에서 거부되었고, 별도 실행 권한으로 재조회한 결과 WSL에 설치된 Linux 배포판이 없다고 확인됐다. WSL 자체의 미설치와 배포판 미설치는 구분한다. Linux 실행 환경과 프로그램 실행 의존성은 아직 확인하지 못했으므로 배치 성공을 실행 성공으로 간주하지 않는다.

## Ubuntu 설치 후 검증 및 실제 실험

사용자가 Ubuntu 설치와 사용자 계정 초기 설정을 완료한 뒤 다음을 확인했다. 앞의 배포판 미설치 상태는 이 검증으로 갱신됐다.

| 항목 | 실제 확인 결과 |
| --- | --- |
| Linux 환경 | Ubuntu 26.04.1 LTS, x86-64, WSL2 |
| 실행 계정 | uid=1000(last_), root 아님 |
| Python | 3.14.4 |
| 필수 도구 | python3, ps, top, ss, file 존재 |
| prepare.sh 실제 실행 | 성공 |
| 제공 앱 부트 검사 | 6개 모두 통과, Agent READY |
| 관제 실제 실행 | 작업 자식 PID의 /proc 수집 성공 |
| 관제 테스트 | Linux에서 6개 통과 |
| Python 구문 | monitor.py, run_case.py py_compile 통과 |
| Bash 구문 | prepare.sh, monitor.sh 통과 |
| 1차 실험 | 기동 확인 1회, 조건 비교 5회 |
| 실험 종료 후 | 대상 실행 프로세스 없음, 15034 리슨 소켓 없음 |
| x86-64 바이너리 SHA-256 | 배치 시 원본 해시와 일치 |

[실험 요약](experiment-summary.md)에 실행별 결과와 원본 증거 경로를 기록했다. 단일 파일 실행 런처와 실제 작업 PID를 구분했으며, 시간 제한으로 수집기가 종료한 경우 metadata.json의 manual_stop에 표시했다. 잔여 프로세스 확인과 포트 해제는 모든 비교 실행이 끝난 뒤 다시 확인했다.

1차 실험에서는 메모리 경로 변화와 앱 Load/OS CPU 수치 차이가 남았다. 다음 보완 실험에서 증거를 추가했다. 데드락 근거는 기존 자원 획득·순환 대기 로그, OS futex 대기, PID 유지와 정체된 RSS를 사용한다.

## 증거 보완 검증

| 항목 | 확인 결과 |
| --- | --- |
| 관제 조건 | CLI interval 추가, 실제 간격을 메타데이터에 기록 |
| 터미널 출력 | PTY 비차단 수집으로 SELF-TERMINATED·WATCHDOG 보존 |
| 메모리 비교 | CPU 30·멀티스레드 false 고정, 256/512MB 각각 최대 90초 |
| 메모리 결과 | 33.341초 보호 종료 / 캐시 복구 후 최소 90초 생존 |
| 복구 RSS 증거 | 최대 530268 KiB, cleanup 직후 18292 KiB |
| CPU 비교 | 메모리 512·멀티스레드 false 고정, CPU 100/30 각각 최대 60초 |
| CPU 수집 | /proc와 연속 top 모두 0.1초 간격 |
| CPU 피크 | /proc 49.366% → 29.736%, top 단일 스레드 50% → 30% |
| CPU 종료 근거 | WATCHDOG ... SIGTERM 메시지, Before의 manual_stop=false |
| 자동화 검증 | 기존 관제 6개 + PTY 수집 2개, 총 8개 테스트 통과 |

두 PTY 테스트는 입력이 없는 비차단 읽기와 SIGTERM 직전 마지막 줄 보존을 확인한다. 테스트용 자식 프로세스는 수집기 검증에만 사용했고 장애 증거에 포함하지 않았다. 실제 비교는 제공 바이너리 원본으로만 수행했다.

보완 실행 4회의 메타데이터에는 실행 간격, PTY 수집 여부, Python·커널 버전, 바이너리 해시를 추가했다. OOM·CPU의 기존 탐색 실행을 덮어쓰지 않고 최종 보고서를 새 근거로 갱신했다. 짧은 CPU 피크와 지속적인 시스템 전체 과점유는 구분했고, 관측 시간 이후의 안정성을 주장하지 않았다.
