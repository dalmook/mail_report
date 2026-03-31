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


def run_weekly_news_job() -> None:
    job_id = create_job('weekly_newsletter', 'running', 'Weekly newsletter job started')
    service = PipelineService()
    ok = service.send_weekly_newsletter()
    finish_job(job_id, 'success' if ok else 'failed', 'Weekly newsletter finished', {'sent': ok})


def start_scheduler() -> None:
    if not scheduler.running:
        if settings.ingest_interval_minutes > 0:
            scheduler.add_job(run_pipeline_job, 'interval', minutes=settings.ingest_interval_minutes, id='full_pipeline', replace_existing=True)
        if settings.weekly_report_auto_send:
            scheduler.add_job(
                run_weekly_news_job,
                'cron',
                day_of_week=str(settings.weekly_report_send_weekday),
                hour=settings.weekly_report_send_hour,
                id='weekly_newsletter',
                replace_existing=True,
            )
        if scheduler.get_jobs():
            scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
