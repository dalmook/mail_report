from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from ..db import get_conn
from .auto_tagger import TagSuggestion


def _json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _sync_tags(conn: Any, message_id: int, tags: list[str], source: str = 'manual', reasons: dict[str, str] | None = None) -> None:
    clean_tags = [tag.strip() for tag in tags if tag and tag.strip()]
    conn.execute('DELETE FROM message_tags WHERE message_id = ?', (message_id,))
    for tag in sorted(set(clean_tags)):
        conn.execute('INSERT INTO tags(name) VALUES (?) ON CONFLICT(name) DO NOTHING', (tag,))
        tag_row = conn.execute('SELECT id FROM tags WHERE name = ?', (tag,)).fetchone()
        if tag_row:
            conn.execute(
                '''
                INSERT INTO message_tags(message_id, tag_id, source, confidence, reason)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(message_id, tag_id) DO UPDATE SET
                  source=excluded.source, confidence=excluded.confidence, reason=excluded.reason
                ''',
                (message_id, tag_row['id'], source, 1.0 if source == 'manual' else 0.7, (reasons or {}).get(tag, '')),
            )


def apply_auto_tags(message_id: int, suggestions: list[TagSuggestion]) -> None:
    tags = [s.tag for s in suggestions]
    reasons = {s.tag: s.reason for s in suggestions}
    with get_conn() as conn:
        _sync_tags(conn, message_id, tags, source='auto', reasons=reasons)
        conn.execute('UPDATE summaries SET tags_json = ?, tag_reasons_json = ? WHERE message_id = ?', (json.dumps(tags, ensure_ascii=False), json.dumps(reasons, ensure_ascii=False), message_id))


def _period_count_sql(period: str) -> str:
    return f"SELECT COUNT(*) FROM messages WHERE datetime(received_at) >= datetime('now', '{period}')"


def dashboard_stats() -> dict[str, Any]:
    with get_conn() as conn:
        total_messages = conn.execute('SELECT COUNT(*) FROM messages').fetchone()[0]
        total_summaries = conn.execute('SELECT COUNT(*) FROM summaries').fetchone()[0]
        summary_failed = conn.execute("SELECT COUNT(*) FROM summaries WHERE tags_json LIKE '%요약실패%'").fetchone()[0]
        attachments = conn.execute('SELECT COUNT(*) FROM messages WHERE has_attachment = 1').fetchone()[0]
        important_messages = conn.execute('SELECT COUNT(*) FROM messages WHERE is_important = 1').fetchone()[0]
        action_item_messages = conn.execute("SELECT COUNT(*) FROM summaries WHERE action_items_json NOT IN ('[]', '', 'null')").fetchone()[0]

        today_count = conn.execute(_period_count_sql('-1 day')).fetchone()[0]
        week_count = conn.execute(_period_count_sql('-7 day')).fetchone()[0]
        month_count = conn.execute(_period_count_sql('-30 day')).fetchone()[0]
        completion_rate = round((total_summaries / total_messages) * 100, 1) if total_messages else 0.0

        category_rows = conn.execute("SELECT COALESCE(category, '미분류') AS category, COUNT(*) AS cnt FROM summaries GROUP BY COALESCE(category, '미분류') ORDER BY cnt DESC").fetchall()
        sender_top = conn.execute("SELECT from_email, COUNT(*) AS cnt FROM messages WHERE from_email <> '' GROUP BY from_email ORDER BY cnt DESC LIMIT 8").fetchall()

        recent_risks = conn.execute(
            '''
            SELECT m.id, m.subject, m.from_email, m.sent_at, s.importance_score
            FROM messages m JOIN summaries s ON s.message_id = m.id
            WHERE s.risks_json NOT IN ('[]', '', 'null')
            ORDER BY s.importance_score DESC, COALESCE(m.sent_at, m.received_at) DESC
            LIMIT 8
            '''
        ).fetchall()
        recent_summary_failures = conn.execute(
            '''
            SELECT m.id, m.subject, m.from_email, m.sent_at
            FROM messages m JOIN summaries s ON s.message_id = m.id
            WHERE s.tags_json LIKE '%요약실패%'
            ORDER BY COALESCE(m.sent_at, m.received_at) DESC
            LIMIT 8
            '''
        ).fetchall()
        recent_resummary_targets = conn.execute(
            '''
            SELECT m.id, m.subject, m.from_email, m.sent_at, s.retry_count
            FROM messages m JOIN summaries s ON s.message_id = m.id
            WHERE s.retry_count > 0 OR s.tags_json LIKE '%요약실패%'
            ORDER BY s.retry_count DESC, COALESCE(m.sent_at, m.received_at) DESC
            LIMIT 8
            '''
        ).fetchall()
        today_focus = conn.execute(
            '''
            SELECT m.id, m.subject, m.from_email, s.importance_score
            FROM messages m LEFT JOIN summaries s ON s.message_id = m.id
            WHERE datetime(m.received_at) >= datetime('now','-1 day')
            ORDER BY COALESCE(s.importance_score, 0) DESC, m.received_at DESC
            LIMIT 10
            '''
        ).fetchall()
        recent_issues = conn.execute('SELECT id, title, status, priority, due_date FROM issues ORDER BY id DESC LIMIT 8').fetchall()
        due_soon_issues = conn.execute("SELECT id, title, status, owner, due_date FROM issues WHERE status <> 'CLOSED' AND due_date IS NOT NULL ORDER BY due_date LIMIT 8").fetchall()
        weekly_summary_row = conn.execute("SELECT llm_summary, summary_json FROM period_summaries WHERE period_type='week' ORDER BY id DESC LIMIT 1").fetchone()
        jobs = conn.execute('SELECT id, job_type, status, started_at, finished_at, message FROM jobs ORDER BY id DESC LIMIT 12').fetchall()

    weekly_highlight = ''
    if weekly_summary_row:
        weekly_highlight = weekly_summary_row['llm_summary'] or ''
        if not weekly_highlight:
            weekly_highlight = f"집계: {weekly_summary_row['summary_json'][:120]}"

    return {
        'total_messages': total_messages,
        'total_summaries': total_summaries,
        'summary_failed': summary_failed,
        'completion_rate': completion_rate,
        'attachments': attachments,
        'important_messages': important_messages,
        'action_item_messages': action_item_messages,
        'today_count': today_count,
        'week_count': week_count,
        'month_count': month_count,
        'category_rows': category_rows,
        'sender_top': sender_top,
        'recent_risks': recent_risks,
        'recent_summary_failures': recent_summary_failures,
        'recent_resummary_targets': recent_resummary_targets,
        'today_focus': today_focus,
        'recent_issues': recent_issues,
        'due_soon_issues': due_soon_issues,
        'weekly_highlight': weekly_highlight,
        'jobs': jobs,
    }


def list_messages(
    q: str = '', sender: str = '', date_from: str = '', date_to: str = '', category: str = '', has_summary: str = '',
    status: str = '', tag: str = '', has_attachment: str = '', importance_min: int | None = None,
    importance_max: int | None = None, sort: str = 'latest', limit: int = 200,
) -> list[Any]:
    sql = '''
    SELECT m.*, s.summary_short, s.category, s.importance_score, s.status AS summary_status,
           s.tags_json, s.action_items_json,
           CASE WHEN s.tags_json LIKE '%요약실패%' THEN 1 ELSE 0 END AS summary_failed
    FROM messages m
    LEFT JOIN summaries s ON s.message_id = m.id
    WHERE 1=1
    '''
    params: list[Any] = []
    if q:
        like = f'%{q}%'
        sql += ' AND (m.subject LIKE ? OR m.body_preview LIKE ? OR m.text_body LIKE ?)'
        params.extend([like, like, like])
    if sender:
        sql += ' AND m.from_email LIKE ?'
        params.append(f'%{sender}%')
    if date_from:
        sql += ' AND COALESCE(m.sent_at, m.received_at) >= ?'
        params.append(date_from)
    if date_to:
        sql += ' AND COALESCE(m.sent_at, m.received_at) <= ?'
        params.append(date_to)
    if category:
        sql += ' AND s.category = ?'
        params.append(category)
    if has_summary == 'Y':
        sql += ' AND s.id IS NOT NULL'
    elif has_summary == 'N':
        sql += ' AND s.id IS NULL'
    if status:
        sql += ' AND COALESCE(s.status, m.status, "new") = ?'
        params.append(status)
    if tag:
        sql += ' AND EXISTS (SELECT 1 FROM message_tags mt JOIN tags t ON t.id = mt.tag_id WHERE mt.message_id = m.id AND t.name LIKE ?)'
        params.append(f'%{tag}%')
    if has_attachment == 'Y':
        sql += ' AND m.has_attachment = 1'
    elif has_attachment == 'N':
        sql += ' AND m.has_attachment = 0'
    if importance_min is not None:
        sql += ' AND COALESCE(s.importance_score, 0) >= ?'
        params.append(importance_min)
    if importance_max is not None:
        sql += ' AND COALESCE(s.importance_score, 100) <= ?'
        params.append(importance_max)

    sort_sql = {
        'latest': 'COALESCE(m.sent_at, m.received_at) DESC',
        'importance_desc': 'COALESCE(s.importance_score, 0) DESC, COALESCE(m.sent_at, m.received_at) DESC',
        'summary_failed_desc': 'summary_failed DESC, COALESCE(m.sent_at, m.received_at) DESC',
    }.get(sort, 'COALESCE(m.sent_at, m.received_at) DESC')

    sql += f' ORDER BY {sort_sql} LIMIT ?'
    params.append(limit)
    with get_conn() as conn:
        return conn.execute(sql, params).fetchall()


def get_message(message_id: int) -> Any:
    with get_conn() as conn:
        return conn.execute(
            '''
            SELECT m.*, s.summary_short, s.summary_long, s.keywords_json,
                   s.risks_json, s.action_items_json, s.category, s.importance_score,
                   s.status as summary_status, s.tags_json, s.tag_reasons_json, s.entities_people_json,
                   s.entities_orgs_json, s.deadlines_json, s.numeric_facts_json, s.retry_count
            FROM messages m
            LEFT JOIN summaries s ON s.message_id = m.id
            WHERE m.id = ?
            ''',
            (message_id,),
        ).fetchone()


def get_attachments(message_id: int) -> list[Any]:
    with get_conn() as conn:
        return conn.execute('SELECT * FROM attachments WHERE message_id = ? ORDER BY id', (message_id,)).fetchall()


def get_links(message_id: int) -> list[Any]:
    with get_conn() as conn:
        return conn.execute('SELECT * FROM links WHERE message_id = ? ORDER BY id DESC', (message_id,)).fetchall()


def update_link(link_id: int, title: str, url: str, link_type: str) -> None:
    with get_conn() as conn:
        conn.execute('UPDATE links SET title = ?, url = ?, link_type = ? WHERE id = ?', (title, url, link_type, link_id))


def delete_link(link_id: int) -> None:
    with get_conn() as conn:
        conn.execute('DELETE FROM links WHERE id = ?', (link_id,))


def get_thread(message_id: int) -> list[Any]:
    with get_conn() as conn:
        current = conn.execute('SELECT thread_key FROM messages WHERE id = ?', (message_id,)).fetchone()
        if not current or not current['thread_key']:
            return []
        return conn.execute(
            '''
            SELECT m.id, m.subject, m.from_email, m.sent_at, m.message_id, m.in_reply_to,
                   s.status as summary_status, s.importance_score, s.summary_short
            FROM messages m
            LEFT JOIN summaries s ON s.message_id = m.id
            WHERE m.thread_key = ?
            ORDER BY COALESCE(m.sent_at, m.received_at)
            ''',
            (current['thread_key'],),
        ).fetchall()


def get_related_messages(message_id: int, limit: int = 8) -> list[Any]:
    with get_conn() as conn:
        current = conn.execute('SELECT subject_normalized FROM messages WHERE id = ?', (message_id,)).fetchone()
        if not current or not current['subject_normalized']:
            return []
        return conn.execute(
            'SELECT id, subject, from_email, sent_at FROM messages WHERE subject_normalized = ? AND id <> ? ORDER BY COALESCE(sent_at, received_at) DESC LIMIT ?',
            (current['subject_normalized'], message_id, limit),
        ).fetchall()


def get_summary_history(message_id: int, limit: int = 10) -> list[Any]:
    with get_conn() as conn:
        return conn.execute('SELECT id, model_name, reason, created_at FROM summary_history WHERE message_id = ? ORDER BY id DESC LIMIT ?', (message_id, limit)).fetchall()


def upsert_summary(message_id: int, model_name: str, data: dict[str, Any], raw_response: dict[str, Any] | None = None, retry_count: int = 0, reason: str = 'summarize') -> None:
    tags = data.get('tags', [])
    tag_reasons = data.get('tag_reasons', {})
    with get_conn() as conn:
        prev = conn.execute('SELECT * FROM summaries WHERE message_id = ?', (message_id,)).fetchone()
        if prev:
            prev_payload = {'summary_short': prev['summary_short'], 'summary_long': prev['summary_long'], 'category': prev['category'], 'status': prev['status'], 'importance_score': prev['importance_score']}
            conn.execute('INSERT INTO summary_history(message_id, model_name, summary_json, reason) VALUES (?, ?, ?, ?)', (message_id, prev['model_name'], json.dumps(prev_payload, ensure_ascii=False), reason))

        conn.execute(
            '''
            INSERT INTO summaries(
                message_id, model_name, summary_short, summary_long, keywords_json,
                risks_json, action_items_json, entities_people_json, entities_orgs_json,
                deadlines_json, numeric_facts_json, category, status, tags_json, tag_reasons_json,
                importance_score, retry_count, raw_response
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(message_id) DO UPDATE SET
                model_name=excluded.model_name, summary_short=excluded.summary_short,
                summary_long=excluded.summary_long, keywords_json=excluded.keywords_json,
                risks_json=excluded.risks_json, action_items_json=excluded.action_items_json,
                entities_people_json=excluded.entities_people_json, entities_orgs_json=excluded.entities_orgs_json,
                deadlines_json=excluded.deadlines_json, numeric_facts_json=excluded.numeric_facts_json,
                category=excluded.category, status=excluded.status, tags_json=excluded.tags_json,
                tag_reasons_json=excluded.tag_reasons_json, importance_score=excluded.importance_score,
                retry_count=excluded.retry_count, raw_response=excluded.raw_response, created_at=CURRENT_TIMESTAMP
            ''',
            (
                message_id, model_name, data.get('summary_short', ''), data.get('summary_long', ''),
                json.dumps(data.get('keywords', []), ensure_ascii=False),
                json.dumps(data.get('risks', []), ensure_ascii=False),
                json.dumps(data.get('action_items', []), ensure_ascii=False),
                json.dumps(data.get('entities_people', []), ensure_ascii=False),
                json.dumps(data.get('entities_orgs', []), ensure_ascii=False),
                json.dumps(data.get('deadlines', []), ensure_ascii=False),
                json.dumps(data.get('numeric_facts', []), ensure_ascii=False),
                data.get('category', '기타'), data.get('status', 'new'),
                json.dumps(tags, ensure_ascii=False), json.dumps(tag_reasons, ensure_ascii=False),
                int(data.get('importance_score', 0) or 0), retry_count,
                json.dumps(raw_response or data, ensure_ascii=False),
            ),
        )
        _sync_tags(conn, message_id, tags, source='manual', reasons=tag_reasons)


def insert_link(message_id: int, link_type: str, title: str, url: str) -> None:
    with get_conn() as conn:
        conn.execute('INSERT INTO links(message_id, link_type, title, url) VALUES (?, ?, ?, ?)', (message_id, link_type, title, url))


def update_message_status(message_id: int, status: str) -> None:
    with get_conn() as conn:
        conn.execute('UPDATE messages SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (status, message_id))
        conn.execute('UPDATE summaries SET status = ? WHERE message_id = ?', (status, message_id))


def toggle_message_important(message_id: int, enabled: bool) -> None:
    with get_conn() as conn:
        conn.execute('UPDATE messages SET is_important = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (1 if enabled else 0, message_id))


def add_tag(message_id: int, tag: str) -> None:
    if not tag.strip():
        return
    with get_conn() as conn:
        conn.execute('INSERT INTO tags(name) VALUES (?) ON CONFLICT(name) DO NOTHING', (tag.strip(),))
        tag_row = conn.execute('SELECT id FROM tags WHERE name = ?', (tag.strip(),)).fetchone()
        if tag_row:
            conn.execute('INSERT INTO message_tags(message_id, tag_id, source, confidence, reason) VALUES (?, ?, ?, ?, ?) ON CONFLICT(message_id, tag_id) DO UPDATE SET source=excluded.source, confidence=excluded.confidence, reason=excluded.reason', (message_id, tag_row['id'], 'manual', 1.0, 'manual add'))
            tags = [row['name'] for row in conn.execute('SELECT t.name FROM tags t JOIN message_tags mt ON mt.tag_id = t.id WHERE mt.message_id = ? ORDER BY t.name', (message_id,)).fetchall()]
            conn.execute('UPDATE summaries SET tags_json = ? WHERE message_id = ?', (json.dumps(tags, ensure_ascii=False), message_id))


def remove_tag(message_id: int, tag: str) -> None:
    with get_conn() as conn:
        conn.execute('DELETE FROM message_tags WHERE message_id = ? AND tag_id IN (SELECT id FROM tags WHERE name = ?)', (message_id, tag.strip()))
        tags = [row['name'] for row in conn.execute('SELECT t.name FROM tags t JOIN message_tags mt ON mt.tag_id = t.id WHERE mt.message_id = ? ORDER BY t.name', (message_id,)).fetchall()]
        conn.execute('UPDATE summaries SET tags_json = ? WHERE message_id = ?', (json.dumps(tags, ensure_ascii=False), message_id))


def list_summary_failed_message_ids(limit: int = 100) -> list[int]:
    with get_conn() as conn:
        rows = conn.execute("SELECT m.id FROM messages m LEFT JOIN summaries s ON s.message_id = m.id WHERE s.id IS NULL OR s.tags_json LIKE '%요약실패%' ORDER BY COALESCE(m.sent_at, m.received_at) DESC LIMIT ?", (limit,)).fetchall()
        return [int(row['id']) for row in rows]


def create_issue_from_message(message_id: int, title: str, owner: str = '', due_date: str = '', priority: str = 'MEDIUM', summary: str = '', next_action: str = '') -> int:
    with get_conn() as conn:
        cur = conn.execute(
            '''INSERT INTO issues(title, source_message_id, status, owner, due_date, priority, summary, next_action, related_links_json)
               VALUES (?, ?, 'OPEN', ?, ?, ?, ?, ?, ?)''',
            (title, message_id, owner, due_date, priority, summary, next_action, json.dumps([], ensure_ascii=False)),
        )
        issue_id = int(cur.lastrowid)
        conn.execute('INSERT INTO issue_events(issue_id, event_type, detail_json) VALUES (?, ?, ?)', (issue_id, 'CREATED', json.dumps({'source_message_id': message_id}, ensure_ascii=False)))
        return issue_id


def list_issues(status: str = '') -> list[Any]:
    sql = 'SELECT * FROM issues WHERE 1=1'
    params: list[Any] = []
    if status:
        sql += ' AND status = ?'
        params.append(status)
    sql += ' ORDER BY CASE status WHEN "OPEN" THEN 1 WHEN "IN_PROGRESS" THEN 2 WHEN "HOLD" THEN 3 ELSE 4 END, due_date IS NULL, due_date, id DESC'
    with get_conn() as conn:
        return conn.execute(sql, params).fetchall()


def get_issue(issue_id: int) -> Any:
    with get_conn() as conn:
        return conn.execute('SELECT * FROM issues WHERE id = ?', (issue_id,)).fetchone()


def update_issue(issue_id: int, status: str, owner: str, due_date: str, priority: str, summary: str, next_action: str) -> None:
    with get_conn() as conn:
        conn.execute(
            '''UPDATE issues SET status=?, owner=?, due_date=?, priority=?, summary=?, next_action=?, updated_at=CURRENT_TIMESTAMP WHERE id=?''',
            (status, owner, due_date or None, priority, summary, next_action, issue_id),
        )
        conn.execute('INSERT INTO issue_events(issue_id, event_type, detail_json) VALUES (?, ?, ?)', (issue_id, 'UPDATED', json.dumps({'status': status, 'owner': owner, 'priority': priority}, ensure_ascii=False)))


def list_issue_events(issue_id: int) -> list[Any]:
    with get_conn() as conn:
        return conn.execute('SELECT * FROM issue_events WHERE issue_id = ? ORDER BY id DESC', (issue_id,)).fetchall()


def get_issue_links(issue_id: int) -> list[dict[str, str]]:
    issue = get_issue(issue_id)
    if not issue:
        return []
    try:
        data = json.loads(issue['related_links_json'] or '[]')
        return data if isinstance(data, list) else []
    except Exception:
        return []


def add_issue_link(issue_id: int, link_type: str, title: str, url: str) -> None:
    links = get_issue_links(issue_id)
    links.append({'link_type': link_type, 'title': title, 'url': url})
    with get_conn() as conn:
        conn.execute('UPDATE issues SET related_links_json = ?, updated_at=CURRENT_TIMESTAMP WHERE id = ?', (json.dumps(links, ensure_ascii=False), issue_id))


def build_period_summary(period_type: str = 'week', ref_date: datetime | None = None) -> dict[str, Any]:
    ref = ref_date or datetime.now(timezone.utc)
    if period_type == 'month':
        start = ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_key = start.strftime('%Y-%m')
    else:
        start = (ref - timedelta(days=ref.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        period_key = start.strftime('%Y-W%W')
    end = ref

    start_iso, end_iso = start.isoformat(), end.isoformat()
    with get_conn() as conn:
        period_count = conn.execute('SELECT COUNT(*) FROM messages WHERE COALESCE(sent_at, received_at) BETWEEN ? AND ?', (start_iso, end_iso)).fetchone()[0]
        important_count = conn.execute('SELECT COUNT(*) FROM messages WHERE is_important = 1 AND COALESCE(sent_at, received_at) BETWEEN ? AND ?', (start_iso, end_iso)).fetchone()[0]
        risk_count = conn.execute("SELECT COUNT(*) FROM summaries s JOIN messages m ON s.message_id = m.id WHERE s.risks_json NOT IN ('[]','','null') AND COALESCE(m.sent_at,m.received_at) BETWEEN ? AND ?", (start_iso, end_iso)).fetchone()[0]
        category_rows = conn.execute("SELECT COALESCE(s.category,'미분류') as category, COUNT(*) cnt FROM summaries s JOIN messages m ON s.message_id=m.id WHERE COALESCE(m.sent_at,m.received_at) BETWEEN ? AND ? GROUP BY COALESCE(s.category,'미분류') ORDER BY cnt DESC", (start_iso, end_iso)).fetchall()
        sender_top = conn.execute('SELECT from_email, COUNT(*) cnt FROM messages WHERE COALESCE(sent_at, received_at) BETWEEN ? AND ? GROUP BY from_email ORDER BY cnt DESC LIMIT 5', (start_iso, end_iso)).fetchall()
        action_item_mails = conn.execute("SELECT m.id, m.subject FROM messages m JOIN summaries s ON s.message_id = m.id WHERE s.action_items_json NOT IN ('[]','','null') AND COALESCE(m.sent_at,m.received_at) BETWEEN ? AND ? ORDER BY s.importance_score DESC LIMIT 8", (start_iso, end_iso)).fetchall()
        issue_converted = conn.execute('SELECT COUNT(*) FROM issues WHERE source_message_id IS NOT NULL AND created_at BETWEEN ? AND ?', (start_iso, end_iso)).fetchone()[0]
        summary_retry = conn.execute('SELECT COUNT(*) FROM summaries s JOIN messages m ON s.message_id=m.id WHERE s.retry_count > 0 AND COALESCE(m.sent_at,m.received_at) BETWEEN ? AND ?', (start_iso, end_iso)).fetchone()[0]
        summary_failed = conn.execute("SELECT COUNT(*) FROM summaries s JOIN messages m ON s.message_id=m.id WHERE s.tags_json LIKE '%요약실패%' AND COALESCE(m.sent_at,m.received_at) BETWEEN ? AND ?", (start_iso, end_iso)).fetchone()[0]

        summary = {
            'period_type': period_type,
            'period_key': period_key,
            'period_count': period_count,
            'important_count': important_count,
            'risk_count': risk_count,
            'category_rows': [dict(row) for row in category_rows],
            'sender_top': [dict(row) for row in sender_top],
            'action_item_mails': [dict(row) for row in action_item_mails],
            'issue_converted': issue_converted,
            'summary_retry': summary_retry,
            'summary_failed': summary_failed,
        }

        conn.execute(
            'INSERT INTO period_summaries(period_type, period_key, summary_json) VALUES (?, ?, ?) ON CONFLICT(period_type, period_key) DO UPDATE SET summary_json=excluded.summary_json, created_at=CURRENT_TIMESTAMP',
            (period_type, period_key, json.dumps(summary, ensure_ascii=False)),
        )
        return summary


def get_period_summary(period_type: str = 'week') -> dict[str, Any]:
    summary = build_period_summary(period_type=period_type)
    with get_conn() as conn:
        row = conn.execute('SELECT llm_summary FROM period_summaries WHERE period_type=? AND period_key=?', (summary['period_type'], summary['period_key'])).fetchone()
    summary['llm_summary'] = row['llm_summary'] if row else ''
    return summary


def save_period_llm_summary(period_type: str, period_key: str, llm_summary: str) -> None:
    with get_conn() as conn:
        conn.execute('UPDATE period_summaries SET llm_summary = ?, created_at=CURRENT_TIMESTAMP WHERE period_type=? AND period_key=?', (llm_summary, period_type, period_key))


def list_message_issues(message_id: int) -> list[Any]:
    with get_conn() as conn:
        return conn.execute('SELECT * FROM issues WHERE source_message_id = ? ORDER BY id DESC', (message_id,)).fetchall()


def tags_for_message(row: Any) -> list[str]:
    return _json_list(row['tags_json']) if row else []
