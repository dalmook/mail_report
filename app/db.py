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
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    return conn


@contextmanager
def get_conn() -> Iterable[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    cols = {row['name'] for row in conn.execute(f'PRAGMA table_info({table})').fetchall()}
    if column not in cols:
        conn.execute(f'ALTER TABLE {table} ADD COLUMN {ddl}')


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            '''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pop3_uidl TEXT UNIQUE,
                message_id TEXT,
                subject TEXT,
                subject_normalized TEXT,
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
                in_reply_to TEXT,
                references_header TEXT,
                source_mailbox TEXT DEFAULT 'pop3',
                has_attachment INTEGER DEFAULT 0,
                is_important INTEGER DEFAULT 0,
                thread_key TEXT,
                eml_path TEXT NOT NULL,
                status TEXT DEFAULT 'new',
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
                entities_people_json TEXT,
                entities_orgs_json TEXT,
                deadlines_json TEXT,
                numeric_facts_json TEXT,
                category TEXT,
                status TEXT DEFAULT 'new',
                tags_json TEXT,
                importance_score INTEGER,
                retry_count INTEGER DEFAULT 0,
                raw_response TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS summary_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                model_name TEXT,
                summary_json TEXT NOT NULL,
                reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS message_tags (
                message_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (message_id, tag_id),
                FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
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

            CREATE INDEX IF NOT EXISTS idx_messages_uidl ON messages(pop3_uidl);
            CREATE INDEX IF NOT EXISTS idx_messages_sent_at ON messages(sent_at);
            CREATE INDEX IF NOT EXISTS idx_messages_thread_key ON messages(thread_key);
            CREATE INDEX IF NOT EXISTS idx_messages_from_email ON messages(from_email);
            CREATE INDEX IF NOT EXISTS idx_messages_important ON messages(is_important);
            CREATE INDEX IF NOT EXISTS idx_links_message_id ON links(message_id);
            CREATE INDEX IF NOT EXISTS idx_summaries_status ON summaries(status);
            CREATE INDEX IF NOT EXISTS idx_summaries_category ON summaries(category);
            CREATE INDEX IF NOT EXISTS idx_summaries_importance ON summaries(importance_score);
            CREATE INDEX IF NOT EXISTS idx_summary_history_message_id ON summary_history(message_id);
            CREATE INDEX IF NOT EXISTS idx_attachments_message_id ON attachments(message_id);
            CREATE INDEX IF NOT EXISTS idx_message_tags_tag_id ON message_tags(tag_id);
            '''
        )

        _ensure_column(conn, 'messages', 'subject_normalized', 'subject_normalized TEXT')
        _ensure_column(conn, 'messages', 'in_reply_to', 'in_reply_to TEXT')
        _ensure_column(conn, 'messages', 'references_header', 'references_header TEXT')
        _ensure_column(conn, 'messages', 'source_mailbox', "source_mailbox TEXT DEFAULT 'pop3'")
        _ensure_column(conn, 'messages', 'is_important', 'is_important INTEGER DEFAULT 0')

        _ensure_column(conn, 'summaries', 'status', "status TEXT DEFAULT 'new'")
        _ensure_column(conn, 'summaries', 'tags_json', 'tags_json TEXT')
        _ensure_column(conn, 'summaries', 'retry_count', 'retry_count INTEGER DEFAULT 0')
        _ensure_column(conn, 'summaries', 'entities_people_json', 'entities_people_json TEXT')
        _ensure_column(conn, 'summaries', 'entities_orgs_json', 'entities_orgs_json TEXT')
        _ensure_column(conn, 'summaries', 'deadlines_json', 'deadlines_json TEXT')
        _ensure_column(conn, 'summaries', 'numeric_facts_json', 'numeric_facts_json TEXT')


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
