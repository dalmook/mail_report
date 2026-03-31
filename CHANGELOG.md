# Changelog

## v4.0.0 - 2026-03-31
- 자동 태깅 고도화: LLM 결과 + 규칙 기반 태그 추천/적용(`중요/보고/일정/리스크/장애/요청/회의/첨부중요/고객/내부/운영/기타`).
- 태그 근거 저장(`tag_reasons_json`, `message_tags.reason/source/confidence`).
- 이슈화 기능 추가: `issues`, `issue_events` 테이블 및 생성/수정/조회 화면.
- 주간/월간 리포트 구조 추가: `period_summaries` 테이블, 기간 집계와 리포트 화면.
- 대시보드 액션성 강화: 오늘 확인할 메일, 요약 실패, 리스크 메일, 최근 이슈, 마감 임박 이슈, 주간 요약.
- 메일 상세에서 이슈 생성/관련 이슈 조회/태그 근거 표시 추가.
- SQLite 인덱스 및 WAL 기반 장기 운영 안정성 보강.
- 자동 태깅/이슈+리포트 테스트 추가.

## v3.0.0 - 2026-03-31
- 운영 중심 고도화: 대시보드 지표(기간별 수집/요약완료율/실패/중요/액션아이템/발신자 TOP/리스크/재요약 대상) 추가.
- 목록 탐색성 강화: 발신자/기간/카테고리/태그/첨부/요약여부/중요도범위/상태 필터 + 정렬 옵션.
- 상세 운영 액션 강화: 상태 변경, 중요 표시, 태그 추가/삭제, 실패 일괄 재요약.
- 스레드/관련 메일/요약 이력(summary_history) 추가로 추적성 강화.
- summaries 스키마 확장(entities/deadlines/numeric facts/retry_count), messages `is_important` 추가.
- SQLite 최적화(PRAGMA WAL/NORMAL), 인덱스 추가, migration 보강.
- parser/dedup/summarizer 파싱 테스트 외 운영 로직 회귀 안정화.
