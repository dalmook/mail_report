# Mail Archive Operator Console v4 (local-first)

로컬 PC에서 실행하는 FastAPI + SQLite 기반 **메일 운영 지원 도구**입니다.

## 이번 단계 핵심
- 메일 자동 태깅(LLM + 규칙 기반) 및 태그 근거 저장
- 메일을 이슈로 승격하고 상태/담당/마감/우선순위 관리
- 주간/월간 리포트 집계 + 리포트 요약 텍스트 저장
- 대시보드에서 즉시 액션 가능한 운영 우선순위 제공

## 주요 화면
- `/` : 운영 대시보드
- `/messages` : 메일 큐
- `/messages/{id}` : 메일 상세 + 이슈 생성/태그/상태/링크/관련 메일
- `/issues` : 이슈 목록
- `/issues/{id}` : 이슈 상세/편집/이력
- `/reports/weekly`, `/reports/monthly` : 기간 리포트

## 운영 흐름 (권장)
1. 대시보드에서 POP3 수집
2. 요약 실패 일괄 재처리
3. 메일 상세에서 상태/태그/중요표시 정리
4. 이슈 승격(담당/마감/우선순위 지정)
5. 주간/월간 리포트 생성 후 팀 공유

## Local setup
1. `pip install -r requirements.txt`
2. `.env.example` 를 `.env`로 복사
3. `python -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload`
4. 브라우저: `http://127.0.0.1:8010`

## 장기 실행 주의사항
- `data/archive.db`, `storage/` 주기 백업
- `.env` 자격증명 주기 점검
- OS 절전 모드로 인한 스케줄 중단 주의
- 월 1회 이상 DB vacuum/백업 권장

## 테스트
- `pytest -q`
- `python -m compileall app tests`
