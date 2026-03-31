from __future__ import annotations

import json
from typing import Any

from ..db import get_conn


def dashboard_stats() -> dict[str, Any]:
    with get_conn() as conn:
        total_messages = conn.execute('SELECT COUNT(*) FROM messages').fetchone()[0]
        total_summaries = conn.execute('SELECT COUNT(*) FROM summaries').fetchone()[0]
        attachments = conn.execute('SELECT COUNT(*) FROM attachments').fetchone()[0]
        recent_messages = conn.execute(
            '''
            SELECT id, subject, from_email, sent_at, body_preview
            FROM messages
            ORDER BY COALESCE(sent_at, received_at) DESC
            LIMIT 10
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
            'SELECT id, job_type, status, started_at, finished_at, message FROM jobs ORDER BY id DESC LIMIT 10'
        ).fetchall()
    return {
        'total_messages': total_messages,
        'total_summaries': total_summaries,
        'attachments': attachments,
        'recent_messages': recent_messages,
        'category_rows': category_rows,
        'jobs': jobs,
    }


def list_messages(q: str = '', category: str = '', has_summary: str = '', limit: int = 100) -> list[Any]:
    sql = '''
    SELECT m.*, s.summary_short, s.category, s.importance_score
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
    sql += ' ORDER BY COALESCE(m.sent_at, m.received_at) DESC LIMIT ?'
    params.append(limit)
    with get_conn() as conn:
        return conn.execute(sql, params).fetchall()


def get_message(message_id: int) -> Any:
    with get_conn() as conn:
        row = conn.execute(
            '''
            SELECT m.*, s.summary_short, s.summary_long, s.keywords_json,
                   s.risks_json, s.action_items_json, s.category, s.importance_score
            FROM messages m
            LEFT JOIN summaries s ON s.message_id = m.id
            WHERE m.id = ?
            ''',
            (message_id,),
        ).fetchone()
        return row


def get_attachments(message_id: int) -> list[Any]:
    with get_conn() as conn:
        return conn.execute('SELECT * FROM attachments WHERE message_id = ? ORDER BY id', (message_id,)).fetchall()


def get_links(message_id: int) -> list[Any]:
    with get_conn() as conn:
        return conn.execute('SELECT * FROM links WHERE message_id = ? ORDER BY id DESC', (message_id,)).fetchall()


def get_thread(message_id: int) -> list[Any]:
    with get_conn() as conn:
        current = conn.execute('SELECT thread_key FROM messages WHERE id = ?', (message_id,)).fetchone()
        if not current:
            return []
        return conn.execute(
            'SELECT id, subject, from_email, sent_at FROM messages WHERE thread_key = ? ORDER BY COALESCE(sent_at, received_at)',
            (current['thread_key'],),
        ).fetchall()


def upsert_summary(message_id: int, model_name: str, data: dict[str, Any], raw_response: dict[str, Any] | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            '''
            INSERT INTO summaries(
                message_id, model_name, summary_short, summary_long, keywords_json,
                risks_json, action_items_json, category, importance_score, raw_response
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(message_id) DO UPDATE SET
                model_name=excluded.model_name,
                summary_short=excluded.summary_short,
                summary_long=excluded.summary_long,
                keywords_json=excluded.keywords_json,
                risks_json=excluded.risks_json,
                action_items_json=excluded.action_items_json,
                category=excluded.category,
                importance_score=excluded.importance_score,
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
                int(data.get('importance_score', 0) or 0),
                json.dumps(raw_response or data, ensure_ascii=False),
            ),
        )


def insert_link(message_id: int, link_type: str, title: str, url: str) -> None:
    with get_conn() as conn:
        conn.execute(
            'INSERT INTO links(message_id, link_type, title, url) VALUES (?, ?, ?, ?)',
            (message_id, link_type, title, url),
        )
