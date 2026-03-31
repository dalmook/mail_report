# Changelog

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
