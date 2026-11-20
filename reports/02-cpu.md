# [Bug] CPU - 짧은 CPU 피크 및 Watchdog 보호 종료

상태: 0.1초 OS 관제와 연속 top으로 피크를 확인하고, 명시적 Watchdog 종료 로그와 설정 변경 후 회피를 확보했다.

## 1. Description (현상 설명)

Ubuntu 26.04.1 LTS / WSL2 / x86-64의 일반 사용자 계정에서 MEMORY_LIMIT=512, MULTI_THREAD_ENABLE=false, 관제 간격 0.1초, 최대 관측 시간 60초를 고정하고 CPU_MAX_OCCUPY만 100/30으로 변경했다. 두 조건은 각각 별도 실행했다.

100 조건은 약 21.228초에 CPU 임계 위반과 Watchdog 메시지를 남기고 SIGTERM으로 종료됐다. 30 조건은 cooldown을 반복하며 60초 관측 종료까지 생존했다.

## 2. Evidence & Logs (증거 자료)

- [Before 앱 로그](../evidence/cpu-before-20261120T164912/app.log), [0.1초 CSV](../evidence/cpu-before-20261120T164912/monitor.csv), [연속 top](../evidence/cpu-before-20261120T164912/top-continuous.txt), [ps](../evidence/cpu-before-20261120T164912/ps.txt), [메타데이터](../evidence/cpu-before-20261120T164912/metadata.json)
- [After 앱 로그](../evidence/cpu-after-20261120T164933/app.log), [0.1초 CSV](../evidence/cpu-after-20261120T164933/monitor.csv), [연속 top](../evidence/cpu-after-20261120T164933/top-continuous.txt), [메타데이터](../evidence/cpu-after-20261120T164933/metadata.json)

Before의 실제 작업 PID는 1325다. 2026-11-20 16:49:33.381 표본은 OS CPU 0.0%, 바로 다음 16:49:33.482 표본은 49.366%였다. 연속 top에서도 해당 단일 작업 스레드의 50.0% 피크가 관측됐다.

종료 직전 실제 앱 로그:

> 16:49:33.403 [INFO] [CpuWorker] Current Load: 52.16%
>
> 16:49:33.505 [CRITICAL] [CpuWorker] CPU Threshold Violated! (52.16%).
>
> [SYSTEM] WATCHDOG: INITIATING EMERGENCY ABORT (SIGTERM)

Before의 returncode=-15, manual_stop=false다. After에서는 다음이 기록됐다.

> 16:49:54.564 [INFO] [CpuWorker] Peak reached (30.00%). Starting cooldown...
>
> 16:50:07.033 [INFO] [CpuWorker] Cooldown complete (5.00%). Resuming load increase...

## 3. Root Cause Analysis (원인 분석)

임계 위반 직후 앱이 Watchdog 보호 종료를 명시했고 수집기 개입 없이 SIGTERM 종료가 뒤따랐다. 따라서 일반적인 비정상 크래시와 구분되는 앱 내부 보호 동작으로 판단한다. 실제 종료 함수나 신호 시스템 콜을 추적한 것은 아니다.

초기 1초 관제는 최대 약 5%만 포착했다. 보완 실험에서는 0.1초 단위로 약 49.4%의 짧은 피크가 관측됐고 top도 50%를 기록했다. 같은 Before CSV에서 10개 연속 표본의 평균(약 1초)의 최댓값은 4.9366%다. 이는 짧은 피크가 긴 구간 평균에서 낮게 나타나는 이유를 설명한다. 10표본 평균은 정확히 1.000초에 정렬된 CPU 측정과는 구분한다.

앱 Load 52.16%, /proc 구간 CPU 49.366%, top 50.0%는 서로 다른 측정 창과 계산 기준의 값이다. 같은 값이라고 단정하지 않는다. 확인한 것은 대상 PID의 짧은 CPU 상승이며 시스템 전체 CPU가 지속적으로 과점유됐거나 사용자의 체감 지연이 발생했다는 증거는 수집하지 않았다.

## 4. Workaround & Verification (조치 및 검증)

| 항목 | Before | After |
| --- | --- | --- |
| CPU_MAX_OCCUPY | 100% | 30% |
| MEMORY_LIMIT / MULTI_THREAD_ENABLE | 512 / false | 512 / false |
| 실제 작업 PID | 1325 | 1341 |
| 관제 간격 / 최대 관측 시간 | 0.1초 / 60초 | 0.1초 / 60초 |
| 관측 종료까지 경과 시간 | 21.228초 | 60.413초 |
| /proc 구간 CPU 최대값 | 49.366% | 29.736% |
| top의 단일 스레드 CPU 최대값 | 50.0% | 30.0% |
| 관제 표본 수 | 205 | 592 |
| 앱 동작 | 52.16% 후 WATCHDOG | 30.00% 후 cooldown |
| 반환값 / 수집기 수동 종료 | -15 / 아니오 | -15 / 예 |

30 조건에서는 관측된 피크가 낮아졌고 Watchdog 종료 없이 최소 60초 실행됐다. After의 SIGTERM은 수집기가 관측을 끝내기 위해 보낸 것으로 앱 보호 종료가 아니다. 단일 실행쌍의 비교이며 종료 시점은 반복 실험에서 달라질 수 있다. 메모리 누수 수정이나 무기한 안정성으로 해석하지 않는다.

재현은 prepare.sh 적용 후 run_case.py의 cpu-before/cpu-after를 각각 cpu 100/30, memory 512, threads false, seconds 60, interval 0.1로 실행한다. 제공 바이너리는 수정하지 않았다.
