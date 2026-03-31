from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterable

from .config import settings


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


@contextmanager
def get_conn() -> Iterable[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            '''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pop3_uidl TEXT UNIQUE,
                message_id TEXT,
                subject TEXT,
                from_name TEXT,
                from_email TEXT,
                to_emails TEXT,
                cc_emails TEXT,
                sent_at TEXT,
                received_at TEXT,
                text_body TEXT,
                html_body TEXT,
                body_preview TEXT,
                importance TEXT,
                has_attachment INTEGER DEFAULT 0,
                thread_key TEXT,
                eml_path TEXT NOT NULL,
                status TEXT DEFAULT 'new',
                external_link TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                filename TEXT,
                content_type TEXT,
                file_size INTEGER,
                file_path TEXT,
                is_inline INTEGER DEFAULT 0,
                content_id TEXT,
                FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL UNIQUE,
                model_name TEXT,
                summary_short TEXT,
                summary_long TEXT,
                keywords_json TEXT,
                risks_json TEXT,
                action_items_json TEXT,
                category TEXT,
                importance_score INTEGER,
                raw_response TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                link_type TEXT DEFAULT 'manual',
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT DEFAULT CURRENT_TIMESTAMP,
                finished_at TEXT,
                message TEXT,
                detail_json TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_messages_sent_at ON messages(sent_at);
            CREATE INDEX IF NOT EXISTS idx_messages_thread_key ON messages(thread_key);
            CREATE INDEX IF NOT EXISTS idx_messages_from_email ON messages(from_email);
            CREATE INDEX IF NOT EXISTS idx_links_message_id ON links(message_id);
            '''
        )


def create_job(job_type: str, status: str = 'running', message: str = '', detail: dict[str, Any] | None = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            'INSERT INTO jobs(job_type, status, message, detail_json) VALUES (?, ?, ?, ?)',
            (job_type, status, message, json.dumps(detail or {}, ensure_ascii=False)),
        )
        return int(cur.lastrowid)


def finish_job(job_id: int, status: str, message: str = '', detail: dict[str, Any] | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            '''
            UPDATE jobs
            SET status = ?, finished_at = CURRENT_TIMESTAMP, message = ?, detail_json = ?
            WHERE id = ?
            ''',
            (status, message, json.dumps(detail or {}, ensure_ascii=False), job_id),
        )
