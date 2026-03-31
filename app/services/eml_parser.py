from __future__ import annotations

import mimetypes
import re
from dataclasses import dataclass, field
from datetime import datetime
from email import policy
from email.header import decode_header, make_header
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


@dataclass
class ParsedAttachment:
    filename: str
    content_type: str
    payload: bytes
    is_inline: bool = False
    content_id: str | None = None


@dataclass
class ParsedEmail:
    message_id: str | None
    subject: str
    from_name: str
    from_email: str
    to_emails: str
    cc_emails: str
    sent_at: str | None
    received_at: str | None
    text_body: str
    html_body: str
    body_preview: str
    importance: str
    thread_key: str
    attachments: list[ParsedAttachment] = field(default_factory=list)


RE_PREFIX = re.compile(r'^(re|fw|fwd)\s*:\s*', re.IGNORECASE)


def _decode_text(value: str | None) -> str:
    if not value:
        return ''
    try:
        return str(make_header(decode_header(value))).strip()
    except Exception:
        return value.strip()


def _flatten_addresses(raw_value: str | None) -> tuple[str, str]:
    pairs = getaddresses([raw_value or ''])
    names = []
    emails = []
    for name, email in pairs:
        if name:
            names.append(_decode_text(name))
        if email:
            emails.append(email.strip())
    joined_names = ', '.join([n for n in names if n])
    joined_emails = ', '.join([e for e in emails if e])
    return joined_names, joined_emails


def _as_iso(value: str | None) -> str | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt is None:
            return None
        return dt.isoformat()
    except Exception:
        return None


def _html_to_text(html: str) -> str:
    if not html:
        return ''
    soup = BeautifulSoup(html, 'html.parser')
    return soup.get_text('\n', strip=True)


def _clean_preview(text: str, limit: int = 220) -> str:
    compact = re.sub(r'\s+', ' ', text or '').strip()
    return compact[:limit]


def _thread_key(subject: str, message_id: str | None) -> str:
    normalized = RE_PREFIX.sub('', subject or '').strip().lower()
    if normalized:
        return normalized[:200]
    return (message_id or 'no-thread')[:200]


def parse_eml_bytes(raw_bytes: bytes) -> ParsedEmail:
    msg = BytesParser(policy=policy.default).parsebytes(raw_bytes)

    subject = _decode_text(msg.get('Subject', ''))
    from_name, from_email = _flatten_addresses(msg.get('From'))
    _, to_emails = _flatten_addresses(msg.get('To'))
    _, cc_emails = _flatten_addresses(msg.get('Cc'))
    message_id = msg.get('Message-ID')
    sent_at = _as_iso(msg.get('Date'))
    received_at = datetime.now().isoformat()
    importance = (msg.get('Importance') or msg.get('X-Priority') or '').strip() or 'normal'

    text_body = ''
    html_body = ''
    attachments: list[ParsedAttachment] = []

    if msg.is_multipart():
        for part in msg.walk():
            content_disposition = (part.get_content_disposition() or '').lower()
            content_type = (part.get_content_type() or 'application/octet-stream').lower()
            payload = part.get_payload(decode=True) or b''
            filename = _decode_text(part.get_filename())

            if content_disposition == 'attachment' or filename:
                attachments.append(
                    ParsedAttachment(
                        filename=filename or 'attachment.bin',
                        content_type=content_type,
                        payload=payload,
                        is_inline=content_disposition == 'inline',
                        content_id=part.get('Content-ID'),
                    )
                )
                continue

            if content_type == 'text/plain' and not text_body:
                charset = part.get_content_charset() or 'utf-8'
                text_body = payload.decode(charset, errors='replace')
            elif content_type == 'text/html' and not html_body:
                charset = part.get_content_charset() or 'utf-8'
                html_body = payload.decode(charset, errors='replace')
    else:
        payload = msg.get_payload(decode=True) or b''
        content_type = msg.get_content_type()
        charset = msg.get_content_charset() or 'utf-8'
        if content_type == 'text/html':
            html_body = payload.decode(charset, errors='replace')
        else:
            text_body = payload.decode(charset, errors='replace')

    if not text_body and html_body:
        text_body = _html_to_text(html_body)

    return ParsedEmail(
        message_id=message_id,
        subject=subject or '(제목 없음)',
        from_name=from_name,
        from_email=from_email,
        to_emails=to_emails,
        cc_emails=cc_emails,
        sent_at=sent_at,
        received_at=received_at,
        text_body=text_body,
        html_body=html_body,
        body_preview=_clean_preview(text_body or html_body),
        importance=importance,
        thread_key=_thread_key(subject, message_id),
        attachments=attachments,
    )


def guess_content_type(filename: str) -> str:
    content_type, _ = mimetypes.guess_type(filename)
    return content_type or 'application/octet-stream'
