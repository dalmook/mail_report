from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..services.repository import (
    dashboard_stats,
    get_attachments,
    get_links,
    get_message,
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
        category: str = '',
        has_summary: str = '',
        status: str = '',
        tag: str = '',
    ):
        rows = list_messages(q=q, category=category, has_summary=has_summary, status=status, tag=tag)
        return templates.TemplateResponse(
            'messages.html',
            {
                'request': request,
                'rows': rows,
                'q': q,
                'category': category,
                'has_summary': has_summary,
                'status': status,
                'tag': tag,
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
        return templates.TemplateResponse(
            'message_detail.html',
            {
                'request': request,
                'row': row,
                'attachments': attachments,
                'links': links,
                'thread_rows': thread_rows,
                'keywords': _parse_json_list(row['keywords_json']),
                'risks': _parse_json_list(row['risks_json']),
                'action_items': _parse_json_list(row['action_items_json']),
                'tags': tags_for_message(row),
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
