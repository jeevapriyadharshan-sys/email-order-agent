import imaplib
import email
from email.header import decode_header
from typing import List, Dict, Optional
import os


def _decode_subject(msg) -> str:
    try:
        dh = decode_header(msg.get("Subject", ""))
        if not dh:
            return ""
        subject, enc = dh[0]
        if isinstance(subject, bytes):
            return subject.decode(enc or "utf-8", errors="ignore")
        return str(subject or "")
    except Exception:
        return ""


def _extract_body_text(msg) -> str:
    body_text = ""
    try:
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disp = str(part.get("Content-Disposition") or "")
                if ctype == "text/plain" and "attachment" not in disp.lower():
                    payload = part.get_payload(decode=True)
                    if payload:
                        body_text = payload.decode(errors="ignore")
                        break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                body_text = payload.decode(errors="ignore")
    except Exception:
        body_text = ""
    return body_text or ""


def fetch_emails(
    host: str,
    user: str,
    password: str,
    folder: str = "INBOX",
    fetch_mode: str = "unseen",         # "unseen" | "recent"
    recent_count: int = 50,             # used when fetch_mode="recent"
    mark_seen: bool = True,             # mark fetched mails as \Seen
) -> List[Dict]:
    """
    Fetch emails from IMAP.

    Modes:
      - unseen: only UNSEEN messages (production default)
      - recent: last N messages (demo-safe; helps when mail was already opened)

    Returns list of dict: message_id, from_email, subject, body_text
    """
    if not host or not user or not password:
        return []

    mail = imaplib.IMAP4_SSL(host)
    mail.login(user, password)
    mail.select(folder)

    results: List[Dict] = []

    try:
        fetch_mode = (fetch_mode or "unseen").strip().lower()

        if fetch_mode == "recent":
            # Get all message ids, then take the last N
            status, data = mail.search(None, "ALL")
            if status != "OK":
                mail.logout()
                return []
            nums = data[0].split()
            if not nums:
                mail.logout()
                return []

            nums = nums[-max(1, int(recent_count)) :]  # last N
        else:
            # Default: only unseen
            status, data = mail.search(None, "UNSEEN")
            if status != "OK":
                mail.logout()
                return []
            nums = data[0].split()

        for num in nums:
            _, msg_data = mail.fetch(num, "(RFC822)")
            if not msg_data or not msg_data[0]:
                continue

            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            message_id = (msg.get("Message-ID", "") or "").strip()
            from_email = (msg.get("From", "") or "").strip()
            subject = _decode_subject(msg)
            body_text = _extract_body_text(msg)

            results.append(
                {
                    "message_id": message_id or f"imap-{num.decode(errors='ignore')}",
                    "from_email": from_email,
                    "subject": subject or "",
                    "body_text": body_text or "",
                }
            )

            if mark_seen:
                # Mark message as seen so it doesn't repeatedly show up in UNSEEN mode
                try:
                    mail.store(num, "+FLAGS", "\\Seen")
                except Exception:
                    pass

    finally:
        mail.logout()

    return results


# Backward compatible name used by worker.py
def fetch_unseen_emails(host: str, user: str, password: str, folder: str = "INBOX") -> List[Dict]:
    fetch_mode = os.getenv("IMAP_FETCH_MODE", "unseen")
    recent_count = int(os.getenv("IMAP_RECENT_COUNT", "50") or "50")
    mark_seen = (os.getenv("IMAP_MARK_SEEN", "true").lower() == "true")

    return fetch_emails(
        host=host,
        user=user,
        password=password,
        folder=folder,
        fetch_mode=fetch_mode,
        recent_count=recent_count,
        mark_seen=mark_seen,
    )