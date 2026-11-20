# 실험 증거

실행별 하위 폴더에 원본 로그를 보관한다. 원본은 덮어쓰지 않는다.

- `app.log`: 프로그램 표준 출력·오류
- `monitor.csv`: PID별 CPU·RSS·스레드 관측값
- `metadata.json`: 실험 환경변수, 시작·종료 시각, 런처·작업 PID, 종료 코드, 수동 종료 여부
- `ps.txt`, `threads.txt`: 시각별 프로세스 및 스레드 상태
- `top.txt`: CPU 급상승 또는 정체 구간의 `top -H` 출력
- `top-continuous.txt`: 보완 CPU 실험의 0.1초 연속 스레드 관측
- `application/`: `AGENT_LOG_DIR`에 프로그램이 직접 기록한 로그

케이스별로 `oom-before`, `oom-after`, `cpu-before`, `cpu-after`, `deadlock-before`, `deadlock-after`를 구분한다. 같은 조건을 재실행하면 별도 폴더를 사용한다. 초기 CPU Before는 다른 케이스를 재사용했지만 최종 보완 보고서는 별도 CPU Before/After 실행을 사용한다. 최종 근거 6회는 [실험 요약](../docs/experiment-summary.md)에 연결했다. `startup-*`는 18초 기동 확인으로, 수동 종료한 탐색 실험이다.

보고서의 재현 근거인 원본 로그를 Git에 포함한다. `.gitattributes`의 `evidence/** -text` 설정으로 원본 바이트를 보존한다. 실행 키 파일은 `.runtime/`에서 관리하며 Git에 포함하지 않는다.
