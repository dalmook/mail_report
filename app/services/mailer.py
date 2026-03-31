from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from ..config import settings


class MailerDisabledError(RuntimeError):
    pass


def send_html_mail(subject: str, html_body: str, to_emails: list[str]) -> None:
    if not settings.smtp_enabled:
        raise MailerDisabledError('SMTP is disabled. Set SMTP_ENABLED=true')
    if not settings.smtp_host or not settings.report_from_email or not to_emails:
        raise MailerDisabledError('SMTP host/from/to are required for sending report mail')

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = settings.report_from_email
    msg['To'] = ', '.join(to_emails)
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_pass)
        server.sendmail(settings.report_from_email, to_emails, msg.as_string())
