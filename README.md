# Mail Archive Operator Console v5 (local-first)

로컬 FastAPI + SQLite로 운영되는 메일 기반 준운영 시스템입니다.

## v5 핵심 자동화
- 자동 파이프라인: 수집 -> 요약 -> 자동태깅 -> 이슈후보화 -> 주간/월간 리포트 생성
- 수동/자동 동시 지원(운영자가 즉시 실행 가능 + 스케줄러 주기 실행)
- 운영관리 패널에서 상태/실패/재시도/후보/파이프라인 이력/스토리지 진단 확인

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
3. `/messages`에서 퀵필터로 중요/실패/리스크/후보 메일 우선 처리
4. 메일 상세에서 태그/상태 수정, 이슈 승격
5. `/issues`에서 마감/담당/우선순위 정리
6. 주간/월간 리포트 생성 및 회의 초안으로 활용

## Local setup
1. `pip install -r requirements.txt`
2. `.env.example` -> `.env` 복사 후 값 입력
3. `python -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload`
4. 브라우저 `http://127.0.0.1:8010`

## 장기 실행/백업 팁
- DB: `data/archive.db` 주기 백업 + 월 1회 `VACUUM` 권장
- 원본: `storage/eml`, `storage/attachments` 폴더 정기 백업
- 운영관리 패널에서 스토리지 누락 진단 수치 정기 확인
- 절전모드/네트워크 절전으로 인한 자동작업 중단 주의

## 테스트
- `pytest -q`
- `python -m compileall app tests`
