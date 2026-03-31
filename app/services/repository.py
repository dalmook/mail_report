from __future__ import annotations

import json
from typing import Any

from ..db import get_conn


def _json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _sync_tags(conn: Any, message_id: int, tags: list[str]) -> None:
    clean_tags = [tag.strip() for tag in tags if tag and tag.strip()]
    conn.execute('DELETE FROM message_tags WHERE message_id = ?', (message_id,))
    for tag in sorted(set(clean_tags)):
        conn.execute('INSERT INTO tags(name) VALUES (?) ON CONFLICT(name) DO NOTHING', (tag,))
        tag_row = conn.execute('SELECT id FROM tags WHERE name = ?', (tag,)).fetchone()
        if tag_row:
            conn.execute(
                'INSERT INTO message_tags(message_id, tag_id) VALUES (?, ?) ON CONFLICT(message_id, tag_id) DO NOTHING',
                (message_id, tag_row['id']),
            )


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

        category_rows = conn.execute(
            "SELECT COALESCE(category, '미분류') AS category, COUNT(*) AS cnt FROM summaries GROUP BY COALESCE(category, '미분류') ORDER BY cnt DESC"
        ).fetchall()
        sender_top = conn.execute(
            "SELECT from_email, COUNT(*) AS cnt FROM messages WHERE from_email <> '' GROUP BY from_email ORDER BY cnt DESC LIMIT 8"
        ).fetchall()

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
        jobs = conn.execute('SELECT id, job_type, status, started_at, finished_at, message FROM jobs ORDER BY id DESC LIMIT 12').fetchall()

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
        'jobs': jobs,
    }


def list_messages(
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
    limit: int = 200,
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
                   s.status as summary_status, s.tags_json, s.entities_people_json,
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
            '''
            SELECT m.id, m.subject, m.from_email, m.sent_at
            FROM messages m
            WHERE m.subject_normalized = ? AND m.id <> ?
            ORDER BY COALESCE(m.sent_at, m.received_at) DESC
            LIMIT ?
            ''',
            (current['subject_normalized'], message_id, limit),
        ).fetchall()


def get_summary_history(message_id: int, limit: int = 10) -> list[Any]:
    with get_conn() as conn:
        return conn.execute(
            'SELECT id, model_name, reason, created_at FROM summary_history WHERE message_id = ? ORDER BY id DESC LIMIT ?',
            (message_id, limit),
        ).fetchall()


def upsert_summary(
    message_id: int,
    model_name: str,
    data: dict[str, Any],
    raw_response: dict[str, Any] | None = None,
    retry_count: int = 0,
    reason: str = 'summarize',
) -> None:
    tags = data.get('tags', [])
    with get_conn() as conn:
        prev = conn.execute('SELECT * FROM summaries WHERE message_id = ?', (message_id,)).fetchone()
        if prev:
            prev_payload = {
                'summary_short': prev['summary_short'],
                'summary_long': prev['summary_long'],
                'category': prev['category'],
                'status': prev['status'],
                'importance_score': prev['importance_score'],
            }
            conn.execute(
                'INSERT INTO summary_history(message_id, model_name, summary_json, reason) VALUES (?, ?, ?, ?)',
                (message_id, prev['model_name'], json.dumps(prev_payload, ensure_ascii=False), reason),
            )

        conn.execute(
            '''
            INSERT INTO summaries(
                message_id, model_name, summary_short, summary_long, keywords_json,
                risks_json, action_items_json, entities_people_json, entities_orgs_json,
                deadlines_json, numeric_facts_json, category, status, tags_json,
                importance_score, retry_count, raw_response
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(message_id) DO UPDATE SET
                model_name=excluded.model_name,
                summary_short=excluded.summary_short,
                summary_long=excluded.summary_long,
                keywords_json=excluded.keywords_json,
                risks_json=excluded.risks_json,
                action_items_json=excluded.action_items_json,
                entities_people_json=excluded.entities_people_json,
                entities_orgs_json=excluded.entities_orgs_json,
                deadlines_json=excluded.deadlines_json,
                numeric_facts_json=excluded.numeric_facts_json,
                category=excluded.category,
                status=excluded.status,
                tags_json=excluded.tags_json,
                importance_score=excluded.importance_score,
                retry_count=excluded.retry_count,
                raw_response=excluded.raw_response,
                created_at=CURRENT_TIMESTAMP
            ''',
            (
                message_id,
                model_name,
                data.get('summary_short', ''),
                data.get('summary_long', ''),
                json.dumps(data.get('keywords', []), ensure_ascii=False),
                json.dumps(data.get('risks', []), ensure_ascii=False),
                json.dumps(data.get('action_items', []), ensure_ascii=False),
                json.dumps(data.get('entities_people', []), ensure_ascii=False),
                json.dumps(data.get('entities_orgs', []), ensure_ascii=False),
                json.dumps(data.get('deadlines', []), ensure_ascii=False),
                json.dumps(data.get('numeric_facts', []), ensure_ascii=False),
                data.get('category', '기타'),
                data.get('status', 'new'),
                json.dumps(tags, ensure_ascii=False),
                int(data.get('importance_score', 0) or 0),
                retry_count,
                json.dumps(raw_response or data, ensure_ascii=False),
            ),
        )
        _sync_tags(conn, message_id, tags)


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
            conn.execute('INSERT INTO message_tags(message_id, tag_id) VALUES (?, ?) ON CONFLICT(message_id, tag_id) DO NOTHING', (message_id, tag_row['id']))
            tags = [row['name'] for row in conn.execute('SELECT t.name FROM tags t JOIN message_tags mt ON mt.tag_id = t.id WHERE mt.message_id = ? ORDER BY t.name', (message_id,)).fetchall()]
            conn.execute('UPDATE summaries SET tags_json = ? WHERE message_id = ?', (json.dumps(tags, ensure_ascii=False), message_id))


def remove_tag(message_id: int, tag: str) -> None:
    with get_conn() as conn:
        conn.execute(
            'DELETE FROM message_tags WHERE message_id = ? AND tag_id IN (SELECT id FROM tags WHERE name = ?)',
            (message_id, tag.strip()),
        )
        tags = [row['name'] for row in conn.execute('SELECT t.name FROM tags t JOIN message_tags mt ON mt.tag_id = t.id WHERE mt.message_id = ? ORDER BY t.name', (message_id,)).fetchall()]
        conn.execute('UPDATE summaries SET tags_json = ? WHERE message_id = ?', (json.dumps(tags, ensure_ascii=False), message_id))


def list_summary_failed_message_ids(limit: int = 100) -> list[int]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT m.id FROM messages m LEFT JOIN summaries s ON s.message_id = m.id WHERE s.id IS NULL OR s.tags_json LIKE '%요약실패%' ORDER BY COALESCE(m.sent_at, m.received_at) DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [int(row['id']) for row in rows]


def tags_for_message(row: Any) -> list[str]:
    return _json_list(row['tags_json']) if row else []
