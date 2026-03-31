from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..services.repository import (
    dashboard_stats,
    get_attachments,
    get_issue,
    get_issue_links,
    get_links,
    get_message,
    get_period_summary,
    get_related_messages,
    get_summary_history,
    get_thread,
    list_issue_candidates,
    list_issue_events,
    list_issues,
    list_message_issues,
    list_messages,
    monitoring_stats,
    storage_consistency_check,
    tags_for_message,
)


def build_router(templates: Jinja2Templates) -> APIRouter:
    router = APIRouter()

    @router.get('/', response_class=HTMLResponse)
    def dashboard(request: Request):
        stats = dashboard_stats()
        return templates.TemplateResponse('dashboard.html', {'request': request, 'stats': stats})

    @router.get('/admin/ops', response_class=HTMLResponse)
    def admin_ops(request: Request, candidate_status: str = 'PENDING'):
        mon = monitoring_stats()
        candidates = list_issue_candidates(status=candidate_status, limit=80)
        diag = storage_consistency_check()
        return templates.TemplateResponse('ops_admin.html', {'request': request, 'mon': mon, 'candidates': candidates, 'candidate_status': candidate_status, 'diag': diag})

    @router.get('/messages', response_class=HTMLResponse)
    def messages_page(
        request: Request,
        q: str = '', sender: str = '', date_from: str = '', date_to: str = '', category: str = '',
        has_summary: str = '', status: str = '', tag: str = '', has_attachment: str = '', importance_min: int | None = None,
        importance_max: int | None = None, sort: str = 'latest', quick: str = '',
    ):
        if quick == 'today_important':
            date_from = '2000-01-01'
            importance_min = 70
            sort = 'importance_desc'
        elif quick == 'summary_failed':
            sort = 'summary_failed_desc'
        elif quick == 'risk':
            category = '운영'
            importance_min = 70
        elif quick == 'issue_candidate':
            tag = '리스크'

        rows = list_messages(
            q=q, sender=sender, date_from=date_from, date_to=date_to, category=category, has_summary=has_summary,
            status=status, tag=tag, has_attachment=has_attachment, importance_min=importance_min,
            importance_max=importance_max, sort=sort,
        )
        return templates.TemplateResponse('messages.html', {
            'request': request, 'rows': rows, 'q': q, 'sender': sender, 'date_from': date_from,
            'date_to': date_to, 'category': category, 'has_summary': has_summary, 'status': status,
            'tag': tag, 'has_attachment': has_attachment,
            'importance_min': importance_min if importance_min is not None else '',
            'importance_max': importance_max if importance_max is not None else '', 'sort': sort, 'quick': quick,
        })

    @router.get('/messages/{message_id}', response_class=HTMLResponse)
    def message_detail(request: Request, message_id: int):
        row = get_message(message_id)
        if not row:
            raise HTTPException(status_code=404, detail='Message not found')
        return templates.TemplateResponse('message_detail.html', {
            'request': request,
            'row': row,
            'attachments': get_attachments(message_id),
            'links': get_links(message_id),
            'thread_rows': get_thread(message_id),
            'related_rows': get_related_messages(message_id),
            'history_rows': get_summary_history(message_id),
            'issues': list_message_issues(message_id),
            'keywords': _parse_json_list(row['keywords_json']),
            'risks': _parse_json_list(row['risks_json']),
            'action_items': _parse_json_list(row['action_items_json']),
            'tags': tags_for_message(row),
            'tag_reasons': _parse_json_dict(row['tag_reasons_json']),
            'entities_people': _parse_json_list(row['entities_people_json']),
            'entities_orgs': _parse_json_list(row['entities_orgs_json']),
            'deadlines': _parse_json_list(row['deadlines_json']),
            'numeric_facts': _parse_json_list(row['numeric_facts_json']),
        })

    @router.get('/issues', response_class=HTMLResponse)
    def issues_page(request: Request, status: str = ''):
        rows = list_issues(status=status)
        return templates.TemplateResponse('issues.html', {'request': request, 'rows': rows, 'status': status})

    @router.get('/issues/{issue_id}', response_class=HTMLResponse)
    def issue_detail(request: Request, issue_id: int):
        issue = get_issue(issue_id)
        if not issue:
            raise HTTPException(status_code=404, detail='Issue not found')
        return templates.TemplateResponse('issue_detail.html', {
            'request': request,
            'issue': issue,
            'events': list_issue_events(issue_id),
            'issue_links': get_issue_links(issue_id),
            'source_message': get_message(issue['source_message_id']) if issue['source_message_id'] else None,
        })

    @router.get('/reports/weekly', response_class=HTMLResponse)
    def weekly_report(request: Request):
        report = get_period_summary(period_type='week')
        return templates.TemplateResponse('report_period.html', {'request': request, 'report': report, 'label': '주간'})

    @router.get('/reports/monthly', response_class=HTMLResponse)
    def monthly_report(request: Request):
        report = get_period_summary(period_type='month')
        return templates.TemplateResponse('report_period.html', {'request': request, 'report': report, 'label': '월간'})

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


def _parse_json_dict(value: str | None) -> dict[str, str]:
    import json

    if not value:
        return {}
    try:
        data = json.loads(value)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}
