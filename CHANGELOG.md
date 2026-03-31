# Changelog

## v3.0.0 - 2026-03-31
- 운영 중심 고도화: 대시보드 지표(기간별 수집/요약완료율/실패/중요/액션아이템/발신자 TOP/리스크/재요약 대상) 추가.
- 목록 탐색성 강화: 발신자/기간/카테고리/태그/첨부/요약여부/중요도범위/상태 필터 + 정렬 옵션.
- 상세 운영 액션 강화: 상태 변경, 중요 표시, 태그 추가/삭제, 실패 일괄 재요약.
- 스레드/관련 메일/요약 이력(summary_history) 추가로 추적성 강화.
- summaries 스키마 확장(entities/deadlines/numeric facts/retry_count), messages `is_important` 추가.
- SQLite 최적화(PRAGMA WAL/NORMAL), 인덱스 추가, migration 보강.
- parser/dedup/summarizer 파싱 테스트 외 운영 로직 회귀 안정화.

## v2.1.0 - 2026-03-31
- 라우팅 계층 분리(`routers/pages.py`, `routers/actions.py`) 및 예외/로깅 정리.
- POP3 처리에서 원본 EML 우선 저장 보장 후 파싱/DB 저장 수행.
- 요약 오케스트레이션 서비스(`summary_service.py`) 추가: 재시도 + fallback 저장.
- `tags`, `message_tags` 테이블 추가 및 태그 동기화 로직 추가.
- summaries에 `retry_count` 추가.
- dedup/summary parsing 테스트 추가.
