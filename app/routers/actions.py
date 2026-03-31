from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from ..db import create_job, finish_job, get_conn
from ..services.pop3_ingest import ingest_from_pop3
from ..services.repository import (
    add_tag,
    delete_link,
    get_message,
    insert_link,
    list_summary_failed_message_ids,
    remove_tag,
    toggle_message_important,
    update_link,
    update_message_status,
)
from ..services.summary_service import SummaryService


def build_router(summary_service: SummaryService | None = None) -> APIRouter:
    router = APIRouter()
    summary_service = summary_service or SummaryService()

    @router.post('/actions/ingest')
    def action_ingest():
        job_id = create_job('pop3_ingest', 'running', 'Manual POP3 ingest started')
        try:
            result = ingest_from_pop3()
            finish_job(job_id, 'success', 'Manual POP3 ingest finished', result)
        except Exception as exc:
            finish_job(job_id, 'failed', f'Manual POP3 ingest failed: {exc}', {'error': str(exc)})
        return RedirectResponse('/', status_code=303)

    @router.post('/actions/summarize/{message_id}')
    def action_summarize(message_id: int):
        job_id = create_job('llm_summary', 'running', f'Summarize message #{message_id}')
        try:
            result = summary_service.summarize_message(message_id)
            finish_job(job_id, 'success' if result['ok'] else 'failed', 'Summary processed', result)
        except Exception as exc:
            finish_job(job_id, 'failed', f'Summary failed: {exc}', {'message_id': message_id, 'error': str(exc)})
        return RedirectResponse(f'/messages/{message_id}', status_code=303)

    @router.post('/actions/resummarize/{message_id}')
    def action_resummarize(message_id: int):
        job_id = create_job('llm_resummary', 'running', f'Re-summarize message #{message_id}')
        try:
            result = summary_service.summarize_message(message_id, force=True)
            finish_job(job_id, 'success' if result['ok'] else 'failed', 'Re-summary processed', result)
        except Exception as exc:
            finish_job(job_id, 'failed', f'Re-summary failed: {exc}', {'message_id': message_id, 'error': str(exc)})
        return RedirectResponse(f'/messages/{message_id}', status_code=303)

    @router.post('/actions/resummarize-failed')
    def action_resummarize_failed(limit: int = Form(30)):
        message_ids = list_summary_failed_message_ids(limit=limit)
        job_id = create_job('llm_resummary_batch', 'running', f'Batch resummarize started ({len(message_ids)})')
        processed, failed = 0, 0
        for message_id in message_ids:
            result = summary_service.summarize_message(message_id, force=True)
            if result['ok']:
                processed += 1
            else:
                failed += 1
        finish_job(job_id, 'success', 'Batch re-summary finished', {'processed': processed, 'failed': failed, 'targets': len(message_ids)})
        return RedirectResponse('/', status_code=303)

    @router.post('/actions/add-link/{message_id}')
    def action_add_link(message_id: int, title: str = Form(...), url: str = Form(...), link_type: str = Form('manual')):
        insert_link(message_id, link_type, title, url)
        return RedirectResponse(f'/messages/{message_id}', status_code=303)

    @router.post('/actions/update-link/{message_id}/{link_id}')
    def action_update_link(message_id: int, link_id: int, title: str = Form(...), url: str = Form(...), link_type: str = Form('manual')):
        update_link(link_id, title, url, link_type)
        return RedirectResponse(f'/messages/{message_id}', status_code=303)

    @router.post('/actions/delete-link/{message_id}/{link_id}')
    def action_delete_link(message_id: int, link_id: int):
        delete_link(link_id)
        return RedirectResponse(f'/messages/{message_id}', status_code=303)

    @router.post('/actions/status/{message_id}')
    def action_update_status(message_id: int, status: str = Form(...)):
        update_message_status(message_id, status)
        return RedirectResponse(f'/messages/{message_id}', status_code=303)

    @router.post('/actions/important/{message_id}')
    def action_toggle_important(message_id: int, enabled: str = Form('1')):
        toggle_message_important(message_id, enabled == '1')
        return RedirectResponse(f'/messages/{message_id}', status_code=303)

    @router.post('/actions/tag/add/{message_id}')
    def action_add_tag(message_id: int, tag: str = Form(...)):
        add_tag(message_id, tag)
        return RedirectResponse(f'/messages/{message_id}', status_code=303)

    @router.post('/actions/tag/remove/{message_id}')
    def action_remove_tag(message_id: int, tag: str = Form(...)):
        remove_tag(message_id, tag)
        return RedirectResponse(f'/messages/{message_id}', status_code=303)

    @router.get('/download/eml/{message_id}')
    def download_eml(message_id: int):
        row = get_message(message_id)
        if not row:
            raise HTTPException(status_code=404, detail='Message not found')
        path = Path(row['eml_path'])
        if not path.exists():
            raise HTTPException(status_code=404, detail='EML file missing')
        return FileResponse(path, filename=path.name, media_type='message/rfc822')

    @router.get('/download/attachment/{attachment_id}')
    def download_attachment(attachment_id: int):
        with get_conn() as conn:
            row = conn.execute('SELECT * FROM attachments WHERE id = ?', (attachment_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Attachment not found')
        path = Path(row['file_path'])
        if not path.exists():
            raise HTTPException(status_code=404, detail='Attachment file missing')
        return FileResponse(path, filename=row['filename'], media_type=row['content_type'])

    return router
