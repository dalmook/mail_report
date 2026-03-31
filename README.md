# Mail Archive Operator Console v2

로컬 PC에서 실행하는 FastAPI 기반 메일 아카이브 운영 콘솔입니다.

## 목표
- POP3 메일을 안전하게 수집하고 원본 EML을 우선 보존
- 메일 파싱/첨부 분리/메타데이터 저장을 안정적으로 수행
- GPT-OSS 요약 결과를 구조화해서 운영자가 매일 검토 가능하게 제공
- 로컬-퍼스트(단일 FastAPI + SQLite + 파일 스토리지) 유지

## 아키텍처
- `app/main.py`: 앱 초기화, 글로벌 예외 처리, 라우터 조립
- `app/routers/pages.py`: 대시보드/목록/상세 화면 라우팅
- `app/routers/actions.py`: 수집/요약/재요약/링크/다운로드 액션
- `app/services/pop3_ingest.py`: POP3 -> EML 저장 -> 파싱 -> DB 저장 파이프라인
- `app/services/eml_parser.py`: MIME 파싱, 제목/본문 디코딩, 스레드 키 계산
- `app/services/summary_service.py`: 요약 재시도 + fallback + DB 저장 orchestration
- `app/services/llm_summarizer.py`: GPT-OSS 호출과 응답 파싱
- `app/services/repository.py`: 조회/저장 query 계층
- `app/db.py`: SQLite 스키마/마이그레이션 보정

## Local setup
1. Python 3.11+ 권장
2. 가상환경 생성 후 의존성 설치
   - `pip install -r requirements.txt`
3. `.env.example`를 `.env`로 복사 후 값 설정
4. 실행
   - `python -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload`
5. 접속
   - `http://127.0.0.1:8010`

## 테스트
- `pytest -q`
- `python -m compileall app tests`

## 운영 메모
- 비밀값(POP3 계정, LLM credential)은 `.env`만 사용
- 요약 실패 시 fallback summary를 저장하고 `jobs`에 실패 이력을 남김
- 기존 DB가 있어도 `init_db()`에서 필요한 컬럼 보강을 시도함
