import os
from typing import Optional

try:
    import resend
except ImportError:
    resend = None  # type: ignore


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
    Sends email via Resend API (HTTP-based, works on Render free tier).
    Falls back gracefully if RESEND_API_KEY is not set.
    """

    if not to_addr:
        return

    from_final = (from_addr or smtp_from or smtp_user or "").strip()
    if not from_final:
        return

    resend_api_key = os.environ.get("RESEND_API_KEY", "")

    if not resend_api_key:
        raise RuntimeError("RESEND_API_KEY is not set. Cannot send email.")

    if resend is None:
        raise RuntimeError("resend package is not installed. Run: pip install resend")

    resend.api_key = resend_api_key

    params = {
        "from": from_final,
        "to": [to_addr],
        "subject": subject,
        "text": body,
    }

    resend.Emails.send(params)