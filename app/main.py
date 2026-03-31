from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import settings
from .db import create_job, finish_job, init_db
from .scheduler import start_scheduler, stop_scheduler
from .services.llm_summarizer import LLMDisabledError, LLMService
from .services.pop3_ingest import ingest_from_pop3
from .services.repository import (
    dashboard_stats,
    get_attachments,
    get_links,
    get_message,
    get_thread,
    insert_link,
    list_messages,
    upsert_summary,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title=settings.app_title, lifespan=lifespan)
app.mount('/static', StaticFiles(directory=Path(__file__).parent / 'static'), name='static')
templates = Jinja2Templates(directory=str(Path(__file__).parent / 'templates'))
llm_service = LLMService()


def _parse_json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        data = json.loads(value)
        return data if isinstance(data, list) else []
    except Exception:
        return []


@app.get('/', response_class=HTMLResponse)
def dashboard(request: Request):
    stats = dashboard_stats()
    return templates.TemplateResponse('dashboard.html', {'request': request, 'stats': stats})


@app.get('/messages', response_class=HTMLResponse)
def messages_page(request: Request, q: str = '', category: str = '', has_summary: str = ''):
    rows = list_messages(q=q, category=category, has_summary=has_summary)
    return templates.TemplateResponse(
        'messages.html',
        {'request': request, 'rows': rows, 'q': q, 'category': category, 'has_summary': has_summary},
    )


@app.get('/messages/{message_id}', response_class=HTMLResponse)
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
        },
    )


@app.post('/actions/ingest')
def action_ingest():
    job_id = create_job('pop3_ingest', 'running', 'Manual POP3 ingest started')
    try:
        result = ingest_from_pop3()
        finish_job(job_id, 'success', 'Manual POP3 ingest finished', result)
    except Exception as exc:
        finish_job(job_id, 'failed', f'Manual POP3 ingest failed: {exc}', {'error': str(exc)})
    return RedirectResponse('/', status_code=303)


@app.post('/actions/summarize/{message_id}')
def action_summarize(message_id: int):
    row = get_message(message_id)
    if not row:
        raise HTTPException(status_code=404, detail='Message not found')

    job_id = create_job('llm_summary', 'running', f'Summarize message #{message_id}')
    try:
        data = llm_service.summarize_mail(row['subject'], row['text_body'] or row['body_preview'] or '')
        upsert_summary(message_id, settings.llm_model, data, data)
        finish_job(job_id, 'success', 'Summary created', {'message_id': message_id})
    except LLMDisabledError as exc:
        finish_job(job_id, 'failed', str(exc), {'message_id': message_id})
    except Exception as exc:
        finish_job(job_id, 'failed', f'Summary failed: {exc}', {'message_id': message_id, 'error': str(exc)})
    return RedirectResponse(f'/messages/{message_id}', status_code=303)


@app.post('/actions/add-link/{message_id}')
def action_add_link(message_id: int, title: str = Form(...), url: str = Form(...), link_type: str = Form('manual')):
    insert_link(message_id, link_type, title, url)
    return RedirectResponse(f'/messages/{message_id}', status_code=303)


@app.get('/download/eml/{message_id}')
def download_eml(message_id: int):
    row = get_message(message_id)
    if not row:
        raise HTTPException(status_code=404, detail='Message not found')
    path = Path(row['eml_path'])
    if not path.exists():
        raise HTTPException(status_code=404, detail='EML file missing')
    return FileResponse(path, filename=path.name, media_type='message/rfc822')


@app.get('/download/attachment/{attachment_id}')
def download_attachment(attachment_id: int):
    from .db import get_conn

    with get_conn() as conn:
        row = conn.execute('SELECT * FROM attachments WHERE id = ?', (attachment_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail='Attachment not found')
    path = Path(row['file_path'])
    if not path.exists():
        raise HTTPException(status_code=404, detail='Attachment file missing')
    return FileResponse(path, filename=row['filename'], media_type=row['content_type'])
