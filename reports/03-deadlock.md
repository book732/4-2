# [Bug] Deadlock - 역순 자원 획득에 따른 순환 대기

상태: 순환 대기 재현과 설정 변경 후 회피를 45초 관측 범위에서 확인했다.

## 1. Description (현상 설명)

Ubuntu 26.04.1 LTS / WSL2 / x86-64, 일반 사용자 계정에서 MEMORY_LIMIT=512, CPU_MAX_OCCUPY=30, MULTI_THREAD_ENABLE=true로 실행했다. 런처 PID 1035, 실제 작업 PID 1036이다.

2026-11-20 16:41:30.986에 두 작업 스레드의 BLOCKED 로그가 나온 뒤 진행 로그가 멈췄다. 프로세스는 살아 있었고 45초 관측 종료 시점에 수집기가 종료했다.

## 2. Evidence & Logs (증거 자료)

- [Before 앱 로그](../evidence/deadlock-before-20261120T164121/app.log), [PID 생존](../evidence/deadlock-before-20261120T164121/ps.txt), [스레드 대기](../evidence/deadlock-before-20261120T164121/threads.txt), [CSV](../evidence/deadlock-before-20261120T164121/monitor.csv), [메타데이터](../evidence/deadlock-before-20261120T164121/metadata.json)
- [After 앱 로그](../evidence/deadlock-after-20261120T164207/app.log), [스레드 상태](../evidence/deadlock-after-20261120T164207/threads.txt), [CSV](../evidence/deadlock-after-20261120T164207/monitor.csv), [메타데이터](../evidence/deadlock-after-20261120T164207/metadata.json)

16:41:28.969에 Thread-1이 Shared_Memory_A 획득을 기록했고 Thread-2는 Socket_Pool_B 획득을 기록했다. 16:41:30.986에는 Thread-1이 B를, Thread-2가 A를 기다리는 WAITING ... (Status: BLOCKED) 로그가 각각 남았다.

16:41:32.379의 ps -L에서 PID/TID 1036·1044·1045가 모두 futex_do_wait로 관측됐다. 이후 시각이 다른 스냅샷에서도 PID가 유지됐고 RSS는 18,276 KiB, 구간 CPU는 대기 이후 0%로 정체됐다. 낮은 CPU만이 아니라 앱의 자원 획득·대기 관계와 OS 상태를 함께 근거로 삼았다.

## 3. Root Cause Analysis (원인 분석)

대기 관계는 Thread-1 → Socket_Pool_B → Thread-2 → Shared_Memory_A → Thread-1이다.

- 상호 배제: 각 자원에 LOCK ACQUIRED가 기록됐고 다른 스레드가 획득하지 못한다.
- 점유 대기: 첫 자원을 보유한 채 두 번째 자원을 요청한다.
- 비선점: 관측 구간 동안 강제 회수나 timeout 복구가 기록되지 않았다. 구현 자체의 비선점 보장은 확인하지 않았다.
- 순환 대기: 서로 보유한 자원을 반대 순서로 요청한다.

앱 로그는 자원 이름과 논리적 작업 스레드를, OS 스냅샷은 실제 대기를 보여 준다. 로그 이름과 개별 TID의 정확한 대응은 직접 계측하지 않았다. 소스나 바이너리 내부 분석 없이 이 실행의 순환 대기를 추론했다.

## 4. Workaround & Verification (조치 및 검증)

MULTI_THREAD_ENABLE만 false로 변경하고 메모리·CPU 설정, 1초 관제, 최대 관측 시간 45초는 유지했다.

| 항목 | Before | After |
| --- | --- | --- |
| MULTI_THREAD_ENABLE | true | false |
| 실제 작업 PID | 1036 | 1071 |
| 관측·종료 시간 | 45.371초 | 45.396초 |
| 수집기 수동 종료 | 예 | 예 |
| 최대 RSS | 18,276 KiB | 376,932 KiB |
| 구간 CPU 최대값 | 0.998% | 3.995% |
| 앱 진행 | 두 작업이 BLOCKED 후 정체 | A·B·C 작업 100% 완료, 후속 작업 진행 |

After에서 Healthy System Monitoring 경로의 All tasks completed와 이후 메모리·CPU 작업 로그가 관측됐다. 양쪽 SIGTERM은 수집기 관측 제한에 따른 수동 종료다. 단일 스레드 설정은 이 조건에서의 회피이며, 메모리 누수·CPU 문제의 근본 수정이나 장기 안정성을 입증하지 않는다.

내부 소스 변경이 가능한 담당자에게는 자원 획득 순서를 모든 경로에서 통일하고 필요하면 제한 시간과 실패 시 자원 반환을 적용할 것을 제안한다. 제공 실행 파일은 수정하지 않았다.
