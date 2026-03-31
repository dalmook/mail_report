from email.message import EmailMessage

from app.services.eml_parser import parse_eml_bytes


def test_thread_key_uses_references_when_no_in_reply_to() -> None:
    msg = EmailMessage()
    msg['Subject'] = 'Re: 운영 보고'
    msg['From'] = 'a@example.com'
    msg['To'] = 'b@example.com'
    msg['References'] = '<root@example.com> <parent@example.com>'
    msg.set_content('내용')

    parsed = parse_eml_bytes(msg.as_bytes())

    assert parsed.thread_key == '<parent@example.com>'
