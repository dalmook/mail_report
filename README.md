# Mail Archive Operator Console v2

로컬 환경에서 운영자가 메일 흐름을 점검하는 FastAPI 기반 메일 아카이브 애플리케이션입니다.

## 핵심 기능
- POP3 수집 → 원본 EML 저장 → 메타데이터/본문 파싱 → SQLite 저장 파이프라인
- GPT-OSS 기반 요약/리스크/액션아이템/카테고리/상태/태그 추출
- 운영자 중심 대시보드(미요약/조치 필요/고중요도 등 액션 지표)
- 메시지 목록 필터(카테고리/요약유무/상태/태그) + 상세 뷰
- 스레드 뷰 + 외부 링크 저장 + 관리자 재요약 액션
- 로컬-퍼스트 실행(단일 프로세스, SQLite, 로컬 파일 저장)

## Local setup
1. Python 3.11+ 권장
2. 가상환경 생성 후 의존성 설치
   - `pip install -r requirements.txt`
3. `.env.example`를 `.env`로 복사 후 값 설정
4. 서버 실행
   - `python -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload`
5. 브라우저 접속
   - `http://127.0.0.1:8010`

## 테스트
- `pytest`

## 디렉터리
- `app/main.py`: 라우팅/액션
- `app/services/pop3_ingest.py`: POP3 ingestion pipeline
- `app/services/eml_parser.py`: EML 파싱 및 스레드 키 계산
- `app/services/llm_summarizer.py`: GPT-OSS API 연동
- `app/services/repository.py`: 조회/저장 쿼리 레이어
- `app/schemas.py`: 요약 스키마 검증
- `app/templates/*`: 운영 화면 템플릿

## 보안/운영 메모
- POP3/LLM credential은 반드시 `.env`에만 저장
- 클라우드 배포/외부 문서 시스템 연동은 본 저장소 범위 밖(로컬 운영 전용)
