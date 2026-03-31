from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SummaryPayload:
    summary_short: str
    summary_long: str
    keywords: list[str]
    risks: list[str]
    action_items: list[str]
    category: str
    importance_score: int
    status: str
    tags: list[str]


_ALLOWED_CATEGORIES = {'운영', '품질', '일정', '보고', '보안', '고객', '기타'}
_ALLOWED_STATUS = {'new', 'triaged', 'action_required', 'waiting', 'closed'}


def _ensure_list_of_str(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def validate_summary_payload(raw: dict[str, Any]) -> SummaryPayload:
    category = str(raw.get('category', '기타')).strip() or '기타'
    if category not in _ALLOWED_CATEGORIES:
        category = '기타'

    status = str(raw.get('status', 'triaged')).strip() or 'triaged'
    if status not in _ALLOWED_STATUS:
        status = 'triaged'

    importance = raw.get('importance_score', 0)
    try:
        importance_score = max(0, min(100, int(importance)))
    except Exception:
        importance_score = 0

    return SummaryPayload(
        summary_short=str(raw.get('summary_short', '')).strip(),
        summary_long=str(raw.get('summary_long', '')).strip(),
        keywords=_ensure_list_of_str(raw.get('keywords', [])),
        risks=_ensure_list_of_str(raw.get('risks', [])),
        action_items=_ensure_list_of_str(raw.get('action_items', [])),
        category=category,
        importance_score=importance_score,
        status=status,
        tags=_ensure_list_of_str(raw.get('tags', [])),
    )


def summary_to_dict(payload: SummaryPayload) -> dict[str, Any]:
    return {
        'summary_short': payload.summary_short,
        'summary_long': payload.summary_long,
        'keywords': payload.keywords,
        'risks': payload.risks,
        'action_items': payload.action_items,
        'category': payload.category,
        'importance_score': payload.importance_score,
        'status': payload.status,
        'tags': payload.tags,
    }
