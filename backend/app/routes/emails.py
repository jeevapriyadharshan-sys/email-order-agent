# backend/app/routes/emails.py
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..models import EmailMessage, EmailStatus
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
    """
    Inbox should NOT stack forever.
    - Shows only non-archived emails.
    - Default shows active statuses (RECEIVED/EXTRACTING/NEEDS_HUMAN_REVIEW/READY_TO_CONFIRM).
    """
    q = db.query(EmailMessage)

    # Hide archived items (if column exists)
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
    """
    Processed emails (archived=True). These are ones for which order creation is done
    (or at least the workflow decided to archive them).
    """
    q = db.query(EmailMessage)

    if _has_archived_column():
        q = q.filter(EmailMessage.archived == True)  # noqa: E712
    else:
        # If archived column doesn't exist yet, fall back to showing completed statuses.
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
# Trigger processing manually
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

    # Queue background processing
    process_email_task.delay(email_id)
    return {"ok": True, "message": "Processing started", "email_id": email_id}


# ---------------------------
# Optional: Archive/unarchive manually (nice for ops)
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