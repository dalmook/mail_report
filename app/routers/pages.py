from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..services.repository import (
    dashboard_stats,
    get_attachments,
    get_links,
    get_message,
    get_related_messages,
    get_summary_history,
    get_thread,
    list_messages,
    tags_for_message,
)



def build_router(templates: Jinja2Templates) -> APIRouter:
    router = APIRouter()

    @router.get('/', response_class=HTMLResponse)
    def dashboard(request: Request):
        stats = dashboard_stats()
        return templates.TemplateResponse('dashboard.html', {'request': request, 'stats': stats})

    @router.get('/messages', response_class=HTMLResponse)
    def messages_page(
        request: Request,
        q: str = '',
        sender: str = '',
        date_from: str = '',
        date_to: str = '',
        category: str = '',
        has_summary: str = '',
        status: str = '',
        tag: str = '',
        has_attachment: str = '',
        importance_min: int | None = None,
        importance_max: int | None = None,
        sort: str = 'latest',
    ):
        rows = list_messages(
            q=q,
            sender=sender,
            date_from=date_from,
            date_to=date_to,
            category=category,
            has_summary=has_summary,
            status=status,
            tag=tag,
            has_attachment=has_attachment,
            importance_min=importance_min,
            importance_max=importance_max,
            sort=sort,
        )
        return templates.TemplateResponse(
            'messages.html',
            {
                'request': request,
                'rows': rows,
                'q': q,
                'sender': sender,
                'date_from': date_from,
                'date_to': date_to,
                'category': category,
                'has_summary': has_summary,
                'status': status,
                'tag': tag,
                'has_attachment': has_attachment,
                'importance_min': importance_min if importance_min is not None else '',
                'importance_max': importance_max if importance_max is not None else '',
                'sort': sort,
            },
        )

    @router.get('/messages/{message_id}', response_class=HTMLResponse)
    def message_detail(request: Request, message_id: int):
        row = get_message(message_id)
        if not row:
            raise HTTPException(status_code=404, detail='Message not found')
        attachments = get_attachments(message_id)
        links = get_links(message_id)
        thread_rows = get_thread(message_id)
        related_rows = get_related_messages(message_id)
        history_rows = get_summary_history(message_id)
        return templates.TemplateResponse(
            'message_detail.html',
            {
                'request': request,
                'row': row,
                'attachments': attachments,
                'links': links,
                'thread_rows': thread_rows,
                'related_rows': related_rows,
                'history_rows': history_rows,
                'keywords': _parse_json_list(row['keywords_json']),
                'risks': _parse_json_list(row['risks_json']),
                'action_items': _parse_json_list(row['action_items_json']),
                'tags': tags_for_message(row),
                'entities_people': _parse_json_list(row['entities_people_json']),
                'entities_orgs': _parse_json_list(row['entities_orgs_json']),
                'deadlines': _parse_json_list(row['deadlines_json']),
                'numeric_facts': _parse_json_list(row['numeric_facts_json']),
            },
        )

    return router


def _parse_json_list(value: str | None) -> list[str]:
    import json

    if not value:
        return []
    try:
        data = json.loads(value)
        return data if isinstance(data, list) else []
    except Exception:
        return []
