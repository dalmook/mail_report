from __future__ import annotations

import os
import poplib
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from ..config import settings
from ..db import get_conn
from .eml_parser import parse_eml_bytes


def _save_eml(raw_bytes: bytes, sent_at_iso: str | None) -> Path:
    dt = datetime.fromisoformat(sent_at_iso) if sent_at_iso else datetime.now()
    target_dir = settings.storage_root / 'eml' / f'{dt.year:04d}' / f'{dt.month:02d}'
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f'{dt.strftime("%Y%m%d_%H%M%S_%f")}.eml'
    file_path = target_dir / filename
    file_path.write_bytes(raw_bytes)
    return file_path


def _save_attachment(message_id: int, attachment: Any, sent_at_iso: str | None) -> str:
    dt = datetime.fromisoformat(sent_at_iso) if sent_at_iso else datetime.now()
    target_dir = settings.storage_root / 'attachments' / f'{dt.year:04d}' / f'{dt.month:02d}' / str(message_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = attachment.filename.replace('/', '_').replace('\\', '_')
    file_path = target_dir / safe_name
    file_path.write_bytes(attachment.payload)
    return str(file_path)


def _insert_message(uidl: str, parsed: Any, eml_path: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            '''
            INSERT INTO messages(
                pop3_uidl, message_id, subject, from_name, from_email, to_emails, cc_emails,
                sent_at, received_at, text_body, html_body, body_preview, importance,
                has_attachment, thread_key, eml_path, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new')
            ''',
            (
                uidl,
                parsed.message_id,
                parsed.subject,
                parsed.from_name,
                parsed.from_email,
                parsed.to_emails,
                parsed.cc_emails,
                parsed.sent_at,
                parsed.received_at,
                parsed.text_body,
                parsed.html_body,
                parsed.body_preview,
                parsed.importance,
                1 if parsed.attachments else 0,
                parsed.thread_key,
                eml_path,
            ),
        )
        return int(cur.lastrowid)


def _insert_attachments(message_row_id: int, parsed: Any) -> None:
    with get_conn() as conn:
        for attachment in parsed.attachments:
            file_path = _save_attachment(message_row_id, attachment, parsed.sent_at)
            conn.execute(
                '''
                INSERT INTO attachments(message_id, filename, content_type, file_size, file_path, is_inline, content_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    message_row_id,
                    attachment.filename,
                    attachment.content_type,
                    len(attachment.payload),
                    file_path,
                    1 if attachment.is_inline else 0,
                    attachment.content_id,
                ),
            )


def ingest_from_pop3() -> dict[str, Any]:
    if not settings.pop3_host or not settings.pop3_user or not settings.pop3_pass:
        return {'fetched': 0, 'stored': 0, 'skipped': 0, 'errors': ['POP3 env is not configured.']}

    client = None
    result = {'fetched': 0, 'stored': 0, 'skipped': 0, 'errors': []}

    try:
        client = poplib.POP3_SSL(settings.pop3_host, settings.pop3_port) if settings.pop3_use_ssl else poplib.POP3(settings.pop3_host, settings.pop3_port)
        client.user(settings.pop3_user)
        client.pass_(settings.pop3_pass)

        _, uidl_lines, _ = client.uidl()
        uidl_pairs = []
        for line in uidl_lines[-settings.pop3_max_messages_per_run :]:
            parts = line.decode('utf-8', errors='replace').split()
            if len(parts) == 2:
                uidl_pairs.append((int(parts[0]), parts[1]))

        for msg_num, uidl in uidl_pairs:
            result['fetched'] += 1
            with get_conn() as conn:
                exists = conn.execute('SELECT id FROM messages WHERE pop3_uidl = ?', (uidl,)).fetchone()
            if exists:
                result['skipped'] += 1
                continue

            try:
                _, lines, _ = client.retr(msg_num)
                raw_bytes = b'\r\n'.join(lines)
                parsed = parse_eml_bytes(raw_bytes)
                eml_path = _save_eml(raw_bytes, parsed.sent_at)
                message_row_id = _insert_message(uidl, parsed, str(eml_path))
                _insert_attachments(message_row_id, parsed)
                result['stored'] += 1

                if settings.pop3_delete_after_fetch:
                    client.dele(msg_num)
            except sqlite3.IntegrityError:
                result['skipped'] += 1
            except Exception as exc:
                result['errors'].append(f'#{msg_num} {exc}')

        return result
    finally:
        if client is not None:
            try:
                client.quit()
            except Exception:
                pass
