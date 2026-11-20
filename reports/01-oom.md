# [Bug] OOM - 메모리 제한 변경 전후 보호 종료와 캐시 복구 비교

상태: MEMORY_LIMIT만 변경하는 보완 실험 완료. 512MB에서 캐시 복구와 90초 생존을 확인했다.

## 1. Description (현상 설명)

Ubuntu 26.04.1 LTS / WSL2 / x86-64, 일반 사용자 last_(uid=1000), Python 3.14.4에서 제공 실행 파일을 관측했다. CPU_MAX_OCCUPY=30, MULTI_THREAD_ENABLE=false, 관제 간격 1초, 최대 관측 시간 90초를 고정하고 MEMORY_LIMIT만 256/512로 변경했다.

256MB 조건은 약 33.341초 후 MemoryGuard로 종료됐다. 512MB 조건은 같은 25MB 증가 패턴 이후 캐시 정리로 회복됐고 90초 관측 종료까지 실행됐다. 해당 시점에는 수집기가 종료했다.

## 2. Evidence & Logs (증거 자료)

- [256MB 앱 로그](../evidence/oom-before-20261120T164708/app.log), [CSV](../evidence/oom-before-20261120T164708/monitor.csv), [ps](../evidence/oom-before-20261120T164708/ps.txt), [메타데이터](../evidence/oom-before-20261120T164708/metadata.json)
- [512MB 앱 로그](../evidence/oom-after-20261120T164741/app.log), [CSV](../evidence/oom-after-20261120T164741/monitor.csv), [ps](../evidence/oom-after-20261120T164741/ps.txt), [메타데이터](../evidence/oom-after-20261120T164741/metadata.json)

256MB의 실제 작업 PID는 1212다. Heap이 25MB에서 약 3초마다 25MB씩 증가했고, 2026-11-20 16:47:41.009에 275MB에 도달했다. 종료 직전 실제 로그:

> 16:47:41.011 [CRITICAL] [MemoryGuard] Memory limit exceeded (275MB >= 256MB)
>
> 16:47:41.012 [CRITICAL] [MemoryGuard] Self-terminating process 1212 to prevent system instability.
>
> [SYSTEM] SELF-TERMINATED (Memory Limit Exceeded)

512MB에서도 MemoryWorker의 동일한 25MB 증분 패턴을 관측했다. 이후 실제 로그:

> 16:48:45.603 [INFO] [MemoryWorker] Current Heap: 525MB
>
> 16:48:45.604 [WARNING] [MemoryWorker] Memory Usage Reached Limit (525MB). Starting cleanup...
>
> 16:48:45.634 [INFO] [System] Memory Cache Flushed. Process Stabilized.
>
> [SYSTEM] MEMORY RECOVERED (Cache Cleared)

512MB 조건의 OS RSS 최대 관측값은 530,268 KiB였다. 복구 메시지 직후 16:48:46.204의 RSS는 18,292 KiB로 감소했다. 이어 16:48:50.670에 Heap 25MB부터 작업이 다시 진행됐다.

## 3. Root Cause Analysis (원인 분석)

256MB 조건에서는 누적 메모리가 앱 임계값을 넘어 MemoryGuard가 자체 종료를 명시했고, 수집기 개입 없이 SIGKILL이 관측됐다. 반환값 -9는 Python subprocess의 신호 종료 표기이며 셸의 137과 구분한다. 이 근거는 앱의 보호 종료를 지지하며 커널 OOM killer가 종료했다고 판단하지 않는다. 커널 OOM 로그는 수집하지 않았다.

512MB 조건에서는 단순히 더 오래 메모리를 쌓다가 종료된 것이 아니라 앱의 캐시 정리 경로가 실행됐다. 복구 메시지와 실제 RSS 감소를 함께 확인했다. 따라서 이 앱에서 MEMORY_LIMIT는 관측된 보호·복구 동작에도 영향을 주는 설정이며, 임계값 변경 효과를 생존 시간만으로 설명하지 않는다.

동일한 MemoryWorker 증분 패턴을 비교했지만 전체 내부 실행 경로가 같다는 뜻은 아니다. 512MB 조건에서는 정상 감시·CPU 작업도 관측됐다. 입력 조건 중 MEMORY_LIMIT만 변경했으며, 내부 분기·객체 해제 구현이나 정확한 누수 코드 위치는 분석하지 않았다.

## 4. Workaround & Verification (조치 및 검증)

| 항목 | Before | After |
| --- | --- | --- |
| MEMORY_LIMIT | 256MB | 512MB |
| CPU_MAX_OCCUPY / MULTI_THREAD_ENABLE | 30 / false | 30 / false |
| 실제 작업 PID | 1212 | 1237 |
| 관제 간격 / 최대 관측 시간 | 1초 / 90초 | 1초 / 90초 |
| 관측 종료까지 경과 시간 | 33.341초 | 90.400초 |
| 최대 RSS | 274,312 KiB | 530,268 KiB |
| 복구 직후 RSS | 복구 전 종료 | 18,292 KiB |
| 종료·복구 근거 | MemoryGuard, SELF-TERMINATED | cleanup, MEMORY RECOVERED |
| 반환값 / 수집기 수동 종료 | -9 / 아니오 | -15 / 예 |

MEMORY_LIMIT=512 설정으로 이 실험의 보호 종료를 회피했고, 복구 후 재진행과 최소 90초 생존을 확인했다. After의 SIGTERM은 관측 제한에 따른 수동 종료이며 앱 오류가 아니다. 무기한 안정성이나 일반적인 메모리 누수의 근본 수정으로 확대 해석하지 않는다.

재현은 프로젝트 루트에서 prepare.sh를 적용한 뒤 run_case.py의 oom-before/oom-after를 각각 memory 256/512, cpu 30, threads false, seconds 90, interval 1로 실행한다. 제공 바이너리는 수정하지 않았다.
