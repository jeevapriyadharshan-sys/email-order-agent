import smtplib
import ssl
from email.mime.text import MIMEText
from typing import Optional

SMTP_TIMEOUT = 15  # seconds


def send_confirmation(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    to_addr: str,
    subject: str,
    body: str,
    from_addr: Optional[str] = None,
    smtp_from: Optional[str] = None,
):
    """
    Generic SMTP sender using Brevo (smtp-relay.brevo.com).
    Works on Render free tier.
    """

    if not smtp_host or not to_addr:
        return

    from_final = (from_addr or smtp_from or smtp_user or "").strip()
    if not from_final:
        return

    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = from_final
    msg["To"] = to_addr
    msg["Subject"] = subject

    context = ssl.create_default_context()

    with smtplib.SMTP(smtp_host, smtp_port, timeout=SMTP_TIMEOUT) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)
        server.sendmail(from_final, [to_addr], msg.as_string())