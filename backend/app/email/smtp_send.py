import smtplib
from email.mime.text import MIMEText
from typing import Optional


def send_confirmation(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    to_addr: str,
    subject: str,
    body: str,
    from_addr: Optional[str] = None,
    smtp_from: Optional[str] = None,  # accept old keyword too
):
    """
    Generic SMTP sender used for:
    - reconfirmation email (order created)
    - missing-fields request email (human review)
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

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        if smtp_user:
            server.login(smtp_user, smtp_password)
        server.sendmail(from_final, [to_addr], msg.as_string())