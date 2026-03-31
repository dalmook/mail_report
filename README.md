# Mail Archive FastAPI MVP

로컬 PC에서 실행하는 메일 아카이브 웹앱입니다.

## 포함 기능
- POP3 수집
- 원본 EML 저장
- SQLite 메타데이터 저장
- 메일 목록 / 상세 / 첨부 다운로드
- GPT-OSS 요약 / 키워드 / 리스크 / 액션아이템
- 대시보드
- 메일별 외부 링크 저장

## 빠른 시작
1. 가상환경 생성
2. `pip install -r requirements.txt`
3. `.env.example` 를 `.env` 로 복사 후 값 입력
4. `python -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload`
5. 브라우저에서 `http://127.0.0.1:8010`

## 비밀값
- POP3 비밀번호
- GPT-OSS credential

위 값들은 코드에 하드코딩하지 말고 `.env` 에만 보관하세요.

## 참고
LLM 호출부는 사용자가 업로드한 GPT-OSS 예제의 헤더 구조와 payload 형식을 참고해 FastAPI 서비스 형태로 옮긴 것입니다.
