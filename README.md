# Mail Archive Operator Console v5 (local-first)

로컬 FastAPI + SQLite 기반 메일 운영 시스템입니다.

## 핵심 자동화
- 자동 파이프라인: 수집 -> 요약 -> 자동태깅 -> 이슈후보화 -> 주간/월간 리포트 갱신
- 수동/자동 동시 지원(운영자가 즉시 실행 가능 + 스케줄러 주기 실행)
- 주간 리포트를 신문형 HTML로 생성하고 SMTP 메일 발송 가능

## 주요 화면
- `/` 대시보드
- `/messages` 메일 큐(퀵필터 포함)
- `/messages/{id}` 메일 상세 + 이슈 생성
- `/issues`, `/issues/{id}` 이슈 운영
- `/reports/weekly`, `/reports/monthly` 기간 리포트
- `/admin/ops` 운영관리 패널

## 운영 흐름(권장)
1. `/admin/ops`에서 운영 상태 확인
2. 필요 시 `전체 파이프라인 실행`
3. 요약 실패/리스크/이슈후보 메일을 퀵필터로 우선 처리
4. 이슈 승격 및 담당/마감 관리
5. 주간 리포트 생성 + 뉴스레터 발송

## Local setup
1. `pip install -r requirements.txt`
2. `.env.example` -> `.env` 복사 후 값 입력
3. `python -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload`
4. 브라우저 `http://127.0.0.1:8010`

## 뉴스레터 메일 발송 설정
- `.env`에서 아래 값 설정:
  - `SMTP_ENABLED=true`
  - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USE_TLS`, `SMTP_USER`, `SMTP_PASS`
  - `REPORT_FROM_EMAIL`, `REPORT_TO_EMAILS`
- 자동 주간 발송:
  - `WEEKLY_REPORT_AUTO_SEND=true`
  - `WEEKLY_REPORT_SEND_WEEKDAY` (0=월 ... 6=일)
  - `WEEKLY_REPORT_SEND_HOUR` (24시간)

## 장기 실행/백업 팁
- DB: `data/archive.db` 주기 백업 + 월 1회 `VACUUM`
- 원본: `storage/eml`, `storage/attachments` 정기 백업
- 운영관리 패널에서 스토리지 누락 진단 정기 확인

## 테스트
- `pytest -q`
- `python -m compileall app tests`
