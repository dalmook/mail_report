from __future__ import annotations

import json
import logging

from ..config import settings
from ..db import get_conn
from .mailer import MailerDisabledError, send_html_mail
from .news_report import render_weekly_news_html
from .repository import (
    build_period_summary,
    list_issues,
    list_summary_failed_message_ids,
    save_period_llm_summary,
    upsert_issue_candidate,
)
from .summary_service import SummaryService
from .pop3_ingest import ingest_from_pop3

logger = logging.getLogger(__name__)


class PipelineService:
    def __init__(self, summary_service: SummaryService | None = None) -> None:
        self.summary_service = summary_service or SummaryService()

    def run_full_pipeline(self, source: str = 'manual') -> dict[str, int]:
        run_id = self._start_run(f'pipeline_{source}')
        stats = {'ingested': 0, 'summarized': 0, 'failed': 0, 'candidates': 0, 'mail_sent': 0}
        try:
            ingest_result = ingest_from_pop3()
            stats['ingested'] = int(ingest_result.get('stored', 0))

            targets = list_summary_failed_message_ids(limit=200)
            for mid in targets:
                result = self.summary_service.summarize_message(mid)
                if result['ok']:
                    stats['summarized'] += 1
                else:
                    stats['failed'] += 1
                cand = upsert_issue_candidate(mid)
                if cand:
                    stats['candidates'] += 1

            week = build_period_summary('week')
            save_period_llm_summary(week['period_type'], week['period_key'], f"주간 자동요약: 수집 {week['period_count']}건, 리스크 {week['risk_count']}건")
            month = build_period_summary('month')
            save_period_llm_summary(month['period_type'], month['period_key'], f"월간 자동요약: 수집 {month['period_count']}건, 이슈전환 {month['issue_converted']}건")

            if source in {'manual', 'auto_weekly'}:
                if self.send_weekly_newsletter(week):
                    stats['mail_sent'] = 1

            self._finish_run(run_id, 'success', detail=stats)
            return stats
        except Exception as exc:
            logger.exception('pipeline run failed')
            self._finish_run(run_id, 'failed', error=str(exc), detail=stats)
            return stats

    def send_weekly_newsletter(self, week_report: dict | None = None) -> bool:
        report = week_report or build_period_summary('week')
        issues = list_issues()[:20]
        html = render_weekly_news_html(report, issues)
        to_emails = [e.strip() for e in settings.report_to_emails.split(',') if e.strip()]
        try:
            send_html_mail(subject=f"[주간운영리포트] {report['period_key']}", html_body=html, to_emails=to_emails)
            return True
        except MailerDisabledError:
            return False
        except Exception:
            logger.exception('weekly newsletter send failed')
            return False

    def _start_run(self, run_type: str) -> int:
        with get_conn() as conn:
            cur = conn.execute('INSERT INTO pipeline_runs(run_type, status, detail_json) VALUES (?, ?, ?)', (run_type, 'running', '{}'))
            return int(cur.lastrowid)

    def _finish_run(self, run_id: int, status: str, error: str = '', detail: dict | None = None) -> None:
        with get_conn() as conn:
            conn.execute(
                '''UPDATE pipeline_runs
                SET status=?, finished_at=CURRENT_TIMESTAMP,
                    last_success_at=CASE WHEN ?='success' THEN CURRENT_TIMESTAMP ELSE last_success_at END,
                    last_failure_at=CASE WHEN ?='failed' THEN CURRENT_TIMESTAMP ELSE last_failure_at END,
                    error_message=?, detail_json=?
                WHERE id=?''',
                (status, status, status, error, json.dumps(detail or {}, ensure_ascii=False), run_id),
            )
