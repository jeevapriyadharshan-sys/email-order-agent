# backend/app/worker.py
from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import text
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

# ── Scheduler ──────────────────────────────────────────────────────────────
_scheduler: Optional[BackgroundScheduler] = None


def start_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        return
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        agent_tick, "interval", seconds=15,
        id="agent_tick", max_instances=3, coalesce=True,
    )
    _scheduler.start()


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)


# ── Constants ──────────────────────────────────────────────────────────────
REQUIRED_FIELDS = [
    "customer_name", "weight_kg",
    "pickup_location", "drop_location", "pickup_time_window",
]


def _now() -> datetime:
    return datetime.utcnow()


def _safe_json(obj: Any) -> Any:
    try:
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
    out = dict(base or {})
    for k, v in (extra or {}).items():
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        if k not in out or out.get(k) in (None, ""):
            out[k] = v
    return out


def _save_extracted(db: Session, email_id: int,
                    extracted: Dict, missing: List[str], status: str) -> None:
    """
    Use raw SQL to force-write JSONB columns.
    This bypasses ALL SQLAlchemy change-tracking issues.
    """
    db.execute(
        text("""
            UPDATE emails
               SET extracted      = CAST(:extracted AS jsonb),
                   missing_fields = CAST(:missing   AS jsonb),
                   status         = :status
             WHERE id = :id
        """),
        {
            "extracted": json.dumps(extracted),
            "missing":   json.dumps(missing),
            "status":    status,
            "id":        email_id,
        }
    )
    db.commit()


def _set_status(db: Session, email_id: int, status: str, error: str = "") -> None:
    db.execute(
        text("UPDATE emails SET status = :s, last_error = :e WHERE id = :id"),
        {"s": status, "e": error, "id": email_id}
    )
    db.commit()


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
        job_id=job_id, email_id=em.id,
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
        _set_status(db, em.id, em.status,
                    (em.last_error or "") + "\nSMTP not configured; confirmation skipped.")
        return

    to_addr = em.from_email
    if not to_addr or "@" not in to_addr:
        return

    ex = em.extracted or {}
    subject = f"Reconfirmation: Transport Order {order.job_id}"
    body = (
        f"Hello,\n\nWe received your transport request. Please reconfirm:\n\n"
        f"Job ID: {order.job_id}\n"
        f"Customer Name: {ex.get('customer_name')}\n"
        f"Weight (kg): {ex.get('weight_kg')}\n"
        f"Pickup Location: {ex.get('pickup_location')}\n"
        f"Drop Location: {ex.get('drop_location')}\n"
        f"Pickup Time Window: {ex.get('pickup_time_window')}\n\n"
        f"Reply if any detail is incorrect.\n\nRegards,\nEmail Order Agent\n"
    )
    try:
        send_confirmation(
            smtp_host=settings.SMTP_HOST,
            smtp_port=int(settings.SMTP_PORT),
            smtp_user=settings.SMTP_USER,
            smtp_password=settings.SMTP_PASSWORD,
            from_addr=(getattr(settings, "SMTP_FROM", "") or settings.SMTP_USER),
            to_addr=to_addr, subject=subject, body=body,
        )
        _set_status(db, em.id, "CONFIRMATION_SENT")
    except Exception as e:
        _set_status(db, em.id, em.status,
                    (em.last_error or "") + f"\nSMTP error: {str(e)}")


def _send_missing_fields_request(db: Session, em: EmailMessage, missing: List[str]) -> None:
    if not (settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD):
        return
    to_addr = em.from_email
    if not to_addr or "@" not in to_addr:
        return

    missing_list = "\n".join([f"- {m}" for m in missing])
    subject = "Action Required: Missing details for your transport request"
    body = (
        "Hello,\n\nWe received your transport request but need:\n\n"
        f"{missing_list}\n\n"
        "Please reply with:\nCustomer Name: ...\nWeight: ... kg\n"
        "Pickup Location: ...\nDrop Location: ...\n"
        "Pickup Date: ...\nDelivery Deadline: ...\n\n"
        "Regards,\nEmail Order Agent\n"
    )
    try:
        send_confirmation(
            smtp_host=settings.SMTP_HOST,
            smtp_port=int(settings.SMTP_PORT),
            smtp_user=settings.SMTP_USER,
            smtp_password=settings.SMTP_PASSWORD,
            from_addr=(getattr(settings, "SMTP_FROM", "") or settings.SMTP_USER),
            to_addr=to_addr, subject=subject, body=body,
        )
        db.execute(
            text("UPDATE emails SET missing_request_sent = true WHERE id = :id"),
            {"id": em.id}
        )
        db.commit()
    except Exception:
        pass


# ── Core pipeline ──────────────────────────────────────────────────────────

def process_email_task(email_id: int) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        em: Optional[EmailMessage] = db.query(EmailMessage).get(email_id)
        if not em:
            return {"ok": False, "error": "Email not found"}

        _set_status(db, email_id, "EXTRACTING", "")
        db.expire(em)
        em = db.query(EmailMessage).get(email_id)

        text_body = em.body_text or ""
        extracted: Dict[str, Any] = copy.deepcopy(em.extracted or {})

        # --- Layer 1: Regex ---
        try:
            rex = extract_with_regex(text_body) or {}
            extracted = _merge(extracted, rex)
            db.add(ExtractionRun(
                email_id=em.id, layer="regex",
                input_snapshot=_safe_json({"text": text_body[:2000]}),
                output_snapshot=_safe_json({"extracted": extracted}),
                created_at=_now(),
            ))
            db.commit()
        except Exception as e:
            db.execute(text("UPDATE emails SET last_error = :e WHERE id = :id"),
                       {"e": f"Regex error: {e}", "id": email_id})
            db.commit()

        missing = _missing_fields(extracted)

        # --- Layer 2: Gemini ---
        if missing and settings.GEMINI_API_KEY and extract_with_gemini is not None:
            try:
                gem = extract_with_gemini(
                    text=text_body, partial=extracted,
                    api_key=settings.GEMINI_API_KEY,
                    model_name=settings.GEMINI_MODEL,
                ) or {}
                extracted = _merge(extracted, gem)
                missing = _missing_fields(extracted)
                db.add(ExtractionRun(
                    email_id=em.id, layer="gemini",
                    input_snapshot=_safe_json({"text": text_body[:2000]}),
                    output_snapshot=_safe_json({"extracted": extracted}),
                    created_at=_now(),
                ))
                db.commit()
            except Exception as e:
                db.execute(
                    text("UPDATE emails SET last_error = :e WHERE id = :id"),
                    {"e": f"Gemini skipped: {e}", "id": email_id}
                )
                db.commit()

        # ✅ Save with raw SQL — bypasses all JSONB tracking issues
        new_status = "NEEDS_HUMAN_REVIEW" if missing else "READY_TO_CONFIRM"
        _save_extracted(db, email_id, extracted, missing, new_status)

        # Reload fresh from DB
        db.expire_all()
        em = db.query(EmailMessage).get(email_id)

        if missing:
            mr_sent = getattr(em, "missing_request_sent", False)
            if not mr_sent:
                _send_missing_fields_request(db, em, missing)
            _ensure_human_review_row(db, email_id)
            return {"ok": True, "status": new_status, "missing_fields": missing}

        # Create order
        _set_status(db, email_id, "READY_TO_CONFIRM")
        db.expire_all()
        em = db.query(EmailMessage).get(email_id)

        order = _create_or_update_order(db, em)
        _set_status(db, email_id, "ORDER_CREATED")

        db.execute(
            text("UPDATE emails SET archived = true WHERE id = :id"),
            {"id": email_id}
        )
        db.commit()

        db.expire_all()
        em = db.query(EmailMessage).get(email_id)
        _send_confirmation(db, em, order)

        return {"ok": True, "status": "ORDER_CREATED", "job_id": order.job_id}

    except Exception as e:
        try:
            _set_status(db, email_id, "FAILED", str(e))
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
            host=settings.IMAP_HOST, user=settings.IMAP_USER,
            password=settings.IMAP_PASSWORD, folder=settings.IMAP_FOLDER,
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
                extracted={}, missing_fields=[], last_error="",
            )
            db.add(em)
            db.commit()
            db.refresh(em)
            inserted += 1
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
        return {"ok": True, "message": "Tick ok", "ingest": ingest_emails_task()}
    finally:
        db.close()