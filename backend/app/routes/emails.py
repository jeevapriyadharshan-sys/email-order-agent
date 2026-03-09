# backend/app/routes/emails.py
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_role
from ..db import get_db
from ..models import EmailMessage, EmailStatus, ExtractionRun, HumanReview
from ..worker import process_email_task

router = APIRouter(prefix="/emails", tags=["emails"])


# ---------------------------
# Helpers
# ---------------------------
ACTIVE_STATUSES = [
    EmailStatus.RECEIVED,
    EmailStatus.EXTRACTING,
    EmailStatus.NEEDS_HUMAN_REVIEW,
    EmailStatus.READY_TO_CONFIRM,
]


def _has_archived_column() -> bool:
    """
    Safety helper: if the DB hasn't been altered yet (archived column missing),
    we still don't want the whole API to crash.
    """
    return hasattr(EmailMessage, "archived")


# ---------------------------
# Inbox (active emails)
# ---------------------------
@router.get("", response_model=None)
def inbox(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    limit: int = Query(100, ge=1, le=500),
    include_processing: bool = Query(True, description="Include RECEIVED/EXTRACTING/READY_TO_CONFIRM"),
):
    q = db.query(EmailMessage)

    if _has_archived_column():
        q = q.filter(EmailMessage.archived == False)  # noqa: E712

    if include_processing:
        q = q.filter(EmailMessage.status.in_(ACTIVE_STATUSES))
    else:
        q = q.filter(EmailMessage.status == EmailStatus.NEEDS_HUMAN_REVIEW)

    items = q.order_by(EmailMessage.received_at.desc()).limit(limit).all()
    return items


# ---------------------------
# Processed / Archive
# ---------------------------
@router.get("/processed", response_model=None)
def processed(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    limit: int = Query(200, ge=1, le=1000),
):
    q = db.query(EmailMessage)

    if _has_archived_column():
        q = q.filter(EmailMessage.archived == True)  # noqa: E712
    else:
        q = q.filter(EmailMessage.status.in_([EmailStatus.ORDER_CREATED, EmailStatus.CONFIRMATION_SENT]))

    items = q.order_by(EmailMessage.received_at.desc()).limit(limit).all()
    return items


# ---------------------------
# Single email detail
# ---------------------------
@router.get("/{email_id}", response_model=None)
def get_email(
    email_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    em = db.query(EmailMessage).get(email_id)
    if not em:
        raise HTTPException(status_code=404, detail="Email not found")
    return em


# ---------------------------
# Trigger processing manually (direct call, no Celery)
# ---------------------------
@router.post("/{email_id}/process", response_model=None)
def process_email_now(
    email_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    em = db.query(EmailMessage).get(email_id)
    if not em:
        raise HTTPException(status_code=404, detail="Email not found")

    # Direct call instead of .delay()
    process_email_task(email_id)
    return {"ok": True, "message": "Processing started", "email_id": email_id}


# ---------------------------
# Optional: Archive/unarchive manually
# ---------------------------
@router.post("/{email_id}/archive", response_model=None)
def archive_email(
    email_id: int,
    archived: bool = True,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    em = db.query(EmailMessage).get(email_id)
    if not em:
        raise HTTPException(status_code=404, detail="Email not found")

    if not _has_archived_column():
        raise HTTPException(
            status_code=400,
            detail="Archived flag not available. Run DB migration to add emails.archived column.",
        )

    em.archived = bool(archived)
    db.commit()
    return {"ok": True, "email_id": email_id, "archived": em.archived}


# ---------------------------
# Clear inbox (admin only)
# ---------------------------
@router.delete("/clear-inbox", response_model=None)
def clear_inbox(
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """
    Deletes all EmailMessage rows and their related
    ExtractionRun + HumanReview records.
    Orders table is NOT touched.
    """
    db.query(HumanReview).delete(synchronize_session=False)
    db.query(ExtractionRun).delete(synchronize_session=False)
    db.query(EmailMessage).delete(synchronize_session=False)
    db.commit()
    return {"ok": True, "message": "Inbox cleared successfully"}