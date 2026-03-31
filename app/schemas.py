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
    entities_people: list[str]
    entities_orgs: list[str]
    deadlines: list[str]
    numeric_facts: list[str]


_ALLOWED_CATEGORIES = {'운영', '품질', '일정', '보고', '보안', '고객', '기타'}
_ALLOWED_STATUS = {'new', 'reviewed', 'flagged', 'archived'}


def _ensure_list_of_str(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _fallback_importance(raw: dict[str, Any], importance_score: int) -> int:
    if importance_score > 0:
        return importance_score
    body = f"{raw.get('summary_short', '')} {raw.get('summary_long', '')}".lower()
    if any(k in body for k in ['긴급', 'urgent', '장애', '사고', '리스크']):
        return 80
    if any(k in body for k in ['요청', '검토', '일정']):
        return 55
    return 30


def validate_summary_payload(raw: dict[str, Any]) -> SummaryPayload:
    category = str(raw.get('category', '기타')).strip() or '기타'
    if category not in _ALLOWED_CATEGORIES:
        category = '기타'

    status = str(raw.get('status', 'new')).strip() or 'new'
    if status not in _ALLOWED_STATUS:
        status = 'new'

    importance = raw.get('importance_score', 0)
    try:
        importance_score = max(0, min(100, int(importance)))
    except Exception:
        importance_score = 0
    importance_score = _fallback_importance(raw, importance_score)

    short = str(raw.get('summary_short', '')).strip()
    long = str(raw.get('summary_long', '')).strip()
    if not short and long:
        short = long[:120]
    if not long and short:
        long = short

    return SummaryPayload(
        summary_short=short,
        summary_long=long,
        keywords=_ensure_list_of_str(raw.get('keywords', [])),
        risks=_ensure_list_of_str(raw.get('risks', [])),
        action_items=_ensure_list_of_str(raw.get('action_items', [])),
        category=category,
        importance_score=importance_score,
        status=status,
        tags=_ensure_list_of_str(raw.get('tags', [])),
        entities_people=_ensure_list_of_str(raw.get('entities_people', [])),
        entities_orgs=_ensure_list_of_str(raw.get('entities_orgs', [])),
        deadlines=_ensure_list_of_str(raw.get('deadlines', [])),
        numeric_facts=_ensure_list_of_str(raw.get('numeric_facts', [])),
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
        'entities_people': payload.entities_people,
        'entities_orgs': payload.entities_orgs,
        'deadlines': payload.deadlines,
        'numeric_facts': payload.numeric_facts,
    }
