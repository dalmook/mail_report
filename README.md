# Mail Archive Operator Console v3 (local-first)

로컬 PC에서 장기 실행 가능한 FastAPI + SQLite 메일 운영 도구입니다.

## 핵심 운영 기능
- POP3 수집 시 원본 EML 우선 저장(파싱 실패 시에도 원본 보존)
- 요약 실패 메일 재처리(개별/일괄)
- 상태(new/reviewed/flagged/archived), 중요 표시, 태그 운영
- 링크 관리(추가/삭제)
- 스레드/관련 메일/요약 이력 기반 추적
- 운영 지표 중심 대시보드(기간별 수집, 실패, 중요/리스크, 발신자 TOP)

## 아키텍처
- `app/main.py`: 앱 초기화/예외 처리/라우터 조립
- `app/routers/pages.py`: 대시보드/목록/상세
- `app/routers/actions.py`: 운영 액션(수집/요약/태그/상태/링크)
- `app/services/pop3_ingest.py`: POP3 -> EML -> parse -> DB 파이프라인
- `app/services/summary_service.py`: 요약 재시도/fallback/저장
- `app/services/repository.py`: 조회/저장/운영 쿼리
- `app/db.py`: SQLite 스키마 + migration 보정

## Local setup
1. Python 3.11+ 권장
2. 가상환경 및 설치
   - `pip install -r requirements.txt`
3. `.env.example` -> `.env` 복사 후 설정
4. 실행
   - `python -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload`
5. 접속
   - `http://127.0.0.1:8010`

## 운영 순서(권장)
1. 대시보드에서 `POP3 수집 실행`
2. 목록 화면에서 필터(발신자/기간/상태/중요도/태그/요약실패순)로 큐 정렬
3. 상세 화면에서 상태/태그/중요 표시/링크 정리
4. 실패 또는 품질 미흡 메일 재요약
5. 대시보드의 재요약 대상/리스크 높은 메일 카드 재점검

## 테스트
- `pytest -q`
- `python -m compileall app tests`

## 장기 실행 주의사항 (로컬 PC)
- SQLite 파일/`storage/` 폴더 주기 백업
- 주기적으로 오래된 첨부/EML 보관정책 점검
- POP3 계정 비밀번호 변경 시 `.env` 즉시 갱신
- 장시간 실행 시 OS 절전모드/네트워크 절전 해제 권장
