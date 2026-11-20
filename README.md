# 4-2: Linux 프로세스 장애 분석

제공 프로그램의 메모리 누수·CPU 과점유·데드락을 관측하고, 증거를 근거로 기술 리포트 3건을 작성하는 프로젝트다. 요구사항 원본은 [4-2.pdf](4-2.pdf), 검증 기준은 [docs/requirements.md](docs/requirements.md)에 있다.

현재 상태는 **요청한 증거 보완 완료**다. Ubuntu 26.04.1 LTS / WSL2의 일반 사용자로 기동 확인 1회, 초기 비교 5회, 보완 비교 4회를 수행했다. 메모리의 동일 증분 패턴·캐시 복구, 0.1초 OS CPU 피크·명시적 Watchdog 종료, 데드락의 순환 대기와 회피를 근거로 보고서 3종을 작성했다. [실험 요약](docs/experiment-summary.md)과 [검증 기록](docs/verification.md)을 참고한다.

## 구성

- `scripts/prepare.sh`: 환경변수 검사, 런타임 디렉터리·과제용 키 파일 준비
- `scripts/monitor.sh`, `scripts/monitor.py`: Linux `/proc`에서 PID별 CPU·RSS를 CSV로 수집
- `scripts/run_case.py`: 실제 작업 PID 탐색, 제한 시간 실험, 원본 증거 수집과 수동 종료 표시
- `reports/01-oom.md`, `02-cpu.md`, `03-deadlock.md`: 실측 기반 보고서 3종과 검증 한계
- `evidence/`: 보고서 근거인 실행별 원본 로그, Git에 포함
- `bin/`: 제공받은 실행 파일 배치, 기본 Git 제외
- `tests/test_monitor.py`: 관제 파싱·단위 계산 검증
- `tests/test_run_case.py`: Linux 비차단 터미널 수집·SIGTERM 직전 출력 보존 검증

외부 Python 패키지는 필요 없다. Linux 실행 환경에는 Bash, Python 3, procfs, `ps`·`top`·`ss`가 필요하다. 실행 파일 자체의 의존성은 제공 패키지에서 별도로 확인한다.

## 환경과 실행

일반 사용자 Linux 셸에서 프로젝트 루트로 이동한다. WSL에서 현재 프로젝트 경로는 `/mnt/d/Codissey/4-2`다. 아래 명령 예시는 실제 Linux에서 실행해야 한다. 현재 Windows 호스트는 x86-64이므로 배치된 `bin/agent-leak-app-x86`을 사용한다. ARM64 Linux에서는 실행 명령의 경로를 `bin/agent-leak-app-arm64`로 바꾼다. 두 파일은 ELF 64비트 Linux 실행 파일이며 Windows에서 직접 실행하지 않는다.

```bash
source scripts/prepare.sh
uname -m
file bin/agent-leak-app-x86
chmod u+x bin/agent-leak-app-x86
ss -ltn 'sport = :15034'
```

포트 사용 중인 프로세스가 있으면 실험을 진행하지 않고 점유 원인을 확인한다. 전역 프로필·방화벽 설정은 바꾸지 않는다. `prepare.sh`는 현재 셸의 환경변수만 설정한다. 기본값 256 MB·50%·단일 스레드는 준비용 값이며 특정 장애를 유발하는 확정 조건이 아니다.

아래 함수는 OOM 변경 전 조건을 최대 90초 실행한다. `run_case.py`가 실행마다 새 증거 폴더를 만들고, 제공 프로그램의 런처 자식인 실제 작업 PID를 찾아 관측한다. `--seconds`는 1~600초, `--interval`은 0.1초 이상이다. 같은 포트를 사용하므로 실험을 동시에 실행하지 않는다.

```bash
_start_experiment() {
    source scripts/prepare.sh || return
    python3 scripts/run_case.py oom-before --memory 256 --cpu 30 --threads false --seconds 90 --interval 1
}

_start_experiment
```

수집 결과는 `app.log`, `monitor.csv`, `ps.txt`, `threads.txt`, `top.txt`, `metadata.json`, `application/`이다. 보완 수집기는 PTY로 앱 출력을 받아 종료 직전 터미널 메시지도 보존한다. CPU 케이스에서는 같은 간격의 `top-continuous.txt`도 수집한다. `%CPU`는 `ps`의 실행 후 평균과 관제의 구간 측정이 다르므로 직접 같은 지표처럼 비교하지 않는다.

`run_case.py`는 제한 시간 종료 시 자신이 시작한 프로세스 그룹을 종료하고 `manual_stop=true`를 기록한다. 자체 종료와 수동 종료는 메타데이터로 구분하며, Python의 `returncode=-9/-15`는 각각 SIGKILL/SIGTERM이다. `monitor.sh`만 단독 실행하면 대상 앱을 종료하지 않는다. 수동 종료 결과를 MemoryGuard·Watchdog 종료로 분류하지 않는다.

## 변경 전후 비교

| 비교 | Before 제안값 | After 제안값 | 고정값 |
| --- | --- | --- | --- |
| OOM | MEMORY_LIMIT=256 | MEMORY_LIMIT=512 | CPU_MAX_OCCUPY=30, MULTI_THREAD_ENABLE=false |
| CPU | CPU_MAX_OCCUPY=100 | CPU_MAX_OCCUPY=30 | MEMORY_LIMIT=512, MULTI_THREAD_ENABLE=false |
| Deadlock | MULTI_THREAD_ENABLE=true | MULTI_THREAD_ENABLE=false | MEMORY_LIMIT=512, CPU_MAX_OCCUPY=30 |

현재 보고서의 OOM은 두 조건 모두 90초 상한·1초 관제, CPU는 60초 상한·0.1초 관제, Deadlock은 45초 상한·1초 관제다. 변경 후에는 별도 증거 폴더를 생성한다. 각 쌍의 한 변수만 바꾸고 수집 조건을 유지한다. 앱 내부 실행 경로와 보호 정책 변화도 함께 기록한다.

## 관제 값 해석

CPU는 두 관측 사이의 프로세스 user+system CPU tick 증가량을 실제 경과 시간으로 나눈다. 논리 코어 1개가 100%이며 다중 스레드는 100%를 넘을 수 있다. RSS 단위는 KiB, `memory_percent`는 호스트 `MemTotal` 기준이므로 컨테이너 cgroup 제한 대비 비율은 아니다. 첫 표본은 지정 간격이 지난 후 기록된다. PID 종료·좀비 상태·PID 재사용을 감지하면 수집을 끝낸다.

## 로컬 검증

```bash
python3 tests/test_monitor.py
python3 tests/test_run_case.py
bash -n scripts/prepare.sh
bash -n scripts/monitor.sh
```

Windows에서는 관제 계산 테스트를 실행할 수 있다. 터미널 수집 테스트와 `/proc` 실측은 Linux에서 실행한다. 관제 6개·터미널 수집 2개, 총 8개 테스트가 통과했다. 보고서와 원본 증거를 Git에 함께 포함하며 `.gitattributes`로 증거 파일의 줄바꿈 변환을 비활성화했다. `.runtime/`의 키 파일과 `bin/`의 제공 실행 파일은 제외한다. 저장소를 새로 받으면 제공 실행 파일을 별도로 배치해야 한다.
