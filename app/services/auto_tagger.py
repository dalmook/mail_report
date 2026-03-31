from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TagSuggestion:
    tag: str
    confidence: float
    reason: str


def suggest_tags(
    subject: str,
    body_preview: str,
    from_email: str,
    has_attachment: bool,
    summary_tags: list[str],
    keywords: list[str],
    category: str,
    importance_score: int,
) -> list[TagSuggestion]:
    text = f"{subject} {body_preview} {' '.join(keywords)} {' '.join(summary_tags)}".lower()
    suggestions: list[TagSuggestion] = []

    def add(tag: str, conf: float, reason: str) -> None:
        suggestions.append(TagSuggestion(tag, conf, reason))

    if importance_score >= 75:
        add('중요', 0.9, 'importance_score >= 75')
    if '보고' in text or category == '보고':
        add('보고', 0.8, '보고 키워드/카테고리')
    if any(k in text for k in ['일정', '마감', 'due', 'deadline']):
        add('일정', 0.75, '일정 관련 키워드')
    if any(k in text for k in ['리스크', '위험', '이슈']):
        add('리스크', 0.8, '리스크 키워드')
    if any(k in text for k in ['장애', 'incident', 'error', 'fail']):
        add('장애', 0.88, '장애 키워드')
    if any(k in text for k in ['요청', 'please', '부탁']):
        add('요청', 0.72, '요청 문구')
    if any(k in text for k in ['회의', 'meeting', 'mtg']):
        add('회의', 0.75, '회의 키워드')
    if has_attachment and importance_score >= 60:
        add('첨부중요', 0.7, '첨부 있음 + 중요도 높음')

    if any(x in from_email.lower() for x in ['customer', 'client', 'cs@']):
        add('고객', 0.78, '발신자 기반')
    elif any(x in from_email.lower() for x in ['ops', 'dev', 'infra']):
        add('운영', 0.65, '발신자 기반')
    elif from_email:
        add('내부', 0.55, '기본 발신자 분류')
    else:
        add('기타', 0.4, '발신자 정보 부족')

    dedup: dict[str, TagSuggestion] = {}
    for s in suggestions:
        old = dedup.get(s.tag)
        if not old or s.confidence > old.confidence:
            dedup[s.tag] = s
    return sorted(dedup.values(), key=lambda x: x.confidence, reverse=True)
