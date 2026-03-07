import os
import json
import urllib.request
import urllib.error
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
    smtp_from: Optional[str] = None,
):
    """
    Sends email via Brevo HTTP API.
    Works on Render free tier (no SMTP ports needed).
    Requires BREVO_API_KEY environment variable.
    """

    if not to_addr:
        return

    from_final = (from_addr or smtp_from or smtp_user or "").strip()
    if not from_final:
        return

    api_key = os.environ.get("BREVO_API_KEY", "")
    if not api_key:
        raise RuntimeError("BREVO_API_KEY is not set. Cannot send email.")

    # Parse to_addr — handle "Name <email>" format
    to_email = to_addr.strip()
    to_name = ""
    if "<" in to_addr and ">" in to_addr:
        to_name = to_addr.split("<")[0].strip()
        to_email = to_addr.split("<")[1].replace(">", "").strip()

    payload = {
        "sender": {"email": from_final},
        "to": [{"email": to_email, "name": to_name or to_email}],
        "subject": subject,
        "textContent": body,
    }

    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=data,
        headers={
            "Content-Type": "application/json",
            "api-key": api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise RuntimeError(f"Brevo API error {e.code}: {error_body}")