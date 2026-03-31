from email.message import EmailMessage

from app.services.eml_parser import parse_eml_bytes


def _to_bytes(msg: EmailMessage) -> bytes:
    return msg.as_bytes()


def test_thread_key_prefers_in_reply_to() -> None:
    msg = EmailMessage()
    msg['Subject'] = 'Re: Weekly Ops'
    msg['From'] = 'ops@example.com'
    msg['To'] = 'team@example.com'
    msg['Message-ID'] = '<child@example.com>'
    msg['In-Reply-To'] = '<parent@example.com>'
    msg.set_content('hello')

    parsed = parse_eml_bytes(_to_bytes(msg))

    assert parsed.thread_key == '<parent@example.com>'
    assert parsed.subject_normalized == 'weekly ops'


def test_thread_key_falls_back_to_normalized_subject() -> None:
    msg = EmailMessage()
    msg['Subject'] = 'Fwd: Incident Report'
    msg['From'] = 'ops@example.com'
    msg['To'] = 'team@example.com'
    msg.set_content('body')

    parsed = parse_eml_bytes(_to_bytes(msg))

    assert parsed.thread_key == 'incident report'


def test_html_mail_generates_text_preview() -> None:
    msg = EmailMessage()
    msg['Subject'] = 'HTML test'
    msg['From'] = 'a@example.com'
    msg['To'] = 'b@example.com'
    msg.add_alternative('<html><body><h1>Hello</h1><p>World</p></body></html>', subtype='html')

    parsed = parse_eml_bytes(_to_bytes(msg))

    assert 'Hello' in parsed.text_body
    assert parsed.body_preview
