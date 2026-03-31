# Changelog

## v5.0.0 - 2026-03-31
- 자동 파이프라인 서비스(`PipelineService`) 추가: 수집→요약→자동태깅→이슈후보→기간리포트 자동화.
- 스케줄러를 full pipeline 기반으로 전환(자동 실행 + 수동 즉시 실행 병행).
- 운영관리 화면(`/admin/ops`) 추가: 마지막 성공/실패, 실패건수, 재시도 대기, 미요약/요약실패, 후보 미검토, 파이프라인 이력.
- `issue_candidates` + 후보 검토 흐름(`PENDING/REVIEWED/REJECTED/CONVERTED`) 추가.
- 검색 품질 강화: 제목/본문/요약/태그/카테고리/발신자 통합 검색.
- 메일 큐 퀵필터 추가(오늘 중요/요약실패/리스크/이슈후보).
- 리포트 생성 액션 강화 및 주간/월간 summary text 자동 저장.
- storage/DB 경로 불일치 진단 로직 추가.
- DB 스키마 확장: `pipeline_runs`, `issue_candidates`, `summaries.confidence_score` 등.

## v4.0.0 - 2026-03-31
- 자동 태깅 고도화: LLM 결과 + 규칙 기반 태그 추천/적용(`중요/보고/일정/리스크/장애/요청/회의/첨부중요/고객/내부/운영/기타`).
- 태그 근거 저장(`tag_reasons_json`, `message_tags.reason/source/confidence`).
- 이슈화 기능 추가: `issues`, `issue_events` 테이블 및 생성/수정/조회 화면.
- 주간/월간 리포트 구조 추가: `period_summaries` 테이블, 기간 집계와 리포트 화면.
- 대시보드 액션성 강화: 오늘 확인할 메일, 요약 실패, 리스크 메일, 최근 이슈, 마감 임박 이슈, 주간 요약.
