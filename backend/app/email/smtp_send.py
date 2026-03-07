import smtplib
import ssl
from email.mime.text import MIMEText
from typing import Optional

SMTP_TIMEOUT = 10  # seconds


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
    Generic SMTP sender used for:
    - reconfirmation email (order created)
    - missing-fields request email (human review)
    Supports both SSL (port 465) and STARTTLS (port 587).
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

    # Use SSL (port 465) or STARTTLS (port 587)
    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=SMTP_TIMEOUT) as server:
            if smtp_user:
                server.login(smtp_user, smtp_password)
            server.sendmail(from_final, [to_addr], msg.as_string())
    else:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=SMTP_TIMEOUT) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            if smtp_user:
                server.login(smtp_user, smtp_password)
            server.sendmail(from_final, [to_addr], msg.as_string())