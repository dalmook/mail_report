from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from .config import settings
from .db import create_job, finish_job
from .services.pipeline import PipelineService

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone='Asia/Seoul')


def run_pipeline_job() -> None:
    job_id = create_job('full_pipeline', 'running', 'Automated pipeline started')
    service = PipelineService()
    try:
        result = service.run_full_pipeline(source='auto')
        finish_job(job_id, 'success', 'Automated pipeline finished', result)
    except Exception as exc:
        logger.exception('Automated pipeline failed')
        finish_job(job_id, 'failed', f'Automated pipeline failed: {exc}', {'error': str(exc)})


def start_scheduler() -> None:
    if settings.ingest_interval_minutes > 0 and not scheduler.running:
        scheduler.add_job(run_pipeline_job, 'interval', minutes=settings.ingest_interval_minutes, id='full_pipeline', replace_existing=True)
        scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
