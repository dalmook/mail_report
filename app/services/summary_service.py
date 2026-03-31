from __future__ import annotations

import logging
from typing import Any

from ..config import settings
from ..schemas import summary_to_dict, validate_summary_payload
from .auto_tagger import suggest_tags
from .llm_summarizer import LLMService
from .repository import apply_auto_tags, get_attachments, get_message, upsert_summary

logger = logging.getLogger(__name__)


class SummaryService:
    def __init__(self, llm: LLMService | None = None) -> None:
        self.llm = llm or LLMService()

    def summarize_message(self, message_id: int, force: bool = False, max_attempts: int = 2) -> dict[str, Any]:
        row = get_message(message_id)
        if not row:
            raise ValueError('Message not found')

        body = row['text_body'] or row['body_preview'] or ''
        if row['html_body'] and not row['text_body']:
            body = row['html_body'][:12000]

        attachments = get_attachments(message_id)
        attach_hint = ', '.join([f"{a['filename']}({a['content_type']})" for a in attachments[:8]])
        if attach_hint:
            body += f'\n\n[첨부파일]\n{attach_hint}'

        attempt = 0
        last_error: str | None = None
        while attempt < max_attempts:
            attempt += 1
            try:
                raw = self.llm.summarize_mail(row['subject'], body)
                validated = validate_summary_payload(raw)
                normalized = summary_to_dict(validated)

                suggestions = suggest_tags(
                    subject=row['subject'],
                    body_preview=row['body_preview'] or '',
                    from_email=row['from_email'] or '',
                    has_attachment=bool(row['has_attachment']),
                    summary_tags=normalized.get('tags', []),
                    keywords=normalized.get('keywords', []),
                    category=normalized.get('category', '기타'),
                    importance_score=normalized.get('importance_score', 0),
                )
                normalized['tags'] = sorted(set(normalized.get('tags', []) + [s.tag for s in suggestions]))
                normalized['tag_reasons'] = {s.tag: s.reason for s in suggestions}

                upsert_summary(
                    message_id,
                    settings.llm_model,
                    normalized,
                    raw,
                    retry_count=attempt - 1,
                    reason='resummarize' if force else 'summarize',
                )
                apply_auto_tags(message_id, suggestions)
                return {'ok': True, 'attempt': attempt, 'summary': normalized}
            except Exception as exc:
                last_error = str(exc)
                logger.warning('summarize_message failed: message_id=%s attempt=%s force=%s err=%s', message_id, attempt, force, exc)

        fallback = {
            'summary_short': (row['body_preview'] or '요약 실패')[:120],
            'summary_long': f'LLM 요약 실패로 원문 미리보기를 대신 저장했습니다.\n오류: {last_error}',
            'keywords': [],
            'risks': ['요약 실패로 리스크 자동 산출 불가'],
            'action_items': ['운영자가 수동 검토 필요'],
            'category': '기타',
            'status': 'flagged',
            'tags': ['요약실패'],
            'tag_reasons': {'요약실패': 'LLM parsing/API failed'},
            'importance_score': 70 if force else 50,
            'entities_people': [],
            'entities_orgs': [],
            'deadlines': [],
            'numeric_facts': [],
        }
        upsert_summary(message_id, settings.llm_model, fallback, {'error': last_error}, retry_count=max_attempts, reason='fallback')
        return {'ok': False, 'attempt': max_attempts, 'error': last_error, 'summary': fallback}
