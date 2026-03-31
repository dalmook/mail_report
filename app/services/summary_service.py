from __future__ import annotations

import logging
from typing import Any

from ..config import settings
from ..schemas import summary_to_dict, validate_summary_payload
from .llm_summarizer import LLMService
from .repository import get_message, upsert_summary

logger = logging.getLogger(__name__)


class SummaryService:
    def __init__(self, llm: LLMService | None = None) -> None:
        self.llm = llm or LLMService()

    def summarize_message(self, message_id: int, force: bool = False, max_attempts: int = 2) -> dict[str, Any]:
        row = get_message(message_id)
        if not row:
            raise ValueError('Message not found')

        body = row['text_body'] or row['body_preview'] or ''
        attempt = 0
        last_error: str | None = None
        while attempt < max_attempts:
            attempt += 1
            try:
                raw = self.llm.summarize_mail(row['subject'], body)
                validated = validate_summary_payload(raw)
                normalized = summary_to_dict(validated)
                upsert_summary(message_id, settings.llm_model, normalized, raw, retry_count=attempt - 1)
                return {'ok': True, 'attempt': attempt, 'summary': normalized}
            except Exception as exc:
                last_error = str(exc)
                logger.warning('summarize_message failed: message_id=%s attempt=%s force=%s', message_id, attempt, force)

        fallback = {
            'summary_short': row['body_preview'] or '요약 실패',
            'summary_long': f'LLM 요약 실패로 원문 미리보기를 대신 저장했습니다.\n오류: {last_error}',
            'keywords': [],
            'risks': [],
            'action_items': [],
            'category': '기타',
            'status': 'triaged',
            'tags': ['요약실패'],
            'importance_score': 0,
        }
        upsert_summary(message_id, settings.llm_model, fallback, {'error': last_error}, retry_count=max_attempts)
        return {'ok': False, 'attempt': max_attempts, 'error': last_error, 'summary': fallback}
