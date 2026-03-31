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


def dashboard_stats() -> dict[str, Any]:
    with get_conn() as conn:
        total_messages = conn.execute('SELECT COUNT(*) FROM messages').fetchone()[0]
        total_summaries = conn.execute('SELECT COUNT(*) FROM summaries').fetchone()[0]
        attachments = conn.execute('SELECT COUNT(*) FROM attachments').fetchone()[0]
        action_required = conn.execute("SELECT COUNT(*) FROM summaries WHERE status = 'action_required'").fetchone()[0]
        high_priority = conn.execute('SELECT COUNT(*) FROM summaries WHERE importance_score >= 80').fetchone()[0]
        unsummarized = conn.execute(
            'SELECT COUNT(*) FROM messages m LEFT JOIN summaries s ON s.message_id = m.id WHERE s.id IS NULL'
        ).fetchone()[0]

        recent_messages = conn.execute(
            '''
            SELECT m.id, m.subject, m.from_email, m.sent_at, m.body_preview,
                   s.status, s.category, s.importance_score
            FROM messages m
            LEFT JOIN summaries s ON s.message_id = m.id
            ORDER BY COALESCE(m.sent_at, m.received_at) DESC
            LIMIT 12
            '''
        ).fetchall()
        category_rows = conn.execute(
            '''
            SELECT COALESCE(category, '미분류') AS category, COUNT(*) AS cnt
            FROM summaries
            GROUP BY COALESCE(category, '미분류')
            ORDER BY cnt DESC
            '''
        ).fetchall()
        jobs = conn.execute(
            'SELECT id, job_type, status, started_at, finished_at, message FROM jobs ORDER BY id DESC LIMIT 12'
        ).fetchall()
    return {
        'total_messages': total_messages,
        'total_summaries': total_summaries,
        'attachments': attachments,
        'action_required': action_required,
        'high_priority': high_priority,
        'unsummarized': unsummarized,
        'recent_messages': recent_messages,
        'category_rows': category_rows,
        'jobs': jobs,
    }


def list_messages(
    q: str = '',
    category: str = '',
    has_summary: str = '',
    status: str = '',
    tag: str = '',
    limit: int = 150,
) -> list[Any]:
    sql = '''
    SELECT m.*, s.summary_short, s.category, s.importance_score, s.status AS summary_status, s.tags_json
    FROM messages m
    LEFT JOIN summaries s ON s.message_id = m.id
    WHERE 1=1
    '''
    params: list[Any] = []
    if q:
        sql += ' AND (m.subject LIKE ? OR m.from_email LIKE ? OR m.text_body LIKE ?)'
        like = f'%{q}%'
        params.extend([like, like, like])
    if category:
        sql += ' AND s.category = ?'
        params.append(category)
    if has_summary == 'Y':
        sql += ' AND s.id IS NOT NULL'
    elif has_summary == 'N':
        sql += ' AND s.id IS NULL'
    if status:
        sql += ' AND COALESCE(s.status, "new") = ?'
        params.append(status)
    if tag:
        sql += ' AND EXISTS (SELECT 1 FROM message_tags mt JOIN tags t ON t.id = mt.tag_id WHERE mt.message_id = m.id AND t.name LIKE ?)'
        params.append(f'%{tag}%')

    sql += ' ORDER BY COALESCE(m.sent_at, m.received_at) DESC LIMIT ?'
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return rows


def get_message(message_id: int) -> Any:
    with get_conn() as conn:
        return conn.execute(
            '''
            SELECT m.*, s.summary_short, s.summary_long, s.keywords_json,
                   s.risks_json, s.action_items_json, s.category, s.importance_score,
                   s.status as summary_status, s.tags_json
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


def get_thread(message_id: int) -> list[Any]:
    with get_conn() as conn:
        current = conn.execute('SELECT thread_key FROM messages WHERE id = ?', (message_id,)).fetchone()
        if not current or not current['thread_key']:
            return []
        return conn.execute(
            '''
            SELECT m.id, m.subject, m.from_email, m.sent_at,
                   s.status as summary_status, s.importance_score
            FROM messages m
            LEFT JOIN summaries s ON s.message_id = m.id
            WHERE m.thread_key = ?
            ORDER BY COALESCE(m.sent_at, m.received_at)
            ''',
            (current['thread_key'],),
        ).fetchall()


def upsert_summary(
    message_id: int,
    model_name: str,
    data: dict[str, Any],
    raw_response: dict[str, Any] | None = None,
    retry_count: int = 0,
) -> None:
    tags = data.get('tags', [])
    with get_conn() as conn:
        conn.execute(
            '''
            INSERT INTO summaries(
                message_id, model_name, summary_short, summary_long, keywords_json,
                risks_json, action_items_json, category, status, tags_json, importance_score, retry_count, raw_response
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(message_id) DO UPDATE SET
                model_name=excluded.model_name,
                summary_short=excluded.summary_short,
                summary_long=excluded.summary_long,
                keywords_json=excluded.keywords_json,
                risks_json=excluded.risks_json,
                action_items_json=excluded.action_items_json,
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
                data.get('category', '기타'),
                data.get('status', 'triaged'),
                json.dumps(tags, ensure_ascii=False),
                int(data.get('importance_score', 0) or 0),
                retry_count,
                json.dumps(raw_response or data, ensure_ascii=False),
            ),
        )
        _sync_tags(conn, message_id, tags)


def insert_link(message_id: int, link_type: str, title: str, url: str) -> None:
    with get_conn() as conn:
        conn.execute(
            'INSERT INTO links(message_id, link_type, title, url) VALUES (?, ?, ?, ?)',
            (message_id, link_type, title, url),
        )


def tags_for_message(row: Any) -> list[str]:
    return _json_list(row['tags_json']) if row else []
