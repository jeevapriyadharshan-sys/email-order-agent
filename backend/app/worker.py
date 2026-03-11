# backend/app/worker.py
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from .config import settings
from .db import SessionLocal
from .models import AgentState, EmailMessage, EmailStatus, ExtractionRun, HumanReview, Order
from .email.imap_ingest import fetch_unseen_emails
from .email.smtp_send import send_confirmation
from .extraction.regex_layer import extract_with_regex

try:
    from .extraction.gemini_layer import extract_with_gemini
except Exception:
    extract_with_gemini = None  # type: ignore

# ── Scheduler instance ────────────────────────────────────────────────────
_scheduler: Optional[BackgroundScheduler] = None


def start_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        return
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        agent_tick,
        "interval",
        seconds=15,
        id="agent_tick",
        max_instances=3,
        coalesce=True,
    )
    _scheduler.start()


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)


# ── Helpers ───────────────────────────────────────────────────────────────
REQUIRED_FIELDS = [
    "customer_name",
    "weight_kg",
    "pickup_location",
    "drop_location",
    "pickup_time_window",
]


def _now() -> datetime:
    return datetime.utcnow()


def _safe_json(obj: Any) -> Any:
    try:
        import json
        json.dumps(obj)
        return obj
    except Exception:
        return {"_non_serializable": str(obj)}


def _missing_fields(extracted: Dict[str, Any]) -> List[str]:
    missing: List[str] = []
    for k in REQUIRED_FIELDS:
        v = (extracted or {}).get(k)
        if v is None:
            missing.append(k)
        elif isinstance(v, str) and not v.strip():
            missing.append(k)
    return missing


def _merge(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    """Conservative merge: fill only missing/empty fields."""
    out = dict(base or {})
    for k, v in (extra or {}).items():
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        if k not in out or out.get(k) in (None, ""):
            out[k] = v
    return out


def _agent_enabled(db: Session) -> bool:
    st = db.query(AgentState).first()
    return bool(st and st.enabled)


def _ensure_human_review_row(db: Session, email_id: int) -> None:
    hr = db.query(HumanReview).filter(HumanReview.email_id == email_id).first()
    if not hr:
        hr = HumanReview(email_id=email_id, approved=False)
        db.add(hr)
        db.commit()


def _create_or_update_order(db: Session, em: EmailMessage) -> Order:
    ex = em.extracted or {}

    w = ex.get("weight_kg")
    try:
        weight_int = int(float(w)) if w not in (None, "") else 0
    except Exception:
        weight_int = 0

    existing = db.query(Order).filter(Order.email_id == em.id).first()

    if existing:
        existing.customer_name      = str(ex.get("customer_name", "")).strip()
        existing.weight_kg          = weight_int
        existing.pickup_location    = str(ex.get("pickup_location", "")).strip()
        existing.drop_location      = str(ex.get("drop_location", "")).strip()
        existing.pickup_time_window = str(ex.get("pickup_time_window", "")).strip()
        db.commit()
        db.refresh(existing)
        return existing

    job_id = f"JOB-{_now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    order = Order(
        job_id=job_id,
        email_id=em.id,
        customer_name=str(ex.get("customer_name", "")).strip(),
        weight_kg=weight_int,
        pickup_location=str(ex.get("pickup_location", "")).strip(),
        drop_location=str(ex.get("drop_location", "")).strip(),
        pickup_time_window=str(ex.get("pickup_time_window", "")).strip(),
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def _send_confirmation(db: Session, em: EmailMessage, order: Order) -> None:
    if not (settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD):
        em.last_error = (em.last_error + "\n" if em.last_error else "") + "SMTP not configured; confirmation skipped."
        db.commit()
        return

    to_addr = em.from_email
    if not to_addr or "@" not in to_addr:
        em.last_error = (em.last_error + "\n" if em.last_error else "") + f"Invalid recipient '{to_addr}'; confirmation skipped."
        db.commit()
        return

    ex = em.extracted or {}
    subject = f"Reconfirmation: Transport Order {order.job_id}"
    body = (
        f"Hello,\n\n"
        f"We received your transport request. Please reconfirm the details:\n\n"
        f"Job ID: {order.job_id}\n"
        f"Customer Name: {ex.get('customer_name')}\n"
        f"Weight (kg): {ex.get('weight_kg')}\n"
        f"Pickup Location: {ex.get('pickup_location')}\n"
        f"Drop Location: {ex.get('drop_location')}\n"
        f"Pickup Time Window: {ex.get('pickup_time_window')}\n\n"
        f"Reply to this email if any detail is incorrect.\n\n"
        f"Regards,\nEmail Order Agent\n"
    )

    try:
        send_confirmation(
            smtp_host=settings.SMTP_HOST,
            smtp_port=int(settings.SMTP_PORT),
            smtp_user=settings.SMTP_USER,
            smtp_password=settings.SMTP_PASSWORD,
            from_addr=(getattr(settings, "SMTP_FROM", "") or settings.SMTP_USER),
            to_addr=to_addr,
            subject=subject,
            body=body,
        )
        em.status = EmailStatus.CONFIRMATION_SENT
        db.commit()
    except Exception as e:
        em.last_error = (em.last_error + "\n" if em.last_error else "") + f"SMTP error (confirmation skipped): {str(e)}"
        db.commit()


def _send_missing_fields_request(db: Session, em: EmailMessage, missing: List[str]) -> None:
    if not (settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD):
        em.last_error = (em.last_error + "\n" if em.last_error else "") + "SMTP not configured; missing-fields request skipped."
        db.commit()
        return

    to_addr = em.from_email
    if not to_addr or "@" not in to_addr:
        em.last_error = (em.last_error + "\n" if em.last_error else "") + f"Invalid recipient '{to_addr}'; missing-fields request skipped."
        db.commit()
        return

    missing_list = "\n".join([f"- {m}" for m in missing])
    subject = "Action Required: Missing details for your transport request"
    body = (
        "Hello,\n\n"
        "We received your transport request but need the following details to proceed:\n\n"
        f"{missing_list}\n\n"
        "Please reply with the missing information in this format:\n\n"
        "Customer Name: ...\n"
        "Weight: ... kg\n"
        "Pickup Location: ...\n"
        "Drop Location: ...\n"
        "Pickup Date: ...\n"
        "Delivery Deadline: ...\n\n"
        "Regards,\n"
        "Email Order Agent\n"
    )

    try:
        send_confirmation(
            smtp_host=settings.SMTP_HOST,
            smtp_port=int(settings.SMTP_PORT),
            smtp_user=settings.SMTP_USER,
            smtp_password=settings.SMTP_PASSWORD,
            from_addr=(getattr(settings, "SMTP_FROM", "") or settings.SMTP_USER),
            to_addr=to_addr,
            subject=subject,
            body=body,
        )
        if hasattr(em, "missing_request_sent"):
            em.missing_request_sent = True
        db.commit()
    except Exception as e:
        em.last_error = (em.last_error + "\n" if em.last_error else "") + f"Missing-fields email failed: {str(e)}"
        db.commit()


# ── Core task functions (plain — no Celery) ───────────────────────────────

def process_email_task(email_id: int) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        em: Optional[EmailMessage] = db.query(EmailMessage).get(email_id)
        if not em:
            return {"ok": False, "error": "Email not found"}

        em.status = EmailStatus.EXTRACTING
        em.last_error = ""
        db.commit()

        text = em.body_text or ""
        # Start from whatever we already know (human review / previous run)
        extracted: Dict[str, Any] = dict(em.extracted or {})

        # --- Layer 1: Regex ---
        try:
            rex = extract_with_regex(text) or {}
            extracted = _merge(extracted, rex)
            db.add(ExtractionRun(
                email_id=em.id,
                layer="regex",
                input_snapshot=_safe_json({"text": text[:2000]}),
                output_snapshot=_safe_json({"extracted": extracted}),
                created_at=_now(),
            ))
            db.commit()
        except Exception as e:
            em.last_error = f"Regex error: {str(e)}"
            db.commit()

        missing = _missing_fields(extracted)

        # --- Layer 2: Gemini (only if fields still missing) ---
        if missing and settings.GEMINI_API_KEY and extract_with_gemini is not None:
            try:
                gem = extract_with_gemini(
                    text=text,
                    partial=extracted,
                    api_key=settings.GEMINI_API_KEY,
                    model_name=settings.GEMINI_MODEL,
                ) or {}
                extracted = _merge(extracted, gem)
                missing = _missing_fields(extracted)
                db.add(ExtractionRun(
                    email_id=em.id,
                    layer="gemini",
                    input_snapshot=_safe_json({"text": text[:2000]}),
                    output_snapshot=_safe_json({"extracted": extracted}),
                    created_at=_now(),
                ))
                db.commit()
            except Exception as e:
                em.last_error = (em.last_error + "\n" if em.last_error else "") + f"Gemini skipped: {str(e)}"
                db.commit()

        # Save extraction output
        em.extracted = extracted
        em.missing_fields = missing
        db.commit()

        # Still missing → human review
        if missing:
            em.status = EmailStatus.NEEDS_HUMAN_REVIEW
            db.commit()
            if not getattr(em, "missing_request_sent", False):
                _send_missing_fields_request(db, em, missing)
            _ensure_human_review_row(db, em.id)
            return {"ok": True, "status": em.status, "missing_fields": missing}

        # Complete → create order
        em.status = EmailStatus.READY_TO_CONFIRM
        db.commit()

        order = _create_or_update_order(db, em)
        em.status = EmailStatus.ORDER_CREATED
        if hasattr(em, "archived"):
            em.archived = True
        db.commit()

        _send_confirmation(db, em, order)

        return {"ok": True, "status": em.status, "job_id": order.job_id}
    except Exception as e:
        try:
            em = db.query(EmailMessage).get(email_id)
            if em:
                em.status = EmailStatus.FAILED
                em.last_error = str(e)
                db.commit()
        except Exception:
            pass
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


def ingest_emails_task() -> Dict[str, Any]:
    db = SessionLocal()
    try:
        if not (settings.IMAP_HOST and settings.IMAP_USER and settings.IMAP_PASSWORD):
            return {"ok": False, "error": "IMAP not configured"}

        items = fetch_unseen_emails(
            host=settings.IMAP_HOST,
            user=settings.IMAP_USER,
            password=settings.IMAP_PASSWORD,
            folder=settings.IMAP_FOLDER,
        )

        inserted, skipped = 0, 0
        for it in items:
            msg_id = it.get("message_id") or it.get("id") or str(uuid.uuid4())
            if db.query(EmailMessage).filter(EmailMessage.message_id == msg_id).first():
                skipped += 1
                continue

            em = EmailMessage(
                message_id=msg_id,
                from_email=it.get("from_email", ""),
                subject=it.get("subject", "") or "",
                body_text=it.get("body_text", "") or "",
                received_at=_now(),
                status=EmailStatus.RECEIVED,
                extracted={},
                missing_fields=[],
                last_error="",
            )
            db.add(em)
            db.commit()
            db.refresh(em)
            inserted += 1

            # Direct call — no Celery
            process_email_task(em.id)

        return {"ok": True, "inserted": inserted, "skipped": skipped}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


def agent_tick() -> Dict[str, Any]:
    db = SessionLocal()
    try:
        if not _agent_enabled(db):
            return {"ok": True, "message": "Agent disabled"}
        res = ingest_emails_task()
        return {"ok": True, "message": "Tick ok", "ingest": res}
    finally:
        db.close()