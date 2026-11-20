# 4-2: Linux 프로세스 장애 분석

제공 프로그램의 메모리 누수·CPU 과점유·데드락을 관측하고, 증거를 근거로 기술 리포트 3건을 작성하는 프로젝트다. 요구사항 원본은 [4-2.pdf](4-2.pdf), 검증 기준은 [docs/requirements.md](docs/requirements.md)에 있다.

현재 상태는 **요청한 증거 보완 완료**다. Ubuntu 26.04.1 LTS / WSL2의 일반 사용자로 기동 확인 1회, 초기 비교 5회, 보완 비교 4회를 수행했다. 메모리의 동일 증분 패턴·캐시 복구, 0.1초 OS CPU 피크·명시적 Watchdog 종료, 데드락의 순환 대기와 회피를 근거로 보고서 3종을 작성했다. [실험 요약](docs/experiment-summary.md)과 [검증 기록](docs/verification.md)을 참고한다.

## PDF 기준 발표·설명 가이드

[과제 PDF](4-2.pdf)의 2~3페이지는 보고서 구성과 필수 증거, 3페이지는 학습 목표, 4~5페이지는 장애별 분석과 환경변수 비교를 요구한다. 아래 내용은 이 요구사항에 맞춘 설명 순서다. 수치와 종료 메시지는 이 프로젝트의 실제 실험 결과이며 PDF에 제시된 예시 수치를 옮긴 것이 아니다.

발표는 **발생 현상 → 실행 조건과 증거 → 원인 판단 → 변경한 설정 → 전후 결과와 한계** 순서로 진행한다. 보고서 3건도 같은 흐름의 Description, Evidence & Logs, Root Cause Analysis, Workaround & Verification으로 구성했다.

| PDF에서 설명해야 하는 내용 | 이 프로젝트에서 제시할 근거 |
| --- | --- |
| 메모리 구조, 메모리 누적과 시스템 영향, 보호 종료 | Heap 증가 로그, OS RSS 증가, MemoryGuard·SELF-TERMINATED, 256/512MB 비교 |
| 특정 프로세스의 CPU 상승과 지연 원리, 보호 정책에 의한 종료 | 실제 작업 PID의 0.1초 CSV·연속 top, WATCHDOG·SIGTERM, CPU 설정 100/30 비교 |
| 살아 있지만 진행하지 못하는 프로세스와 순환 대기 | 시각별 PID 유지, 스레드 futex 대기, 자원 획득·BLOCKED 로그, true/false 비교 |
| 증거를 근거로 동료에게 장애를 전달하는 방법 | 실행 조건·시각·PID·로그 경로를 포함한 [보고서 3종](docs/experiment-summary.md) |

### 1. 프로젝트 목적과 실험 방법

발표에서는 다음과 같이 시작한다.

> 이 프로젝트는 제공된 Linux 프로그램에서 메모리 문제, CPU 급상승, 데드락을 재현하고 로그와 운영체제 측정값으로 원인을 분석한 실험입니다. Ubuntu의 일반 사용자 계정에서 실행했고, 환경변수를 하나씩 변경해 장애 발생 전후를 비교했습니다. 제공 프로그램의 내부 코드를 수정한 실험이 아니라 외부 관측으로 진단하고 설정 변경 효과를 검증한 실험입니다.

실험 조건은 Ubuntu 26.04.1 LTS / WSL2 / x86-64, uid=1000이다. 앱의 부트 검사에서 환경변수, 과제용 키 파일, 로그 쓰기 권한, 15034 포트 사용 가능 여부를 확인했다. 런처와 실제 작업 자식 프로세스의 PID를 구분해 작업 프로세스를 측정했다. 비교 실행별 조건과 PID는 `metadata.json`에 남겼다.

### 2. 메모리: 무엇이 증가했고 왜 종료됐는가

설명할 개념은 **Heap과 RSS의 차이, 메모리 누적의 영향, 애플리케이션 보호 종료의 근거**다. Heap은 동적으로 할당한 데이터를 보관하는 메모리 영역이다. RSS는 프로세스의 메모리 중 현재 물리 메모리에 상주하는 양이며 Heap 외의 영역도 포함한다. 앱이 출력한 Heap의 MB 수치와 관제의 RSS KiB를 동일한 값으로 취급하지 않는다.

일반적으로 해제되지 않는 데이터가 계속 쌓이면 프로세스가 더 많은 물리 메모리를 사용하고, 시스템 메모리 압박과 스왑 사용 등으로 다른 작업에도 영향을 줄 수 있다. 이번 실험에서 직접 확인한 것은 대상 프로세스의 증가와 앱 보호 정책이다. 시스템 전체의 메모리 고갈이나 스왑 지연은 측정하지 않았다.

> 메모리 사용량이 약 3초마다 25MB씩 증가했습니다. MEMORY_LIMIT가 256일 때는 앱 Heap이 275MB에 도달한 뒤 MemoryGuard가 제한 초과와 자체 종료를 기록했고, 약 33초에 SIGKILL로 종료됐습니다. CPU 설정 30과 멀티스레드 false를 유지한 채 메모리 설정만 512로 바꾸자, 같은 증가 패턴 이후 525MB에서 캐시 정리가 실행됐습니다. 복구 메시지뿐 아니라 OS의 RSS 감소도 확인했고, 이후 90초까지 실행됐습니다.

| 비교 | 256MB | 512MB |
| --- | --- | --- |
| 최대 관측 시간 / 관제 간격 | 90초 / 1초 | 90초 / 1초 |
| 실제 관측 결과 | 약 33.341초에 MemoryGuard 종료 | 캐시 복구 후 90초까지 생존 |
| OS RSS | 최대 274,312 KiB | 최대 530,268 KiB, 복구 직후 18,292 KiB |
| 핵심 메시지 | Memory limit exceeded, SELF-TERMINATED | Memory Cache Flushed, MEMORY RECOVERED |
| 수집기의 종료 개입 | 없음 | 관측 제한으로 수동 종료 |

발표 화면에서는 [256MB 종료 로그](evidence/oom-before-20261120T164708/app.log)의 `MemoryGuard`를 먼저 보여 주고, [512MB 복구 로그](evidence/oom-after-20261120T164741/app.log)의 `MEMORY RECOVERED`와 [RSS CSV](evidence/oom-after-20261120T164741/monitor.csv)의 16:48:46.204 표본을 연결해 설명한다. 상세 분석은 [메모리 보고서](reports/01-oom.md)에 있다.

결론은 **이 설정에서 보호 종료 회피와 캐시 복구를 확인했다**는 것이다. 정확한 누수 코드 위치를 찾아 수정했다거나 커널 OOM killer가 종료했다고 설명하지 않는다. 설정 변경에 따라 앱 내부 실행 경로도 달라졌으며, 전체 작업 구성이 완전히 동일했다고 주장하지 않는다.

### 3. CPU: 왜 관측 간격을 바꿨는가

설명할 개념은 **프로세스별 CPU 사용률, 짧은 피크와 긴 구간 평균의 차이, CPU 경쟁과 보호 정책**이다. CPU는 두 관측 사이에 해당 프로세스가 소비한 user·system CPU 시간의 증가량을 실제 경과 시간으로 나눠 계산했다. 논리 코어 하나를 100%로 해석하므로 컴퓨터 전체 CPU 사용률과 구분한다.

일반적으로 실행 가능한 작업이 CPU를 얻기 위해 경쟁하면 실행 대기와 응답 지연이 늘 수 있다. 이번 실험은 대상 PID의 짧은 피크와 Watchdog 종료를 확인했으며, 시스템 전체의 지속적 과부하나 체감 지연을 직접 입증한 실험은 아니다.

> 처음에는 1초 간격으로 관측해서 CPU 최대값이 약 5%로 보였습니다. 짧은 피크가 평균에 묻힐 가능성을 확인하려고 0.1초 간격으로 보완했고, 실제 작업 PID에서 약 49.4%의 피크를 포착했습니다. 별도로 수집한 top에서도 50%가 관측됐고, 종료 직전 WATCHDOG와 SIGTERM 메시지를 확보했습니다. 메모리 설정 512와 멀티스레드 false를 유지한 채 CPU 설정만 100에서 30으로 낮추자 피크가 약 29.7%로 낮아졌고, Watchdog 종료 없이 60초까지 실행됐습니다.

| 비교 | CPU 설정 100 | CPU 설정 30 |
| --- | --- | --- |
| 최대 관측 시간 / 관제 간격 | 60초 / 0.1초 | 60초 / 0.1초 |
| /proc 구간 CPU 최대값 | 49.366% | 29.736% |
| top의 단일 스레드 CPU 최대값 | 50.0% | 30.0% |
| 실제 관측 결과 | 약 21.228초에 Watchdog 종료 | cooldown을 반복하며 60초까지 생존 |
| 수집기의 종료 개입 | 없음 | 관측 제한으로 수동 종료 |

발표 화면에서는 [CPU CSV](evidence/cpu-before-20261120T164912/monitor.csv)의 16:49:33.381 표본 0%와 다음 16:49:33.482 표본 49.366%, [연속 top](evidence/cpu-before-20261120T164912/top-continuous.txt), [Watchdog 종료 로그](evidence/cpu-before-20261120T164912/app.log)를 함께 보여 준다. 변경 후에는 [cooldown 로그](evidence/cpu-after-20261120T164933/app.log)를 제시한다. 상세 분석은 [CPU 보고서](reports/02-cpu.md)에 있다.

같은 Before CSV에서 연속 10개 표본의 평균, 즉 약 1초 평균의 최댓값은 4.9366%다. 이는 짧은 피크가 긴 측정 구간에서 낮게 나타날 수 있다는 근거다. 앱 Load 52.16%, /proc 49.366%, top 50%는 서로 다른 지표·측정 창이므로 정확히 같은 수치라고 말하지 않는다. CPU 설정 100도 OS가 사용률 100%까지 보장하거나 제한한다는 뜻으로 해석하지 않는다. 실제 관측된 앱의 보호 동작을 기준으로 설명한다.

### 4. 데드락: 단순한 대기와 어떻게 구분했는가

핵심은 **PID가 살아 있다는 사실만으로 정상 동작이라고 판단할 수 없으며, 낮은 CPU만으로도 데드락을 확정할 수 없다**는 점이다. 자원을 보유하고 상대 자원을 기다리는 관계와 OS의 실제 대기 상태를 함께 확인했다.

> Thread-1은 Shared_Memory_A를 보유하고 Socket_Pool_B를 기다렸고, Thread-2는 Socket_Pool_B를 보유한 채 Shared_Memory_A를 기다렸습니다. 상대가 가진 자원이 필요해 서로 진행할 수 없는 순환 대기입니다. 프로세스는 살아 있었지만 로그가 BLOCKED 지점에서 멈췄고, 스레드들은 futex 대기 상태였습니다. 메모리와 CPU 설정을 유지한 채 MULTI_THREAD_ENABLE만 false로 바꾼 비교에서는 A·B·C 작업의 완료와 후속 작업 진행을 확인했습니다.

| 교착상태의 네 조건 | 이 실험에서 설명할 근거 |
| --- | --- |
| 상호 배제 | 자원 A와 B에 각각 LOCK ACQUIRED가 기록됐고 다른 스레드가 획득하지 못함 |
| 점유 대기 | 첫 자원을 보유한 상태로 상대의 두 번째 자원을 요청함 |
| 비선점 | 관측 중 자원 강제 회수·timeout 복구가 없었음. 내부 구현 전체의 보장을 확인한 것은 아님 |
| 순환 대기 | Thread-1 → B → Thread-2 → A → Thread-1 관계 |

발표 화면에서는 [자원 획득·BLOCKED 로그](evidence/deadlock-before-20261120T164121/app.log), [시각별 PID 생존](evidence/deadlock-before-20261120T164121/ps.txt), [스레드의 futex_do_wait](evidence/deadlock-before-20261120T164121/threads.txt), [변화가 멈춘 CPU·RSS](evidence/deadlock-before-20261120T164121/monitor.csv)를 순서대로 보여 준다. 변경 후에는 [작업 완료 로그](evidence/deadlock-after-20261120T164207/app.log)를 제시한다. 두 조건 모두 45초를 관측했다. 상세 분석은 [데드락 보고서](reports/03-deadlock.md)에 있다.

동시 처리 설정 변경으로 이번 교착상태를 회피한 것이며, 락 코드를 수정한 것은 아니다. 소스 수정이 가능한 상황의 근본 해결 방향은 모든 작업의 자원 획득 순서를 통일하고, 필요하면 제한 시간과 실패 시 자원 반환을 적용하는 것이다.

### 5. 작성한 수집 코드의 역할

| 파일·함수 | 질문을 받았을 때 설명할 내용 |
| --- | --- |
| [prepare.sh](scripts/prepare.sh)의 `_prepare()` | 일반 사용자·환경변수 범위를 검사하고 경로와 과제용 키를 준비함. 부트 실패와 실제 장애를 구분하기 위한 준비 단계 |
| [monitor.py](scripts/monitor.py)의 `_read_process()` | /proc/PID/stat에서 CPU tick, RSS 페이지 수, 스레드 수, 상태, 시작 시각을 읽음 |
| 같은 파일의 `_calculate_metrics()` | CPU 시간 증가량을 경과 시간으로 나눠 사용률을 계산하고, RSS 페이지 수를 KiB로 변환함 |
| 같은 파일의 `_monitor()` | 정해진 간격으로 CSV를 기록하고 종료·좀비 상태·PID 재사용을 감지해 수집을 끝냄 |
| [run_case.py](scripts/run_case.py)의 `_run_case()`·`_snapshot()` | 실행별 증거 폴더를 만들고 실제 작업 PID의 관제·ps·스레드·top 결과를 수집함 |
| 같은 파일의 `_drain_output()` | PTY 출력을 비차단 방식으로 저장해 급작스러운 종료 직전 터미널 메시지를 보존함 |

RSS는 `rss_pages × page_size ÷ 1024`로 KiB로 변환한다. CPU는 `CPU tick 증가량 ÷ 초당 tick 수 ÷ 실제 경과 초 × 100`으로 계산한다. 이 코드의 목적은 제공 프로그램의 장애를 측정하고 증거를 남기는 것이다.

### 6. 예상 질문과 답변

| 질문 | 답변 요지 |
| --- | --- |
| 프로그램이 꺼졌는데 왜 커널 OOM이라고 하지 않았나? | 앱의 MemoryGuard·자체 종료 메시지가 근거다. 커널 OOM 로그는 수집하지 않았으므로 커널의 종료로 단정하지 않았다. |
| 메모리 제한만 올리면 누수가 해결되나? | 일반적인 근본 해결은 아니다. 이번 앱에서는 512 설정에서 실제 캐시 복구와 RSS 감소를 관측했다. 내부 코드 수정 여부와 구분한다. |
| 60초·90초에 종료됐다는 것은 다시 장애가 난 것인가? | After는 관측 제한으로 수집기가 종료했다. metadata.json의 manual_stop=true가 이를 구분한다. 해당 시점까지 생존했다는 의미다. |
| -15라는 종료 코드만 보면 Watchdog인지 알 수 있나? | SIGTERM 사실만 알 수 있다. Watchdog 메시지와 manual_stop=false를 함께 확인했다. 수동 종료도 -15일 수 있다. |
| CPU가 낮고 로그가 멈추면 모두 데드락인가? | 정상적인 유휴·I/O 대기도 가능하다. 이번에는 상호 자원 보유·BLOCKED 로그와 futex 대기를 함께 확인했다. |
| 테스트 8개가 장애 재현 8회라는 뜻인가? | 아니다. 6개는 관제 파싱·계산, 2개는 터미널 출력 수집 검증이다. 실제 실행은 기동 확인 1회와 비교 실험 9회이며, 최종 보고서의 근거는 그중 6회다. |

마무리에서는 다음과 같이 설명한다.

> 장애를 증상만으로 분류하지 않고 로그, 프로세스 수치, 스레드 상태를 연결해 판단했습니다. 한 환경변수씩 변경해 조치 효과를 비교했고, 특히 관측 간격을 줄여 짧은 CPU 피크를 포착했습니다. 결과는 정해진 관측 시간 안의 검증이며 무기한 안정성이나 모든 내부 결함의 수정을 주장하지 않습니다.

PDF 5~6페이지의 스케줄링 추론은 선택 과제다. 예시의 Round-Robin 결론을 실제 결과로 사용하지 않는다. 보너스를 설명한다면 앱 로그의 작업 실행 순서에 대한 추론과 OS 스케줄러의 확정을 구분해야 하며, 현재 필수 보고서 3건의 결론에 OS 스케줄러 분석까지 포함했다고 말하지 않는다.

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
