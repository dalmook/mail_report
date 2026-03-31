from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from .config import settings
from .db import create_job, finish_job
from .services.pop3_ingest import ingest_from_pop3

scheduler = BackgroundScheduler(timezone='Asia/Seoul')


def run_ingest_job() -> None:
    job_id = create_job('pop3_ingest', 'running', 'POP3 ingest started')
    try:
        result = ingest_from_pop3()
        finish_job(job_id, 'success', 'POP3 ingest finished', result)
    except Exception as exc:
        finish_job(job_id, 'failed', f'POP3 ingest failed: {exc}', {'error': str(exc)})


def start_scheduler() -> None:
    if settings.ingest_interval_minutes > 0 and not scheduler.running:
        scheduler.add_job(run_ingest_job, 'interval', minutes=settings.ingest_interval_minutes, id='pop3_ingest', replace_existing=True)
        scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
