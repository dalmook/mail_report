# Changelog

## v2.1.0 - 2026-03-31
- 라우팅 계층 분리(`routers/pages.py`, `routers/actions.py`) 및 예외/로깅 정리.
- POP3 처리에서 원본 EML 우선 저장 보장 후 파싱/DB 저장 수행.
- 요약 오케스트레이션 서비스(`summary_service.py`) 추가: 재시도 + fallback 저장.
- `tags`, `message_tags` 테이블 추가 및 태그 동기화 로직 추가.
- summaries에 `retry_count` 추가.
- dedup/summary parsing 테스트 추가.

## v2.0.0 - 2026-03-31
- 아키텍처 리팩터링: config/schema/service/repository 역할 분리.
- POP3→EML→파싱→DB 파이프라인의 메타데이터 확장(subject_normalized, in_reply_to, references_header, source_mailbox).
- 스레드 키 전략 개선(In-Reply-To/References 우선, fallback to normalized subject).
- LLM 요약 스키마 확장(status/tags) 및 서버측 검증 추가.
- 관리자 재요약 액션(`/actions/resummarize/{message_id}`) 추가.
- 대시보드/목록/상세 화면 정보구조 개선(카드형 지표, 운영 상태, 액션 강조).
- 외부 링크 관리 UX 개선.
- critical parsing unit tests 추가.
- 로컬 실행 문서 및 `.env.example` 추가.
